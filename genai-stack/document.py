import os
import base64
import pycurl
import json
from io import BytesIO
import io
from urllib.parse import urlencode

import traceback
import uuid
import requests

import streamlit as st
from langchain.chains import RetrievalQA
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.callbacks.base import BaseCallbackHandler
from langchain.vectorstores.neo4j_vector import Neo4jVector

#from langchain.document_loaders import UnstructuredPDFLoader
import fitz  # PyMuPDF test with structural object code

from streamlit.logger import get_logger
from chains import (
    load_embedding_model,
    load_llm,
)
from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

import tempfile

from docling.document_converter import DocumentConverter

from dotenv import load_dotenv

load_dotenv(".env")

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
llm_name = os.getenv("LLM")
llm_vision_name = os.getenv("LLM_VISION")
os.environ["NEO4J_URL"] = url

language = os.getenv("SUMMARY_LANGUAGE")
summary_size = os.getenv("SUMMARY_SIZE")
tags_number = os.getenv("TAGS_NUMBER")

# A11y
MAX_RETRIES_LLM_LOOP_DEFAULT = os.getenv("MAX_RETRIES_LLM_LOOP_DEFAULT")

logger = get_logger(__name__)

embeddings, dimension = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger
)

class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)


llm = load_llm(llm_name, logger=logger, config={"ollama_base_url": ollama_base_url})

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def getQa(file: UploadFile):
    pdf_reader = PdfReader(file.file)

    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len
    )

    chunks = text_splitter.split_text(text=text)

    vector_store = Neo4jVector.from_texts(
        chunks,
        url=url,
        username=username,
        password=password,
        embedding=embeddings,
        index_name="pdf_bot",
        node_label="PdfBotChunk",
        pre_delete_collection=True,
    )
    qa = RetrievalQA.from_chain_type(
        llm=llm, chain_type="stuff", retriever=vector_store.as_retriever()
    )
    return qa

@app.post("/describe")
async def describe(image: UploadFile):

    contents = await image.read()
    img_base64 = base64.b64encode(contents).decode("utf-8")

    prompt = """You are an assistant tasked with summarizing images for retrieval. \
    These summaries will be embedded and used to retrieve the raw image. \
    Give a concise summary of the image that is well optimized for retrieval."""

    buffer = BytesIO()
    curl = pycurl.Curl()
    curl.setopt(pycurl.URL, ollama_base_url + "/api/generate")
    curl.setopt(pycurl.WRITEDATA, buffer)
    post_data = {"model": "" + llm_vision_name + "", 
                 "prompt": "" + prompt + "",
                 "stream": False,
                 "images": ["" + img_base64 + ""]}
    postfields = json.dumps(post_data)
    curl.setopt(pycurl.POST, True)
    curl.setopt(pycurl.POSTFIELDS, postfields)
    curl.perform()
    curl.close()
    response = json.loads(buffer.getvalue().decode("utf-8"))
    return { "description": response["response"], "model": llm_vision_name }

@app.post("/classify")
async def classify(file: UploadFile, termList: str):

    qa = getQa(file)
    stream_handler = StreamHandler(st.empty())

    term_query = ("Pick one of the following list of categories: " + termList + ". " +
              "Write the answer only in " + language + " language. " + 
              "Don't add any explanation for the choice in the answer. " + 
              "Don't add any note after the word in the answer. " +
              "Don't add any space before the word in the answer. " +
              "Don't add in the answer the translation of the word in a different language after chosen word. " +
              "Give the answer exactly as a single word from the list.")

    term = qa.run(term_query, callbacks=[stream_handler])
    return {"term": term, "model": llm_name}

@app.post("/prompt")
async def prompt(file: UploadFile, prompt: str):

    qa = getQa(file)
    stream_handler = StreamHandler(st.empty())

    prompt = (prompt + 
              ". Write the answer only in " + language + " language. " + 
              "Don't add any translation to the answer.")

    answer = qa.run(prompt, callbacks=[stream_handler])
    return {"answer": answer, "model": llm_name}

