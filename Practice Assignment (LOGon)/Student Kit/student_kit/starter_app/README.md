# Starter App: Gemini Order Capture

This is a small reference prototype for the LOGon/Foppa order-capture project. It uses FastAPI and a static frontend because that keeps the example easy to run and inspect.

FastAPI is not required for student submissions. Teams may replace it with Flask, Node/TypeScript, a notebook, a CLI, or another stack if they preserve the same pipeline responsibilities.

It demonstrates:

- text and file upload endpoint, with PDFs as the intended baseline input;
- optional live Gemini extraction using the Google Gen AI SDK;
- schema-shaped extracted orders;
- customer-template matching;
- fallback catalog search;
- review UI;
- feedback capture.

If `GEMINI_API_KEY` is not set, the app runs in demo mode and returns a sample extraction. This lets students explore the pipeline before configuring Google credentials.

The schema layer is conceptually required, but Pydantic itself is not. Equivalent choices include JSON Schema, Zod, TypeBox, or framework-native validation.

## Setup

```bash
cd student_kit/starter_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Optional live Gemini mode:

```bash
export GEMINI_API_KEY="your-key"
export GEMINI_MODEL="gemini-3-flash-preview"
```

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

Run tests:

```bash
pytest
```

## API

`POST /api/extract`

Form fields:

- `customer_code`: default `CUST-DEMO`
- `text`: optional order text for debugging
- `file`: PDF or scanned document file

`POST /api/feedback`

Stores finalized review data in `feedback.jsonl`.

## Student Exercises

1. Add a new product synonym and prove it with a test.
2. Add PDF-specific prompt instructions for page layout and table extraction.
3. Store feedback in SQLite or DuckDB.
4. Add a confidence threshold control to the frontend.
5. Replace fuzzy scoring with embeddings or a hybrid score.
