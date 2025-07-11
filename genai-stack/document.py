"""
 FastAPI service that upgrades uploaded PDFs to an accessible / barrier-free version
 using an LLM – refactored to reuse the utility functions that were built in the
 Jupyter notebook so that there is only one implementation of the PDF pipeline.

 Major changes compared with the original PoC:
   • Consolidated all helper functions (uncompress, extract streams, prompt building,
     LLM call, PDF rebuild, etc.) into this file so that both a notebook and the
     API share identical logic.
   • Added support for example PDF pairs so the prompt can include few-shot
     examples (directory configured via $EXAMPLE_DIR).
   • Added optional LIMIT_LINES / LINES_LIMIT environment flags to trim very long
     streams during prompt construction to stay within context windows.
   • Uncompresses PDFs with qpdf prior to text extraction to improve reliability.
   • Uses retry logic from the notebook (MAX_RETRIES_LLM_LOOP_DEFAULT) instead of
     the hard-coded 2 retries.
   • More robust logging and explicit error handling.
 """

from __future__ import annotations

import os
import json
import uuid
import logging
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List

import fitz  # PyMuPDF
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Configuration & logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
load_dotenv(".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_NAME = os.getenv("LLM", "llama3")

MAX_RETRIES_LLM_LOOP_DEFAULT = int(os.getenv("MAX_RETRIES_LLM_LOOP_DEFAULT", "5"))
LIMIT_LINES = os.getenv("LIMIT_LINES", "False").lower() == "true"
LINES_LIMIT = int(os.getenv("LINES_LIMIT", "1000"))
EXAMPLE_DIR = Path(os.getenv("EXAMPLE_DIR", "./examples"))

LLM_HTTP_TIMEOUT = int(os.getenv("LLM_HTTP_TIMEOUT", "300")) # 5 min default

logger.info("🤖 Using LLM model: %s", LLM_NAME)
logger.info("🔧 LIMIT_LINES=%s, LINES_LIMIT=%d", LIMIT_LINES, LINES_LIMIT)
logger.info("📂 Looking for example PDFs in: %s", EXAMPLE_DIR.resolve())

# ---------------------------------------------------------------------------
#   Helper functions (taken from the notebook so both code paths match)
# ---------------------------------------------------------------------------

def _run_or_copy(cmd: List[str], src: Path, dst: Path) -> None:
    """Run qpdf or, if it's not available, just copy the file (best‑effort fallback)."""
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        logger.warning("qpdf not found – continuing with original PDF (streams may stay compressed).")
        dst.write_bytes(src.read_bytes())
    except subprocess.CalledProcessError as e:
        logger.warning("qpdf failed (%s) – continuing with original PDF.", e)
        dst.write_bytes(src.read_bytes())


def uncompress_pdf(input_pdf_path: Path, output_pdf_path: Path) -> None:
    logger.info("🔓 Uncompressing PDF: %s", input_pdf_path)
    _run_or_copy([
        "qpdf", "--qdf", "--object-streams=disable", str(input_pdf_path), str(output_pdf_path)
    ], input_pdf_path, output_pdf_path)


def extract_pdf_content_streams(path: str, *, limit_lines: bool = False, max_lines: int = 1000) -> List[str]:
    logger.info("📂 Extracting content streams from: %s", path)
    doc = fitz.open(path)
    streams: List[str] = []
    for page_idx, page in enumerate(doc):
        xrefs = page.get_contents()
        if not xrefs:
            logger.warning("⚠️  No content stream on page %d", page_idx + 1)
            streams.append("% No content")
            continue
        raw_stream = b"".join(doc.xref_stream(x) for x in xrefs)
        decoded = raw_stream.decode("utf-8", errors="ignore")
        if limit_lines:
            decoded = "\n".join(decoded.splitlines()[:max_lines])
        streams.append(decoded)
    logger.info("✅ Extracted %d stream(s)", len(streams))
    return streams


def build_prompt_with_examples(
    example_pairs: List[tuple[str, str]],
    target_streams: List[str],
    *,
    limit_lines: bool = False,
    max_lines: int = 1000,
) -> str:
    header = [
        "You are a low-level PDF code generator.",
        "Given raw PDF page content streams (e.g., BT/ET blocks), rewrite each stream for accessibility.",
        "Only return the improved PDF stream – no explanation, no markdown, no commentary.",
        "Each input stream will be followed by your output stream.",
        "Here are some examples:"  # few-shot examples inline
    ]
    prompt = "\n".join(header)

    for idx, (non_bf, bf) in enumerate(example_pairs, start=1):
        def _trim(s: str) -> str:
            return "\n".join(s.strip().splitlines()[:max_lines]) if limit_lines else s.strip()
        prompt += f"\n\n% Example {idx}:\nInput:\n{_trim(non_bf)}\nOutput:\n{_trim(bf)}"

    prompt += "\n\nNow improve the following:"
    for stream in target_streams:
        block = "\n".join(stream.strip().splitlines()[:max_lines]) if limit_lines else stream.strip()
        prompt += f"\n\n{block}"
    return prompt


def call_llm_generate_streams(
    prompt: str,
    *,
    model: str,
    base_url: str,
    retries: int = 2,
) -> List[str]:
    logger.info("🚀 Calling LLM '%s' (%s)", model, base_url)
    for attempt in range(1, retries + 1):
        logger.info("🧠 Attempt %d/%d", attempt, retries)
        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=LLM_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("❌ LLM request failed: %s", exc)
            continue

        answer = resp.json().get("response", "")
        if "```" in answer:
            logger.warning("⚠️  Code fences detected – skipping response.")
            continue

        parts = [blk.strip() + "\nendstream" for blk in answer.split("endstream") if blk.strip()]
        if parts:
            logger.info("✅ Parsed %d stream blocks from LLM", len(parts))
            return parts
        logger.warning("⚠️  No usable stream blocks – retrying…")

    raise RuntimeError("LLM failed to produce valid stream content in allotted retries.")


def build_full_pdf_from_streams(
    streams: List[str],
    output_path: str,
    *,
    limit_lines: bool = False,
    max_lines: int = 1000,
) -> None:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for s in streams:
        pdf.add_page()
        lines = s.splitlines()
        if limit_lines:
            lines = lines[:max_lines]
        for line in lines:
            pdf.cell(0, 10, line[:100], ln=True)
    pdf.output(output_path)
    logger.info("📄 Accessible PDF written to: %s", output_path)


def collect_example_pairs(
    directory: Path,
    *,
    max_pages: int = 1,
    limit_lines: bool = False,
    max_lines: int = 1000,
) -> List[tuple[str, str]]:
    """Searches for files matching "* bf.pdf" as accessible versions next to their originals."""
    pairs: List[tuple[str, str]] = []
    if not directory.exists():
        logger.warning("No example directory found – continuing without few-shot examples.")
        return pairs

    tmp_dir = Path("/tmp/pdf_examples")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    for bf_path in directory.glob("* bf.pdf"):
        orig_path = directory / bf_path.name.replace(" bf.pdf", ".pdf")
        if not orig_path.exists():
            continue
        logger.info("📚 Example pair: %s + %s", orig_path.name, bf_path.name)

        # Uncompress both for easier stream comparison
        orig_u = tmp_dir / f"{orig_path.stem}_u.pdf"
        bf_u = tmp_dir / f"{bf_path.stem}_u.pdf"
        uncompress_pdf(orig_path, orig_u)
        uncompress_pdf(bf_path, bf_u)

        orig_streams = extract_pdf_content_streams(str(orig_u), limit_lines=limit_lines, max_lines=max_lines)[:max_pages]
        bf_streams = extract_pdf_content_streams(str(bf_u), limit_lines=limit_lines, max_lines=max_lines)[:max_pages]
        pairs.extend(zip(orig_streams, bf_streams))
    logger.info("🧾 Loaded %d example stream pairs", len(pairs))
    return pairs

# ---------------------------------------------------------------------------
#   FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load few-shot examples once at startup (cold-start optimisation)
EXAMPLE_PAIRS: List[tuple[str, str]] = collect_example_pairs(
    EXAMPLE_DIR,
    limit_lines=LIMIT_LINES,
    max_lines=LINES_LIMIT,
)


@app.post("/accessible-document-version")
async def accessible_document_version(
    file: UploadFile = File(...),
    metadata: str | None = Form(None),  # kept for compatibility – currently unused
    max_retries: int | None = Query(None, alias="max_retries_param"),
):
    """Return an accessible PDF generated via LLM few-shot prompting."""
    try:
        logger.info("📥 Received PDF: %s", file.filename)
        # ------------------------------------------------------------------
        # 1) Persist (and optionally uncompress later) the incoming PDF
        # ------------------------------------------------------------------
        with TemporaryDirectory() as tmpdir:
            uploaded_path = Path(tmpdir) / f"{uuid.uuid4()}_{file.filename}"

            # read exactly once so we can measure size too
            raw_bytes = await file.read()
            uploaded_path.write_bytes(raw_bytes)
            size_bytes = len(raw_bytes)

            logger.info(
                "💾 Stored upload at: %s (%d bytes)",
                uploaded_path, size_bytes
            )

            # Guard: reject empty uploads early
            if size_bytes == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded PDF is empty (0 bytes)."
                )

            uncompressed_path = uploaded_path.with_name(
                f"{uploaded_path.stem}_u{uploaded_path.suffix}"
            )
            uncompress_pdf(uploaded_path, uncompressed_path)

            # ------------------------------------------------------------------
            # 2) Extract low‑level content streams
            # ------------------------------------------------------------------
            streams = extract_pdf_content_streams(
                str(uncompressed_path),
                limit_lines=LIMIT_LINES,
                max_lines=LINES_LIMIT,
            )

            # ------------------------------------------------------------------
            # 3) Build prompt
            # ------------------------------------------------------------------
            prompt = build_prompt_with_examples(
                EXAMPLE_PAIRS,
                streams,
                limit_lines=LIMIT_LINES,
                max_lines=LINES_LIMIT,
            )

            # Optional: save prompt for debugging
            prompt_debug_path = Path(tmpdir) / "prompt.txt"
            prompt_debug_path.write_text(prompt, encoding="utf-8")
            logger.debug("📝 Prompt saved to %s (size=%d)", prompt_debug_path, prompt_debug_path.stat().st_size)

            # ------------------------------------------------------------------
            # 4) Call LLM
            # ------------------------------------------------------------------
            retries = max_retries or MAX_RETRIES_LLM_LOOP_DEFAULT
            improved_streams = call_llm_generate_streams(
                prompt,
                model=LLM_NAME,
                base_url=OLLAMA_BASE_URL,
                retries=retries,
            )

            # ------------------------------------------------------------------
            # 5) Build accessible PDF
            # ------------------------------------------------------------------
            accessible_path = Path(tmpdir) / f"accessible_{file.filename}"
            build_full_pdf_from_streams(
                improved_streams,
                str(accessible_path),
                limit_lines=LIMIT_LINES,
                max_lines=LINES_LIMIT,
            )

            logger.info("📤 Returning accessible PDF (%d bytes)", accessible_path.stat().st_size)
            return StreamingResponse(
                open(accessible_path, "rb"),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="accessible_{file.filename}"'
                },
            )
    except Exception as exc:
        logger.exception("🔥 Error while processing PDF: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc), "status": "failure"})


# ---------------------------------------------------------------------------
#   Local dev convenience
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "accessible_document_api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