@app.post("/summary")
async def summary(file: UploadFile):

    qa = getQa(file)
    stream_handler = StreamHandler(st.empty())

    summary_query = "Write a short summary of the text in " + summary_size + " words only in " + language
    summary_result = qa.run(summary_query, callbacks=[stream_handler])

    tags_query = ("Provide " + tags_number + " words to categorize the document in language " + language + " in a single line. " +
                 "Use only language " + language + " for these " + tags_number + " words in the answer. " +
                 "Don't add any explanation for the words in the answer. " + 
                 "Don't add any note after the list of words in the answer. " +
                 "Don't use bullets or numbers to list the words in the answer. " +
                 "Don't add in the answer the translation of the words in a different language after the list of words. " +
                 "Give the answer exactly as a list of " + tags_number + " words in language " + language + " separated with comma and without ending dot.")
    tags_result = qa.run(tags_query, callbacks=[stream_handler])

    return {"summary": summary_result, "tags": tags_result, "model": llm_name}

# Define the DocumentConverter
converter = DocumentConverter()

@app.post("/jsonify")
async def jsonify(file: UploadFile):
    """
    Endpoint to process an uploaded PDF file and output JSON format.
    """
    try:
        # Save the uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(await file.read())

        # Convert the document using Docling
        result = converter.convert(temp_file_path)

        # Export the result to a JSON-compatible dictionary
        json_output = result.document.export_to_dict()

        # Clean up temporary file
        os.remove(temp_file_path)

        # Return JSON output
        return {"document": json_output, "status": "success"}

    except Exception as e:
        return {"error": str(e), "status": "failure"}

def is_valid_pdf(path: str) -> (bool, str):
    try:
        reader = PdfReader(path)
        _ = reader.metadata
        _ = len(reader.pages)
        return True, "Valid PDF"
    except Exception as e:
        return False, str(e)

def repair_pdf_with_pymupdf(input_path: str, output_path: str) -> bool:
    try:
        logger.info("🔧 Repair via PyMuPDF: %s → %s", input_path, output_path)
        doc = fitz.open(input_path)
        if doc.page_count == 0:
            logger.warning("⚠️ Cannot repair: zero pages")
            doc.close()
            return False
        new_doc = fitz.open()
        for i in range(doc.page_count):
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
        new_doc.save(output_path)
        new_doc.close()
        doc.close()
        logger.info("✅ Repair successful, pages: %d", doc.page_count)
        return True
    except Exception as e:
        logger.error("❌ PyMuPDF repair failed: %s", e)
        return False

def build_full_pdf_from_streams(content_streams: list[str], output_path: str):
    N = len(content_streams)
    logger.info("📦 Assembling PDF with %d pages", N)

    # Header + Catalog + Pages
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

        # Page object
        offsets[page_obj] = pos
        entry = (
            f"{page_obj} 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cont_obj} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>\n"
            "endobj\n\n"
        )
        pdf_bytes += entry
        pos = len(pdf_bytes.encode("latin-1"))

        # Content stream
        offsets[cont_obj] = pos
        pdf_bytes += f"{cont_obj} 0 obj\n{stream}\n\n"
        pos = len(pdf_bytes.encode("latin-1"))

        # Font object
        offsets[font_obj] = pos
        font_entry = (
            f"{font_obj} 0 obj\n"
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
            "endobj\n\n"
        )
        pdf_bytes += font_entry
        pos = len(pdf_bytes.encode("latin-1"))

    # Build xref
    xref_start = pos
    total_objs = 1 + 1 + 3*N
    pdf_bytes += f"xref\n0 {total_objs+1}\n"
    pdf_bytes += "0000000000 65535 f \n"
    for obj in range(1, total_objs+1):
        off = offsets.get(obj, 0)
        pdf_bytes += f"{off:010d} 00000 n \n"

    # Trailer
    pdf_bytes += (
        "trailer\n"
        f"<< /Size {total_objs+1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n"
        "%%EOF\n"
    )

    with open(output_path, "wb") as f:
        f.write(pdf_bytes.encode("latin-1"))
    logger.info("📄 PDF assembly complete: %s", output_path)


