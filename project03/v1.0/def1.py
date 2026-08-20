"""
extract_ordersDEF.py
====================
Reads order files (image, audio, text) from the Data folder,
uses the Google Gemini API to extract item descriptions and quantities,
maps them to the customer's Schablone (product catalog) in Masterdata/Schablone.xlsx,
and writes the result to orders_output.json.

Supported order file formats:
  .jpg / .jpeg / .png  -> image order
  .m4a / .mp3 / .wav   -> audio order  
  .txt                 -> text order

File naming convention expected: <CustomerCode>_<OrderNumber>[_<Part>].<ext>
  e.g.  A0233_0001.jpg   ->  CustomerCode = A0233, OrderNumber = 0001
"""

import os
import re
import sys
import json
import pathlib
import pandas as pd
from collections import defaultdict
from google import genai
from google.genai import types

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR  = pathlib.Path(__file__).parent
DATA_DIR     = PROJECT_DIR / "Data"
SCHABLONE    = PROJECT_DIR / "Masterdata" / "Schablone.xlsx"
OUTPUT_FILE  = PROJECT_DIR / "orders_output.json"

# API key: read from environment or fall back to the hardcoded key in project
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyD5Dsum-b6g_qpScw2KITj_Mg0L1KdlLdw")

# Extensions that contain the original order (exclude .csv which are already
# extracted reference files, and .py / .xlsx / .docx / .md / .m4a test)
ORDER_EXTENSIONS = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".m4a":  "audio/mp4",
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".txt":  "text/plain",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_schablone(path: pathlib.Path) -> pd.DataFrame:
    """Load the customer product catalog from Excel."""
    print(f"Loading Schablone from {path} …")
    df = pd.read_excel(path)
    # Normalise column names (strip whitespace)
    df.columns = [c.strip() for c in df.columns]
    print(f"  -> {len(df)} rows loaded, customers: {df['Customercode'].nunique()}")
    return df


def find_and_group_order_files(directory: pathlib.Path) -> list[dict]:
    """
    Scan the directory for order files and group multi-part files
    belonging to the same (CustomerCode, OrderNumber) together.

    Returns a list of order groups, each dict:
      {
        customer_code: str,
        order_number:  str,
        files: [ {path, mime_type}, ... ]   # sorted by part number
      }
    """
    # Pattern: CustomerCode_OrderNumber[_Part].ext
    pattern = re.compile(r"^([A-Za-z0-9]+)_(\d+)(?:_(\d+))?(\.[^.]+)$")
    groups = defaultdict(lambda: {"files": []})

    for file in sorted(directory.iterdir()):
        m = pattern.match(file.name)
        if not m:
            continue
        ext = m.group(4).lower()
        if ext not in ORDER_EXTENSIONS:
            continue

        customer = m.group(1).upper()
        order_no = m.group(2)
        part_no  = m.group(3) or "0"   # default "0" if no part suffix
        mime     = ORDER_EXTENSIONS[ext]

        key = (customer, order_no)
        groups[key]["customer_code"] = customer
        groups[key]["order_number"]  = order_no
        groups[key]["files"].append({
            "path":    file,
            "mime":    mime,
            "part_no": part_no,
        })

    # Sort each group's files by part number, then return sorted by key
    result = []
    for key in sorted(groups.keys()):
        g = groups[key]
        g["files"].sort(key=lambda f: int(f["part_no"]))
        result.append(g)

    return result


def build_schablone_context(df: pd.DataFrame, customer_code: str) -> str:
    """
    Build a compact text representation of the customer's allowed items
    to inject into the Gemini prompt.
    """
    subset = df[df["Customercode"] == customer_code].copy()
    if subset.empty:
        return f"(No items found in Schablone for customer {customer_code})"

    lines = [
        f"Customer: {customer_code}",
        f"Available items ({len(subset)} total):",
        "ItemCode | Description (German) | Unit | PCPerUnit",
        "-" * 60,
    ]
    for _, row in subset.iterrows():
        blocked = " [BLOCKED]" if str(row.get("Blocked", "")).strip().lower() in ("yes", "ja", "1", "true") else ""
        lines.append(
            f"{row['ItemCode']} | {row['DescriptionGerman']} | "
            f"{row['UnitofMeasurement']} | {row['PCPerUnit']}{blocked}"
        )
    return "\n".join(lines)


