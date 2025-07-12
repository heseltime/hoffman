#!/usr/bin/env python3
"""
extract_methods.py

Extract text from a PDF with multiple strategies and save each result
to a separate file whose name indicates the method.

Methods
-------
1. rendered  – visible text via pdfminer.six
2. streams   – raw content streams via PyMuPDF (fitz)

Usage
-----
    python extract_methods.py input.pdf [--outdir DIR]

Dependencies
------------
    pip install pdfminer.six pymupdf
"""

import argparse
import logging
from pathlib import Path
from typing import List

from pdfminer.high_level import extract_text as pdfminer_extract_text
import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Extraction methods
# ------------------------------------------------------------------
def extract_pdf_text(path: Path) -> str:
    """Visible text extracted by pdfminer.six."""
    try:
        return pdfminer_extract_text(str(path))
    except Exception as exc:
        log.error("pdfminer failed on %s: %s", path, exc)
        return ""


def extract_pdf_content_streams(
    path: Path,
    *,
    limit_lines: bool = False,
    max_lines: int = 1000,
) -> List[str]:
    """Raw uncompressed content streams (one per page) using PyMuPDF."""
    doc = fitz.open(path)
    streams: List[str] = []
    for page_idx, page in enumerate(doc):
        xrefs = page.get_contents()
        if not xrefs:
            log.warning("No content stream on page %d", page_idx + 1)
            streams.append("% No content")
            continue
        raw_stream = b"".join(doc.xref_stream(x) for x in xrefs)
        decoded = raw_stream.decode("utf-8", errors="ignore")
        if limit_lines:
            decoded = "\n".join(decoded.splitlines()[:max_lines])
        streams.append(decoded)
    return streams


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF text using multiple methods."
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file")
    parser.add_argument(
        "--outdir", type=Path, default=Path("."), help="Output directory"
    )
    args = parser.parse_args()

    pdf_path = args.pdf
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    stem = pdf_path.stem

    # --- Method 1: rendered text ---
    rendered_text = extract_pdf_text(pdf_path)
    rendered_file = outdir / f"{stem}_rendered.txt"
    rendered_file.write_text(rendered_text, encoding="utf-8")
    log.info(
        "Saved rendered text to %s (%d chars)", rendered_file.name, len(rendered_text)
    )

    # --- Method 2: raw streams ---
    streams = extract_pdf_content_streams(pdf_path)
    streams_text = "\n\n%% --- PAGE BREAK --- %%\n\n".join(streams)
    streams_file = outdir / f"{stem}_streams.txt"
    streams_file.write_text(streams_text, encoding="utf-8")
    log.info("Saved raw streams to %s (%d chars)", streams_file.name, len(streams_text))


if __name__ == "__main__":  # pragma: no cover
    main()
