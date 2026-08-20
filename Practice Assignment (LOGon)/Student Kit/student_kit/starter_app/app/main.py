from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .gemini_pipeline import GeminiOrderExtractor
from .matching import match_order
from .schemas import ExtractResponse, FeedbackPayload


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = APP_ROOT / "frontend"

app = FastAPI(title="Gemini Order Capture Starter")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = GeminiOrderExtractor()


def model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "live_gemini": extractor.live_enabled,
        "model": extractor.model,
    }


@app.post("/api/extract", response_model=ExtractResponse)
async def extract_order(
    customer_code: str = Form(default="CUST-DEMO"),
    text: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
) -> ExtractResponse:
    file_bytes = None
    mime_type = None

    if file is not None and file.filename:
        file_bytes = await file.read()
        mime_type = file.content_type or "application/octet-stream"

    if not text and not file_bytes and extractor.live_enabled:
        raise HTTPException(status_code=400, detail="Provide text or upload a file.")

    extracted = extractor.extract(text=text, file_bytes=file_bytes, mime_type=mime_type)
    threshold = int(os.getenv("MATCH_THRESHOLD", "85"))
    matched = match_order(extracted, customer_code=customer_code, threshold=threshold)

    return ExtractResponse(
        live_gemini=extractor.live_enabled,
        model=extractor.model,
        customer_code=customer_code,
        extracted=extracted,
        matched=matched,
    )


@app.post("/api/feedback")
async def save_feedback(payload: FeedbackPayload) -> JSONResponse:
    feedback_path = APP_ROOT / os.getenv("FEEDBACK_PATH", "feedback.jsonl")
    record = model_dump(payload)
    record["received_at"] = datetime.now(timezone.utc).isoformat()

    with feedback_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    return JSONResponse({"ok": True, "path": str(feedback_path)})


app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