def extract_order_with_gemini(
    client: genai.Client,
    order: dict,
    schablone_context: str,
) -> list[dict]:
    """
    Send all files of an order to Gemini and return extracted items.
    Handles multi-part orders by including all files as separate content parts.
    """
    customer_code = order["customer_code"]
    files         = order["files"]
    file_names    = ", ".join(f["path"].name for f in files)
    print(f"  Processing [{file_names}] for customer {customer_code} …")

    # ── Build the prompt ──────────────────────────────────────────────────────
    system_prompt = (
        "You are an assistant that processes food-service orders written in German or dialect. "
        "Your job is to identify the ordered items and quantities, then match them to the "
        "provided product catalog (Schablone) by ItemCode. "
        "Return ONLY valid JSON — an array of objects, nothing else."
    )

    user_prompt = f"""
Here is the product catalog for customer {customer_code}:

{schablone_context}

---

Analyse the attached order file(s). There may be multiple files (images, audio clips, text)
that all belong to the SAME order — combine them into a single unified list.

For each ordered item:
1. Identify what was ordered (even if abbreviated, in dialect, or transcribed from audio).
2. Find the best matching ItemCode from the catalog above.
3. Extract the quantity as stated in the order (as a number).

Return a JSON array with EXACTLY this structure (no markdown, no explanation):
[
  {{
    "item_code": "XXXXX",
    "description_german": "...",
    "unit": "...",
    "ordered_pieces": <number or null>
  }}
]

If you cannot confidently match an item, set item_code to null and describe it.
If the quantity is unclear, use null.
"""

    # ── Build Gemini content parts ────────────────────────────────────────────
    parts = [types.Part.from_text(text=user_prompt)]

    for f in files:
        file_bytes = f["path"].read_bytes()
        mime       = f["mime"]
        if mime.startswith("text/"):
            text_content = file_bytes.decode("latin-1")
            parts.append(types.Part.from_text(
                text=f"\n\nOrder file ({f['path'].name}):\n{text_content}"
            ))
        else:
            parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime))

    contents = [
        types.Content(
            role="user",
            parts=parts,
        )
    ]

    # ── Call Gemini helper ───────────────────────────────────────────────────
    def call_gemini(max_tokens: int) -> str:
        cfg = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            max_output_tokens=max_tokens,
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=cfg,
        )
        return resp.text.strip()

    def clean_json(raw: str) -> str:
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.rstrip())
        return raw

    raw_text = clean_json(call_gemini(8192))

    try:
        items = json.loads(raw_text)
        if not isinstance(items, list):
            items = [items]
    except json.JSONDecodeError as exc:
        print(f"    [WARN] JSON parse error ({exc}), retrying with higher token limit...")
        raw_text = clean_json(call_gemini(16384))
        try:
            items = json.loads(raw_text)
            if not isinstance(items, list):
                items = [items]
        except json.JSONDecodeError as exc2:
            print(f"    [ERROR] Retry also failed: {exc2}")
            print(f"    First 500 chars: {raw_text[:500]}")
            items = []

    return items


