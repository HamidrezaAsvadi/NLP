# Introduction to the Google Gen AI SDK

The current recommended library for Gemini API work is the Google Gen AI SDK. Google documents Python, JavaScript/TypeScript, Go, Java, and C# SDKs, with Python and JavaScript being the best fit for this course prototype.

## Install

Python:

```bash
pip install -U google-genai
```

JavaScript/TypeScript:

```bash
npm install @google/genai
```

Set the API key in your shell:

```bash
export GEMINI_API_KEY="your-key"
```

Do not commit API keys. Do not put a Gemini API key directly in browser code.

## First Python Request

```python
from google import genai

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Explain fuzzy matching for product names in two sentences.",
)

print(response.text)
```

The official quickstart currently uses `gemini-3-flash-preview` for first examples. For more conservative deployments, students may use `gemini-2.5-flash` if preview-model availability or quota becomes an issue.

## First JavaScript Request

```js
import { GoogleGenAI } from "@google/genai";

const ai = new GoogleGenAI({});

const response = await ai.models.generateContent({
  model: "gemini-3-flash-preview",
  contents: "Explain fuzzy matching for product names in two sentences.",
});

console.log(response.text);
```

## Structured JSON Output

For this project, the model should not return prose. It should return JSON that matches a schema.

Python example:

```python
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class OrderItem(BaseModel):
    raw_text: str = Field(description="The item phrase found in the input.")
    quantity: float | None = Field(default=None)
    unit_hint: str | None = Field(default=None)

class ExtractedOrder(BaseModel):
    customer_hint: str | None = None
    delivery_note: str | None = None
    items: list[OrderItem]

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Extract the order: 2 cans Sonnenblumenoel Big Chef, 4 boxes eggs L, deliver tomorrow",
    config=types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        response_schema=ExtractedOrder,
    ),
)

order = ExtractedOrder.model_validate_json(response.text)
print(order)
```

Note: If structured output / schema binding fails with a specific model version, fall back to JSON mode (`response_mime_type="application/json"`) and validate the response locally with Pydantic.

## Multimodal Input

Gemini can accept text, images, PDFs, audio, and video. For this course project, start with PDF or scanned-document input:

- use PDF input for scanned forms or exported order sheets.
- use image input only when the source document is provided as a photo or scan.
- treat audio as an optional extension, not the baseline task.

Small local PDF example:

```python
from google import genai
from google.genai import types
from pathlib import Path

client = genai.Client()
pdf_bytes = Path("order.pdf").read_bytes()

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        "Extract all order lines as JSON with raw text, quantity, and unit hints.",
    ],
)

print(response.text)
```

For larger files or repeated use, prefer the Files API. Google recommends using the Files API when the total request is larger than 20 MB.

## Pipeline Pattern for This Project

Use Gemini for extraction and reasoning, but keep business validation in normal code:

1. Gemini extracts raw order candidates from a PDF or scanned document.
2. Python or TypeScript validates the JSON schema.
3. Matching code compares the extracted item text to customer history and the full catalog.
4. The app exposes confidence, alternatives, and explanations to a human reviewer.
5. The final corrected order is stored as feedback.

This separation matters. The model is strong at interpreting messy inputs, but deterministic code should decide whether an order is complete enough to send to ERP.

## Sources

- Google Gemini API quickstart: https://ai.google.dev/gemini-api/docs/quickstart
- Google Gen AI Python SDK: https://googleapis.github.io/python-genai/
- Gemini structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini Files API: https://ai.google.dev/gemini-api/docs/files
- Gemini image understanding: https://ai.google.dev/gemini-api/docs/image-understanding
- Gemini audio understanding: https://ai.google.dev/gemini-api/docs/audio
