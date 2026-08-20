"""
extract_ordersDEF.py
====================
Reads order files (image, audio, text) from the Data folder,
uses the Google Gemini API to extract item descriptions and quantities,
maps them to the customer's Schablone (product catalog) in Masterdata/Schablone.xlsx,
and writes the result to orders_output.json.

Enhanced with:
  - Fuzzy matching  : RapidFuzz token_set_ratio + trigram overlap for robust
                      item-description matching when Gemini returns imperfect text.
  - Probabilistic   : Every match carries a confidence score (0–1) combining
    scoring           multiple signals (exact code hit, fuzzy desc, semantic sim).
  - Reinforcement   : A lightweight Q-table (rl_feedback.json) learns from
    learning          human accept/reject feedback so match weights improve over
                      time without retraining.

Supported order file formats:
  .jpg / .jpeg / .png  -> image order
  .m4a / .mp3 / .wav   -> audio order
  .txt                 -> text order

File naming convention expected: <CustomerCode>_<OrderNumber>[_<Part>].<ext>
  e.g.  A0233_0001.jpg   ->  CustomerCode = A0233, OrderNumber = 0001
"""

import sys
import site

# Dynamically inject user site-packages directory to resolve imports
user_site = site.getusersitepackages() if hasattr(site, 'getusersitepackages') else None
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

import os
import re
import sys
import json
import math
import pathlib
import unicodedata
from collections import defaultdict
from typing import Optional

import pandas as pd
import numpy as np

# ── Optional / graceful imports ───────────────────────────────────────────────
try:
    from rapidfuzz import fuzz as rfuzz
    from rapidfuzz import process as rfprocess
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    print("[WARN] rapidfuzz not installed – falling back to difflib fuzzy matching.")
    from difflib import SequenceMatcher

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    print("[WARN] google-genai not installed – Gemini extraction will be skipped.")

# ── Configuration ───────────────────────────────────────────────────────────

PROJECT_DIR  = pathlib.Path(__file__).parent
DATA_DIR     = PROJECT_DIR / "Data"
SCHABLONE    = PROJECT_DIR / "Masterdata" / "Schablone.xlsx"
OUTPUT_FILE  = PROJECT_DIR / "orders_output.json"
RL_FEEDBACK  = PROJECT_DIR / "rl_feedback.json"   # persisted Q-table

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyD9VyLF0dUeVGxyjRQBl1z9MzhKPKjHk8Y")

ORDER_EXTENSIONS = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".m4a":  "audio/mp4",
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".txt":  "text/plain",
}

# ── Scoring weights (tuned at start; RL adjusts them over time) ───────────────
DEFAULT_WEIGHTS = {
    "exact_code":    1.00,   # Gemini returned a valid ItemCode directly
    "fuzzy_desc":    0.60,   # fuzzy description similarity score
    "trigram":       0.30,   # trigram overlap bonus
    "blocked_penalty": -0.40,  # deduct if the matched item is blocked
}

# Minimum confidence to accept a match without flagging as uncertain
CONFIDENCE_THRESHOLD = 0.45

# ── RL hyperparameters ────────────────────────────────────────────────────────
RL_ALPHA  = 0.15   # learning rate
RL_GAMMA  = 0.90   # discount factor (not used in tabular Q here, kept for extension)
RL_REWARD_ACCEPT = +1.0
RL_REWARD_REJECT = -1.0


# ═════════════════════════════════════════════════════════════════════════════
# Section 1 – Fuzzy & probabilistic matching utilities
# ═════════════════════════════════════════════════════════════════════════════

