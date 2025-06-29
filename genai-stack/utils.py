import requests
import logging
import fitz

logger = logging.getLogger(__name__)


def build_pdf_prompt(prompt_lines: list[str], page_streams: list[str]) -> str:
    for i, content in enumerate(page_streams, 1):
        prompt_lines.append(f"--- Page {i} ---\n{content}")

    return "\n\n".join(prompt_lines)


def call_llm_generate_streams(prompt: str, model: str, base_url: str, retries: int = 2) -> list[str]:
    for attempt in range(1, retries + 1):
        logger.info("🧠 LLM attempt %d/%d", attempt, retries)
        try:
            r = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False}
            )
            r.raise_for_status()
        except Exception as e:
            logger.error("🚨 LLM request failed: %s", e)
            continue

        response = r.json().get("response", "")

        logger.info("💬 Raw LLM response (first 500 chars):\n%s", response[:500].replace("\n", "\\n"))
        logger.debug("💬 Full LLM response:\n%s", response)

        if "```" in response:
            logger.warning("⚠️ Code block markers present in response. Skipping this attempt.")
            continue

        parts = [blk.strip() + "\nendstream" for blk in response.split("endstream") if blk.strip()]
        if len(parts) == 0:
            logger.warning("⚠️ No usable stream blocks found in LLM response.")
            continue

        logger.info("✅ LLM returned %d stream block(s)", len(parts))
        return parts

    raise RuntimeError("LLM failed to return valid PDF stream content after %d attempts." % retries)


def extract_pdf_content_streams(path: str) -> list[str]:
    logger.info("📂 Opening PDF for content stream extraction: %s", path)
    doc = fitz.open(path)
    content_streams = []

    for i in range(len(doc)):
        page = doc[i]
        logger.info("📃 Page %d", i + 1)
        xrefs = page.get_contents()
        if not xrefs:
            logger.warning("⚠️ No content streams found on page %d", i + 1)
            content_streams.append("% No content on this page")
            continue

        stream = b""
        for xref in xrefs:
            logger.debug("🔍 Reading stream xref %d", xref)
            stream += doc.xref_stream(xref)

        try:
            decoded = stream.decode("utf-8", errors="ignore")
            logger.info("📄 Extracted content (page %d):\n%s", i + 1, decoded[:1000]) # show only first ... characters
        except Exception as e:
            logger.warning("❗ Could not decode stream on page %d: %s", i + 1, e)
            decoded = "% Error decoding stream"

        content_streams.append(decoded)

    doc.close()
    logger.info("✅ Extracted %d stream(s)", len(content_streams))
    return content_streams

def build_full_pdf_from_streams(content_streams: list[str], output_path: str):
    N = len(content_streams)
    logger.info("📦 Assembling PDF with %d pages", N)

    pdf_bytes = "%PDF-1.4\n\n"
    pdf_bytes += "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n\n"
    kids = " ".join(f"{3 + i*3} 0 R" for i in range(N))
    pdf_bytes += f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {N} >>\nendobj\n\n"

    offsets = {}
    pos = len(pdf_bytes.encode("latin-1"))

    for i, stream in enumerate(content_streams):
        page_obj = 3 + i*3
        cont_obj = page_obj + 1
        font_obj = page_obj + 2

        offsets[page_obj] = pos
        pdf_bytes += (
            f"{page_obj} 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cont_obj} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>\n"
            "endobj\n\n"
        )
        pos = len(pdf_bytes.encode("latin-1"))

        offsets[cont_obj] = pos
        pdf_bytes += f"{cont_obj} 0 obj\n{stream}\n\n"
        pos = len(pdf_bytes.encode("latin-1"))

        offsets[font_obj] = pos
        pdf_bytes += (
            f"{font_obj} 0 obj\n"
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
            "endobj\n\n"
        )
        pos = len(pdf_bytes.encode("latin-1"))

    xref_start = pos
    total_objs = 1 + 1 + 3*N
    pdf_bytes += f"xref\n0 {total_objs+1}\n0000000000 65535 f \n"
    for obj in range(1, total_objs+1):
        off = offsets.get(obj, 0)
        pdf_bytes += f"{off:010d} 00000 n \n"

    pdf_bytes += (
        "trailer\n"
        f"<< /Size {total_objs+1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    )

    with open(output_path, "wb") as f:
        f.write(pdf_bytes.encode("latin-1"))
    logger.info("✅ PDF written to %s", output_path)