def enrich_with_schablone(
    extracted: list[dict],
    df: pd.DataFrame,
    customer_code: str,
) -> list[dict]:
    """Add PCPerUnit from Schablone and compute final_quantity."""
    subset = df[df["Customercode"] == customer_code].set_index("ItemCode")
    enriched = []

    for item in extracted:
        code           = item.get("item_code")
        ordered_pieces = item.get("ordered_pieces")

        if code and code in subset.index:
            row         = subset.loc[code]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            pc_per_unit = float(row["PCPerUnit"]) if pd.notna(row["PCPerUnit"]) else None
            unit        = str(row["UnitofMeasurement"]).strip()
            desc_de     = str(row["DescriptionGerman"]).strip()
        else:
            pc_per_unit = None
            unit        = item.get("unit", "")
            desc_de     = item.get("description_german", "")

        # Compute final quantity
        if ordered_pieces is not None and pc_per_unit is not None:
            try:
                final_quantity = round(float(ordered_pieces) * pc_per_unit, 4)
            except (ValueError, TypeError):
                final_quantity = None
        else:
            final_quantity = None

        enriched.append({
            "item_code":      code,
            "description":    desc_de,
            "unit":           unit,
            "ordered_pieces": ordered_pieces,
            "pc_per_unit":    pc_per_unit,
            "final_quantity": final_quantity,
        })

    return enriched


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Order Extraction & Schablone Mapping (DEF)")
    print(f"Input folder : {DATA_DIR}")
    print(f"Output file  : {OUTPUT_FILE}")
    print("=" * 60)

    # Ensure output directories exist
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Schablone
    schablone_df = load_schablone(SCHABLONE)

    # 2. Find and group order files
    order_groups = find_and_group_order_files(DATA_DIR)
    if not order_groups:
        print("No order files found. Exiting.")
        return

    print(f"\nFound {len(order_groups)} order(s):")
    for g in order_groups:
        files_str = ", ".join(f["path"].name for f in g["files"])
        print(f"  {g['customer_code']}_{g['order_number']} -> [{files_str}]")

    # 3. Load existing results for resuming (from OUTPUT_FILE or DATA_DIR/orders_output.json)
    all_results = []
    processed_keys = set()
    
    for path_to_load in [OUTPUT_FILE, DATA_DIR / "orders_output.json"]:
        if path_to_load.exists():
            try:
                with open(path_to_load, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > len(all_results):
                        all_results = data
                        print(f"Resuming using {path_to_load.name} ({len(all_results)} orders loaded).")
            except Exception as e:
                print(f"Error loading {path_to_load.name}: {e}")

    processed_keys = {
        (r["customer_code"], r["order_number"]) for r in all_results
    }

    # 4. Initialize Gemini client
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 5. Process each order group
    for i, order in enumerate(order_groups, 1):
        customer_code = order["customer_code"]
        order_number = order["order_number"]
        key = (customer_code, order_number)

        if key in processed_keys:
            print(f"\n[{i}/{len(order_groups)}] Skipping {customer_code}_{order_number} (already processed)")
            continue

        print(f"\n[{i}/{len(order_groups)}] {customer_code}_{order_number}")

        schablone_ctx = build_schablone_context(schablone_df, customer_code)
        extracted     = extract_order_with_gemini(client, order, schablone_ctx)
        enriched      = enrich_with_schablone(extracted, schablone_df, customer_code)

        source_files = [f["path"].name for f in order["files"]]
        result = {
            "source_files":  source_files,
            "customer_code": customer_code,
            "order_number":  order_number,
            "items":         enriched,
        }
        all_results.append(result)

        for item in enriched:
            code  = item["item_code"] or "?"
            desc  = (item["description"] or "?")[:38]
            qty   = item["ordered_pieces"]
            final = item["final_quantity"]
            unit  = item["unit"]
            print(f"    {code:8s}  {desc:38s}  {qty} -> {final} {unit}")

        # Write incrementally to both output locations
        for dest in [OUTPUT_FILE, DATA_DIR / "orders_output.json"]:
            try:
                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error writing to {dest}: {e}")

    print(f"\n{'=' * 60}")
    print(f"[DONE] {len(all_results)} orders written to:")
    print(f"       {OUTPUT_FILE}")
    print(f"       {DATA_DIR / 'orders_output.json'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