@app.post("/accessible-document-version")
async def accessible_document_version_flexible(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    max_retries_param: int = Query(None)
):
    try:
        logger.info("📥 Received request at /accessible-document-version")

        # 1. Validate upload
        if file.content_type != "application/pdf":
            logger.error("❌ Invalid content type: %s", file.content_type)
            raise ValueError(f"Invalid content type: {file.content_type}")
        raw_bytes = await file.read()
        if not raw_bytes:
            logger.error("❌ Uploaded file empty")
            raise ValueError("Uploaded file is empty")

        # 2. Parse A11y metadata
        a11y_data = json.loads(metadata)
        logger.info("📊 Parsed metadata keys: %s", list(a11y_data.keys()))
        max_retries = max_retries_param or a11y_data.get("maxRetries", 2)
        logger.info("🔁 Will retry LLM up to %d times", max_retries)

        # 3. Extract page texts
        tmp_in = f"/tmp/orig_{uuid.uuid4()}.pdf"
        with open(tmp_in, "wb") as f:
            f.write(raw_bytes)
        doc = fitz.open(tmp_in)
        page_texts = [doc.load_page(i).get_text("text") for i in range(doc.page_count)]
        doc.close()
        logger.info("📄 Extracted text for %d pages", len(page_texts))

        # 4. Build a super-strict prompt with concrete example
        N = len(page_texts)
        example = (
            "<< /Length 44 >>\n"
            "stream\n"
            "BT\n"
            "/F1 12 Tf\n"
            "72 720 Td\n"
            "(Hello, world!) Tj\n"
            "ET\n"
            "endstream\n\n"
        )
        prompt = (
            "You are a finite-state PDF generator. Do not output any code or explanation—"
            "only raw PDF tokens.\n\n"
            "Example of one content-stream object (literal PDF syntax):\n\n"
            f"{example}"
            "Now, produce exactly "
            f"{N} such blocks in this exact format for the page texts below.\n"
            "Each block must:\n"
            "  1. Start with `<< /Length L >>` where L is the byte length of the stream body.\n"
            "  2. Contain `BT`, font-setting, text-positioning, and `(…) Tj` with the page text.\n"
            "  3. End with `ET` then `endstream`.\n\n"
            "Here are the page texts (escape parentheses with `\\(` and `\\)`):\n"
        )
        for i, txt in enumerate(page_texts, 1):
            esc = txt.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            prompt += f"\n--- Page {i}:\n{esc}\n"
        prompt += f"\nReturn {N} consecutive PDF blocks, no extra text."

        logger.info("✉️ Prompt to LLM:\n%s", prompt)

        # 5. Call the LLM and validate response
        raw = ""
        for attempt in range(1, max_retries+1):
            logger.info("🧠 LLM attempt %d/%d", attempt, max_retries)
            r = requests.post(
                f"{os.getenv('OLLAMA_BASE_URL')}/api/generate",
                json={"model": os.getenv("LLM"), "prompt": prompt, "stream": False}
            )
            r.raise_for_status()
            candidate = r.json().get("response", "")
            logger.info("💬 LLM response (first 500 chars):\n%s", candidate[:500].replace("\n","\\n"))

            # Basic check for PDF stream syntax
            if candidate.count("<< /Length") >= N and "```" not in candidate:
                raw = candidate
                logger.info("✅ LLM response passed PDF‐stream check")
                break
            else:
                logger.warning("⚠️ LLM response invalid for PDF streams; retrying")

        if not raw:
            logger.error("❌ LLM did not produce valid PDF streams after %d attempts", max_retries)
            return JSONResponse(
                status_code=500,
                content={"error": "LLM failed to produce valid PDF streams", "status": "failure"}
            )

        # 6. Split into content-stream blocks
        parts = [blk.strip() for blk in raw.split("endstream") if blk.strip()]
        streams = [blk + "\nendstream" for blk in parts[:N]]

        # 7. Assemble and write the PDF
        base = f"/tmp/genai_{uuid.uuid4()}"
        assembled = f"{base}.pdf"
        build_full_pdf_from_streams(streams, assembled)

        # 8. Validate & repair if needed
        valid, msg = is_valid_pdf(assembled)
        logger.info("🔍 Validation: %s (%s)", "OK" if valid else "FAIL", msg)
        if not valid:
            repaired = f"{base}_rep.pdf"
            if repair_pdf_with_pymupdf(assembled, repaired):
                valid2, msg2 = is_valid_pdf(repaired)
                logger.info("🔍 Post-repair: %s (%s)", "OK" if valid2 else "FAIL", msg2)
                if valid2:
                    assembled = repaired
                else:
                    return JSONResponse(
                        status_code=500,
                        content={"error": f"Repaired PDF invalid: {msg2}", "status": "failure"}
                    )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"error": f"Could not repair PDF: {msg}", "status": "failure"}
                )

        # 9. Stream final PDF
        logger.info("📤 Streaming final PDF: %s", assembled)
        return StreamingResponse(
            open(assembled, "rb"),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="accessible_{file.filename}"'}
        )

    except Exception as e:
        logger.exception("🔥 Exception in /accessible-document-version")
        return JSONResponse(status_code=500, content={"error": str(e), "status": "failure"})