def safe_str(val) -> Optional[str]:
    """Convert pandas/excel values to standard string or None, handling datetimes."""
    if pd.isna(val):
        return None
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def safe_float(val) -> Optional[float]:
    """Convert pandas/excel values to standard float or None."""
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _normalize(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def _trigrams(text: str) -> set:
    """Return the set of character trigrams for a string."""
    t = _normalize(text)
    return {t[i:i+3] for i in range(len(t) - 2)} if len(t) >= 3 else set()


def trigram_similarity(a: str, b: str) -> float:
    """Jaccard similarity of trigram sets."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def fuzzy_score(query: str, candidate: str) -> float:
    """
    Combined fuzzy similarity in [0, 1].
    Uses rapidfuzz token_set_ratio when available, difflib otherwise.
    """
    if not query or not candidate:
        return 0.0
    if HAS_RAPIDFUZZ:
        return rfuzz.token_set_ratio(_normalize(query), _normalize(candidate)) / 100.0
    else:
        return SequenceMatcher(None, _normalize(query), _normalize(candidate)).ratio()


def best_fuzzy_match(
    query_desc: str,
    catalog: pd.DataFrame,
    top_n: int = 5,
) -> list[dict]:
    """
    Find the top-N catalog rows whose DescriptionGerman best matches query_desc.
    Returns a list of dicts sorted by combined_score descending.
    """
    results = []
    q_norm = _normalize(query_desc)

    for _, row in catalog.iterrows():
        desc = str(row.get("DescriptionGerman", ""))
        fz   = fuzzy_score(q_norm, desc)
        tg   = trigram_similarity(q_norm, desc)
        combined = 0.7 * fz + 0.3 * tg          # weighted blend
        results.append({
            "item_code":    safe_str(row.get("ItemCode")),
            "description":  desc,
            "unit":         str(row.get("UnitofMeasurement", "")).strip(),
            "pc_per_unit":  safe_float(row.get("PCPerUnit")),
            "blocked":      str(row.get("Blocked", "")).strip().lower() in ("yes", "ja", "1", "true"),
            "fuzzy_score":  round(fz, 4),
            "trigram_score":round(tg, 4),
            "combined":     round(combined, 4),
        })

    results.sort(key=lambda x: x["combined"], reverse=True)
    return results[:top_n]


# ═════════════════════════════════════════════════════════════════════════════
# Section 2 – Probabilistic confidence scoring
# ═════════════════════════════════════════════════════════════════════════════

def compute_confidence(
    gemini_code: Optional[str],
    gemini_desc: Optional[str],
    best_match: dict,
    weights: dict,
) -> float:
    """
    Compute a confidence score in [0, 1] for an item match.

    Signals used:
      - exact_code    : Gemini returned an ItemCode that exists in catalog
      - fuzzy_desc    : top fuzzy similarity between Gemini description & catalog
      - trigram       : trigram bonus
      - blocked_penalty: deduct for blocked items
    """
    score = 0.0

    # Signal 1 – Gemini gave us a matching code
    if gemini_code and gemini_code == best_match.get("item_code"):
        score += weights["exact_code"]
    else:
        # Partial credit when code differs but description is strong
        score += best_match["fuzzy_score"]  * weights["fuzzy_desc"]
        score += best_match["trigram_score"] * weights["trigram"]

    # Signal 2 – Blocked item penalty
    if best_match.get("blocked"):
        score += weights["blocked_penalty"]

    # Clamp to [0, 1]
    return round(max(0.0, min(1.0, score)), 4)


def sigmoid(x: float) -> float:
    """Sigmoid function to squash unbounded values to (0,1)."""
    return 1.0 / (1.0 + math.exp(-x))


# ═════════════════════════════════════════════════════════════════════════════
# Section 3 – Reinforcement learning (Q-table on match features)
# ═════════════════════════════════════════════════════════════════════════════

class RLMatcher:
    """
    Lightweight tabular RL agent that learns match-weight adjustments.

    State  : discretised confidence bucket  (e.g. "0.4-0.5")
    Action : accept / reject
    Q-table: maps (state, action) -> Q-value

    After each human feedback call (accept_feedback / reject_feedback),
    the Q-table is updated and the live weights are nudged in the
    direction that maximises future reward.
    """

    BUCKETS = [(i/10, i/10 + 0.1) for i in range(0, 10)]   # 0.0–0.1, …, 0.9–1.0

    def __init__(self, feedback_path: pathlib.Path, weights: dict):
        self.path    = feedback_path
        self.weights = dict(weights)          # live copy; mutated by RL
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text("utf-8"))
                self.q_table   = data.get("q_table", {})
                self.weights   = data.get("weights", self.weights)
                self.n_updates = data.get("n_updates", 0)
                print(f"[RL] Loaded Q-table ({self.n_updates} updates) from {self.path.name}")
            except Exception as e:
                print(f"[RL] Could not load feedback file: {e}")
                self._reset()
        else:
            self._reset()

    def _reset(self):
        self.q_table   = {}
        self.n_updates = 0

    def _save(self):
        data = {
            "q_table":   self.q_table,
            "weights":   self.weights,
            "n_updates": self.n_updates,
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    # ── State discretisation ─────────────────────────────────────────────────

    @staticmethod
    def _bucket(confidence: float) -> str:
        lo = min(int(confidence * 10) / 10, 0.9)
        return f"{lo:.1f}-{lo+0.1:.1f}"

    # ── Q-value helpers ───────────────────────────────────────────────────────

    def _q(self, state: str, action: str) -> float:
        return self.q_table.get(f"{state}|{action}", 0.0)

    def _set_q(self, state: str, action: str, value: float):
        self.q_table[f"{state}|{action}"] = round(value, 6)

    # ── Q-table update (Bellman-style, single step) ───────────────────────────

    def _update(self, confidence: float, reward: float):
        state  = self._bucket(confidence)
        action = "accept" if reward > 0 else "reject"
        old_q  = self._q(state, action)
        new_q  = old_q + RL_ALPHA * (reward - old_q)   # simplified TD(0)
        self._set_q(state, action, new_q)
        self.n_updates += 1

        # Nudge weights based on reward signal
        self._adjust_weights(confidence, reward)
        self._save()

    def _adjust_weights(self, confidence: float, reward: float):
        """
        Heuristic weight adaptation:
          - Positive reward at low confidence → increase fuzzy/trigram weights.
          - Negative reward at high confidence → penalise over-reliance on exact_code.
        """
        delta = RL_ALPHA * reward * 0.05          # small nudge per update
        if reward > 0 and confidence < 0.55:
            self.weights["fuzzy_desc"]  = min(1.0, self.weights["fuzzy_desc"]  + delta)
            self.weights["trigram"]     = min(1.0, self.weights["trigram"]     + delta)
        elif reward < 0 and confidence > 0.75:
            self.weights["exact_code"]  = max(0.5, self.weights["exact_code"]  + delta)  # delta<0

    # ── Public API ────────────────────────────────────────────────────────────

    def best_action(self, confidence: float) -> str:
        """Return the greedy action for this confidence level."""
        state = self._bucket(confidence)
        qa = self._q(state, "accept")
        qr = self._q(state, "reject")
        return "accept" if qa >= qr else "reject"

    def accept_feedback(self, confidence: float):
        """Call when a human confirms the match was correct."""
        self._update(confidence, RL_REWARD_ACCEPT)
        print(f"[RL] +reward for conf={confidence:.3f}  (updates={self.n_updates})")

    def reject_feedback(self, confidence: float):
        """Call when a human marks the match as wrong."""
        self._update(confidence, RL_REWARD_REJECT)
        print(f"[RL] -reward for conf={confidence:.3f}  (updates={self.n_updates})")

    def summary(self) -> str:
        return (
            f"Q-table entries: {len(self.q_table)}  |  "
            f"Updates: {self.n_updates}  |  "
            f"Weights: {json.dumps({k: round(v,3) for k,v in self.weights.items()})}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Section 4 – Original helpers (load_schablone, find_and_group, etc.)
# ═════════════════════════════════════════════════════════════════════════════

def load_schablone(path: pathlib.Path) -> pd.DataFrame:
    print(f"Loading Schablone from {path} …")
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    
    # Normalize core columns to standard types to prevent datetime/numpy issues
    for col in ["Customercode", "ItemCode", "DescriptionGerman", "UnitofMeasurement"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: "" if pd.isna(x) else (x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x).strip()))
            
    print(f"  -> {len(df)} rows loaded, customers: {df['Customercode'].nunique()}")
    return df


def find_and_group_order_files(directory: pathlib.Path) -> list[dict]:
    pattern = re.compile(r"^([A-Za-z0-9]+)_(\d+)(?:_(\d+))?(\.[^.]+)$")
    groups  = defaultdict(lambda: {"files": []})

    for file in sorted(directory.iterdir()):
        m = pattern.match(file.name)
        if not m:
            continue
        ext = m.group(4).lower()
        if ext not in ORDER_EXTENSIONS:
            continue
        customer = m.group(1).upper()
        order_no = m.group(2)
        part_no  = m.group(3) or "0"
        mime     = ORDER_EXTENSIONS[ext]
        key      = (customer, order_no)
        groups[key]["customer_code"] = customer
        groups[key]["order_number"]  = order_no
        groups[key]["files"].append({"path": file, "mime": mime, "part_no": part_no})

    result = []
    for key in sorted(groups.keys()):
        g = groups[key]
        g["files"].sort(key=lambda f: int(f["part_no"]))
        result.append(g)
    return result


def build_schablone_context(df: pd.DataFrame, customer_code: str) -> str:
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
    client,
    order: dict,
    schablone_context: str,
) -> list[dict]:
    customer_code = order["customer_code"]
    files         = order["files"]
    file_names    = ", ".join(f["path"].name for f in files)
    print(f"  Processing [{file_names}] for customer {customer_code} …")

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

    parts = [types.Part.from_text(text=user_prompt)]
    for f in files:
        file_bytes = f["path"].read_bytes()
        mime = f["mime"]
        if mime.startswith("text/"):
            text_content = file_bytes.decode("latin-1")
            parts.append(types.Part.from_text(
                text=f"\n\nOrder file ({f['path'].name}):\n{text_content}"
            ))
        else:
            parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime))

    contents = [types.Content(role="user", parts=parts)]

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
        print(f"    [WARN] JSON parse error ({exc}), retrying …")
        raw_text = clean_json(call_gemini(16384))
        try:
            items = json.loads(raw_text)
            if not isinstance(items, list):
                items = [items]
        except json.JSONDecodeError as exc2:
            print(f"    [ERROR] Retry failed: {exc2}")
            items = []

    return items


# ═════════════════════════════════════════════════════════════════════════════
# Section 5 – Enhanced enrichment: fuzzy + probabilistic + RL
# ═════════════════════════════════════════════════════════════════════════════

def enrich_with_schablone(
    extracted: list[dict],
    df: pd.DataFrame,
    customer_code: str,
    rl: "RLMatcher",
) -> list[dict]:
    """
    For each Gemini-extracted item:
      1. Attempt exact ItemCode look-up (original behaviour).
      2. If code is missing/invalid, run fuzzy matching against the catalog.
      3. Compute a probabilistic confidence score.
      4. Consult the RL agent for its recommended action.
      5. Enrich the item record with all scoring metadata.
    """
    subset = df[df["Customercode"] == customer_code].copy()
    subset_indexed = subset.set_index("ItemCode")
    enriched = []

    for item in extracted:
        gemini_code = item.get("item_code")
        gemini_desc = item.get("description_german", "")
        ordered_pcs = item.get("ordered_pieces")

        # ── Step 1: exact code lookup ─────────────────────────────────────
        exact_hit = (
            gemini_code is not None
            and gemini_code in subset_indexed.index
        )

        if exact_hit:
            row        = subset_indexed.loc[gemini_code]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            matched_code = safe_str(gemini_code)
            matched_desc = safe_str(row.get("DescriptionGerman", ""))
            matched_unit = safe_str(row.get("UnitofMeasurement", ""))
            pc_per_unit  = safe_float(row.get("PCPerUnit"))
            is_blocked   = str(row.get("Blocked", "")).strip().lower() in ("yes","ja","1","true")
            best = {
                "item_code":     matched_code,
                "description":   matched_desc,
                "unit":          matched_unit,
                "pc_per_unit":   pc_per_unit,
                "blocked":       is_blocked,
                "fuzzy_score":   1.0,
                "trigram_score": 1.0,
                "combined":      1.0,
            }
        else:
            # ── Step 2: fuzzy matching ────────────────────────────────────
            query = gemini_desc or gemini_code or ""
            candidates = best_fuzzy_match(query, subset, top_n=5)
            best = candidates[0] if candidates else {
                "item_code": None, "description": gemini_desc,
                "unit": item.get("unit",""), "pc_per_unit": None,
                "blocked": False, "fuzzy_score": 0.0,
                "trigram_score": 0.0, "combined": 0.0,
            }
            matched_code = best["item_code"]
            matched_desc = best["description"]
            matched_unit = best["unit"]
            pc_per_unit  = best["pc_per_unit"]

        # ── Step 3: confidence score ──────────────────────────────────────
        confidence = compute_confidence(
            gemini_code=gemini_code,
            gemini_desc=gemini_desc,
            best_match=best,
            weights=rl.weights,
        )

        # ── Step 4: RL recommendation ─────────────────────────────────────
        rl_action = rl.best_action(confidence)

        # ── Step 5: final quantity ────────────────────────────────────────
        final_quantity = None
        if ordered_pcs is not None and pc_per_unit is not None:
            try:
                final_quantity = round(float(ordered_pcs) * float(pc_per_unit), 4)
            except (ValueError, TypeError):
                pass

        enriched.append({
            "item_code":          matched_code,
            "description":        matched_desc,
            "unit":               matched_unit,
            "ordered_pieces":     ordered_pcs,
            "pc_per_unit":        pc_per_unit,
            "final_quantity":     final_quantity,
            # ── Scoring metadata ──────────────────────────────────────────
            "gemini_code":        gemini_code,
            "gemini_desc":        gemini_desc,
            "confidence":         confidence,
            "fuzzy_score":        best["fuzzy_score"],
            "trigram_score":      best["trigram_score"],
            "match_method":       "exact_code" if exact_hit else "fuzzy",
            "rl_recommended":     rl_action,
            "needs_review":       confidence < CONFIDENCE_THRESHOLD,
        })

    return enriched


# ═════════════════════════════════════════════════════════════════════════════
# Section 6 – Feedback CLI (interactive or batch)
# ═════════════════════════════════════════════════════════════════════════════

def run_feedback_session(rl: RLMatcher):
    """
    Interactive CLI to provide RL feedback on previously extracted orders.

    Usage (run directly):
        python extract_ordersDEF.py --feedback
    """
    if not OUTPUT_FILE.exists():
        print("No orders_output.json found. Run extraction first.")
        return

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)

    print("\n═══════════════════════════════════════════════════════")
    print(" RL Feedback Session")
    print(" Press  a  to accept,  r  to reject,  s  to skip,  q  to quit")
    print("═══════════════════════════════════════════════════════\n")

    for order in results:
        cust, onum = order["customer_code"], order["order_number"]
        for item in order.get("items", []):
            if not item.get("needs_review") and item.get("confidence", 1.0) >= 0.80:
                continue   # skip high-confidence items unless you want full review
            print(f"  Order  : {cust}_{onum}")
            print(f"  Gemini : {item.get('gemini_code')} / {item.get('gemini_desc')}")
            print(f"  Matched: {item.get('item_code')} / {item.get('description')}")
            print(f"  Conf   : {item.get('confidence'):.3f}  (fuzzy={item.get('fuzzy_score'):.3f})")
            print(f"  Qty    : {item.get('ordered_pieces')} x {item.get('pc_per_unit')} = {item.get('final_quantity')}")
            print(f"  RL says: {item.get('rl_recommended')}")

            key = input("  [a/r/s/q] → ").strip().lower()
            if key == "q":
                print("\nFeedback session ended.")
                print(rl.summary())
                return
            elif key == "a":
                rl.accept_feedback(item.get("confidence", 0.5))
            elif key == "r":
                rl.reject_feedback(item.get("confidence", 0.5))
            else:
                print("  (skipped)")
            print()

    print("\nAll items reviewed.")
    print(rl.summary())


def apply_batch_feedback(
    rl: RLMatcher,
    feedback_list: list[dict],
):
    """
    Programmatic batch feedback.  Each entry:
      { "item_code": "X", "confidence": 0.6, "accepted": True }
    """
    for entry in feedback_list:
        conf     = float(entry.get("confidence", 0.5))
        accepted = bool(entry.get("accepted", True))
        if accepted:
            rl.accept_feedback(conf)
        else:
            rl.reject_feedback(conf)
    print(f"[RL] Applied {len(feedback_list)} batch feedback entries.")
    print(rl.summary())


# ═════════════════════════════════════════════════════════════════════════════
# Section 6.5 – Post-processing & Double-checking
# ═════════════════════════════════════════════════════════════════════════════

def postprocess_doublecheck(all_results: list[dict], data_dir: pathlib.Path):
    """
    Compares the extraction results from Gemini/Schablone mapping
    against the ground truth CSV files in the data directory and outputs
    a detailed evaluation report.
    """
    def safe_print(msg: str):
        try:
            print(msg)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "utf-8"
            safe_msg = msg.encode(encoding, errors="replace").decode(encoding)
            print(safe_msg)

    safe_print("\n" + "=" * 60)
    safe_print(" POST-PROCESSING & DOUBLE-CHECK REPORT (JSON vs Ground Truth CSV)")
    safe_print("=" * 60)
    
    total_gt_items = 0
    total_extracted_items = 0
    total_correct_codes = 0
    total_qty_matches = 0
    
    detailed_discrepancies = []
    
    for order in all_results:
        cust = order.get("customer_code")
        onum = order.get("order_number")
        items = order.get("items", [])
        
        csv_filename = f"{cust}_{onum}.csv"
        csv_path = data_dir / csv_filename
        
        if not csv_path.exists():
            csv_path = data_dir.parent / csv_filename
            
        if not csv_path.exists():
            safe_print(f"Order {cust}_{onum}: Ground truth CSV ({csv_filename}) not found. Skipping check.")
            continue
            
        # Parse ground truth CSV
        gt_items = {}
        try:
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 4:
                        item_code = parts[0].strip()
                        desc = parts[1].strip()
                        unit = parts[2].strip()
                        qty_str = parts[3].strip().replace(",", ".")
                        try:
                            qty = float(qty_str)
                        except ValueError:
                            qty = 0.0
                        gt_items[item_code] = {
                            "description": desc,
                            "unit": unit,
                            "quantity": qty
                        }
        except Exception as e:
            safe_print(f"Order {cust}_{onum}: Error reading ground truth CSV: {e}")
            continue
            
        safe_print(f"\nChecking Order {cust}_{onum} (GT has {len(gt_items)} items, Extraction has {len(items)} items):")
        
        extracted_codes = {}
        for it in items:
            code = it.get("item_code")
            final_qty = it.get("final_quantity")
            if final_qty is None:
                final_qty = it.get("ordered_pieces")  # fallback
            if final_qty is not None:
                try:
                    final_qty = float(final_qty)
                except ValueError:
                    final_qty = 0.0
            else:
                final_qty = 0.0
            
            if code:
                extracted_codes[code] = {
                    "final_quantity": final_qty,
                    "needs_review": it.get("needs_review", False),
                    "confidence": it.get("confidence", 0.0)
                }
                
        # Compare
        for code, gt in gt_items.items():
            total_gt_items += 1
            if code in extracted_codes:
                total_correct_codes += 1
                ext_qty = extracted_codes[code]["final_quantity"]
                gt_qty = gt["quantity"]
                if math.isclose(ext_qty, gt_qty, abs_tol=1e-4):
                    total_qty_matches += 1
                    safe_print(f"  [OK]  {code:8s}: Quantity matches ({gt_qty})")
                else:
                    qty_diff = ext_qty - gt_qty
                    detailed_discrepancies.append({
                        "order": f"{cust}_{onum}",
                        "item_code": code,
                        "type": "quantity_mismatch",
                        "gt_qty": gt_qty,
                        "ext_qty": ext_qty,
                        "diff": qty_diff
                    })
                    safe_print(f"  [QTY] {code:8s}: Qty mismatch! GT={gt_qty}, Extracted={ext_qty} (diff={qty_diff:+.2f})")
            else:
                detailed_discrepancies.append({
                    "order": f"{cust}_{onum}",
                    "item_code": code,
                    "type": "missing_item",
                    "gt_desc": gt["description"]
                })
                safe_print(f"  [MISS] {code:8s}: Missing in extracted items! GT desc: '{gt['description']}'")
                
        # Check for False Positives (extra items extracted that are not in GT)
        for code in extracted_codes:
            total_extracted_items += 1
            if code not in gt_items:
                detailed_discrepancies.append({
                    "order": f"{cust}_{onum}",
                    "item_code": code,
                    "type": "extra_item"
                })
                safe_print(f"  [EXTRA] {code:8s}: Extra item extracted! (Not in GT)")
                
    # Global Summary
    safe_print("\n" + "-" * 60)
    safe_print(" GLOBAL EVALUATION SUMMARY")
    safe_print("-" * 60)
    safe_print(f"Total Ground Truth Items Evaluated : {total_gt_items}")
    safe_print(f"Total Extracted Items              : {total_extracted_items}")
    safe_print(f"Correctly Matched Item Codes (TP)  : {total_correct_codes}")
    
    precision = total_correct_codes / total_extracted_items if total_extracted_items > 0 else 0.0
    recall = total_correct_codes / total_gt_items if total_gt_items > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    safe_print(f"Item Code Precision               : {precision:.2%}")
    safe_print(f"Item Code Recall (Match Rate)      : {recall:.2%}")
    safe_print(f"Item Code F1-Score                 : {f1:.2%}")
    if total_correct_codes > 0:
        safe_print(f"Perfect Quantity Matches           : {total_qty_matches} / {total_correct_codes} matches ({total_qty_matches / total_correct_codes:.2%})")
    else:
        safe_print(f"Perfect Quantity Matches           : 0 / 0 matches (0.00%)")
    
    if detailed_discrepancies:
        safe_print(f"\nTotal Discrepancies Found: {len(detailed_discrepancies)}")
    else:
        safe_print("\nPerfect Match! No discrepancies found between extraction results and ground truth.")
    safe_print("=" * 60 + "\n")


# ═════════════════════════════════════════════════════════════════════════════
# Section 7 – Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    # ── Check for --feedback flag ─────────────────────────────────────────────
    if "--feedback" in sys.argv:
        rl = RLMatcher(RL_FEEDBACK, DEFAULT_WEIGHTS)
        run_feedback_session(rl)
        return

    print("=" * 60)
    print("Order Extraction & Schablone Mapping (DEF + Fuzzy/RL)")
    print(f"Input folder : {DATA_DIR}")
    print(f"Output file  : {OUTPUT_FILE}")
    print("=" * 60)

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

    # 3. Load existing results for resuming
    all_results    = []
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

    processed_keys = {(r["customer_code"], r["order_number"]) for r in all_results}

    # 4. Initialise Gemini client
    if not HAS_GENAI:
        print("[ERROR] google-genai is required for extraction. Install it with:")
        print("         pip install google-genai")
        return
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 5. Initialise RL agent
    rl = RLMatcher(RL_FEEDBACK, DEFAULT_WEIGHTS)
    print(f"\n[RL] {rl.summary()}\n")

    # 6. Process each order group
    for i, order in enumerate(order_groups, 1):
        customer_code = order["customer_code"]
        order_number  = order["order_number"]
        key = (customer_code, order_number)

        if key in processed_keys:
            print(f"\n[{i}/{len(order_groups)}] Skipping {customer_code}_{order_number} (already processed)")
            continue

        print(f"\n[{i}/{len(order_groups)}] {customer_code}_{order_number}")

        schablone_ctx = build_schablone_context(schablone_df, customer_code)
        extracted     = extract_order_with_gemini(client, order, schablone_ctx)
        enriched      = enrich_with_schablone(extracted, schablone_df, customer_code, rl)

        source_files = [f["path"].name for f in order["files"]]
        result = {
            "source_files":  source_files,
            "customer_code": customer_code,
            "order_number":  order_number,
            "items":         enriched,
        }
        all_results.append(result)

        # Print summary
        for item in enriched:
            code   = item["item_code"] or "?"
            desc   = (item["description"] or "?")[:35]
            qty    = item["ordered_pieces"]
            final  = item["final_quantity"]
            unit   = item["unit"]
            conf   = item["confidence"]
            method = item["match_method"]
            review = " ⚠ REVIEW" if item["needs_review"] else ""
            print(f"    {code:8s}  {desc:35s}  {qty} → {final} {unit}  "
                  f"[conf={conf:.2f} {method}]{review}")

        # Write incrementally
        for dest in [OUTPUT_FILE, DATA_DIR / "orders_output.json"]:
            try:
                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error writing to {dest}: {e}")

    # 7. Postprocess and doublecheck the results against the ground truth CSV files
    postprocess_doublecheck(all_results, DATA_DIR)

    print(f"\n{'=' * 60}")
    print(f"[DONE] {len(all_results)} orders written to:")
    print(f"       {OUTPUT_FILE}")
    print(f"       {DATA_DIR / 'orders_output.json'}")
    print(f"\n[RL]  {rl.summary()}")
    print(f"\nTip:  Run   python {pathlib.Path(__file__).name} --feedback")
    print(f"      to start an interactive RL feedback session on uncertain matches.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

