from __future__ import annotations

import os
from typing import Optional

from .sample_data import DEMO_TEXT
from .schemas import ExtractedItem, ExtractedOrder


EXTRACTION_PROMPT = """You extract food-wholesale orders for an ERP workflow.

Return only structured JSON matching the requested schema. Do not invent article
codes. Extract raw item phrases, quantities, unit hints, customer hints, and
delivery notes. Preserve uncertainty in the raw_text or notes fields.
"""


def parse_order_json(raw_json: str) -> ExtractedOrder:
    if hasattr(ExtractedOrder, "model_validate_json"):
        return ExtractedOrder.model_validate_json(raw_json)
    return ExtractedOrder.parse_raw(raw_json)


def demo_extraction(text: Optional[str] = None) -> ExtractedOrder:
    raw_text = text.strip() if text and text.strip() else DEMO_TEXT
    return ExtractedOrder(
        customer_hint=None,
        delivery_note="morgen liefern" if "morgen" in raw_text.lower() else None,
        raw_text=raw_text,
        items=[
            ExtractedItem(raw_text="Mango puree", quantity=1, unit_hint="BEG"),
            ExtractedItem(raw_text="Sonnenblumenoel Big Chef", quantity=2, unit_hint="KAN"),
            ExtractedItem(raw_text="180er Eier L", quantity=4, unit_hint="KRT"),
        ],
    )


class GeminiOrderExtractor:
    def __init__(self) -> None:
        self.model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    @property
    def live_enabled(self) -> bool:
        return bool(self.api_key)

    def extract(
        self,
        *,
        text: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> ExtractedOrder:
        if not self.live_enabled:
            return demo_extraction(text)

        from google import genai
        from google.genai import types

        client = genai.Client()
        contents = []

        if file_bytes and mime_type:
            contents.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))

        text_part = EXTRACTION_PROMPT
        if text and text.strip():
            text_part += f"\n\nAdditional text from the user:\n{text.strip()}"
        contents.append(text_part)

        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ExtractedOrder,
            ),
        )

        return parse_order_json(response.text)
