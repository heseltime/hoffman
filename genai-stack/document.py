import os
import json
import uuid
import fitz
import requests
import logging

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from dotenv import load_dotenv
from utils import build_pdf_prompt, call_llm_generate_streams, extract_pdf_content_streams, build_full_pdf_from_streams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(".env")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
LLM_NAME = os.getenv("LLM")

@app.post("/accessible-document-version")
async def accessible_document_version(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    max_retries_param: int = Query(None)
):
    try:
        logger.info("📥 Received request at /accessible-document-version")
        temp_path = f"/tmp/{uuid.uuid4()}.pdf"
        with open(temp_path, "wb") as f:
            raw_bytes = await file.read()
            f.write(raw_bytes)
        logger.info("📄 Saved uploaded PDF to: %s (%d bytes)", temp_path, len(raw_bytes))

        logger.info("🔍 Extracting PDF content streams...")
        content_streams = extract_pdf_content_streams(temp_path)
        logger.info("📄 Extracted %d content stream(s)", len(content_streams))

        logger.info("🧾 Building LLM prompt")

        prompt_lines = [
            "You are a PDF cleaner. Your task is to rewrite PDF content streams for accessibility.",
            "Each input is a low-level PDF page content stream (BT/ET block).",
            "For each stream, return an improved version using Helvetica font, 12pt size, and correctly positioned text.",
            "Ensure the syntax remains valid PDF content streams with BT/ET blocks.",
            "Respond only with updated PDF streams — no explanation or formatting.",
            "Each stream must be returned between `<< /Length L >>` and `endstream`, where L is the byte length of the stream body.",
            "Do not wrap the response in code fences or markdown."
        ]

        prompt = build_pdf_prompt(prompt_lines, content_streams)
        logger.debug("📨 Prompt preview:\n%s", prompt[:500])

        retries = max_retries_param or 2
        logger.info("🔁 Calling LLM with up to %d retries", retries)
        improved_streams = call_llm_generate_streams(
            prompt, model=LLM_NAME, base_url=OLLAMA_BASE_URL, retries=retries
        )
        logger.info("✅ LLM returned %d improved stream(s)", len(improved_streams))

        output_path = f"/tmp/genai_{uuid.uuid4()}.pdf"
        logger.info("🛠️  Building PDF to: %s", output_path)
        build_full_pdf_from_streams(improved_streams, output_path)

        logger.info("📤 Returning PDF response")
        return StreamingResponse(
            open(output_path, "rb"),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="accessible_{file.filename}"'}
        )

    except Exception as e:
        logger.exception("🔥 Error in /accessible-document-version")
        return JSONResponse(status_code=500, content={"error": str(e), "status": "failure"})
    