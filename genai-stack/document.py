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


@app.post("/accessible-document-version")
async def accessible_document_version_raw_pdf(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    max_retries_param: int = Query(None)
):
    try:
        logger.info("📥 Received request at /accessible-document-version")

        if file.content_type != "application/pdf":
            logger.warning("❌ Invalid file type: %s", file.content_type)
            raise ValueError(f"Invalid content type: {file.content_type}")

        file_bytes = await file.read()
        if not file_bytes:
            logger.warning("❌ Uploaded file is empty.")
            raise ValueError("Uploaded file is empty")

        logger.info("📎 Processing file: %s (%d bytes)", file.filename, len(file_bytes))

        a11y_data = json.loads(metadata)
        logger.info("📊 Parsed A11y metadata:\n%s", json.dumps(a11y_data, indent=2))

        max_retries = max_retries_param or a11y_data.get("maxRetries", 2)
        logger.info("📊 Obtained max LLM-retries: %d (max retries - by - default: %d)", max_retries, MAX_RETRIES_LLM_LOOP_DEFAULT)

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        extracted_text = "\n".join([page.get_text() for page in doc])
        doc.close()
        logger.info("📄 Extracted text length: %d characters", len(extracted_text))

        prompt = (
            "You are a highly specialized assistant that returns valid PDF files using raw PDF syntax.\n\n"
            "Your task is to generate a simplified but valid PDF document that incorporates the following accessibility metadata:\n"
            f"{json.dumps(a11y_data, indent=2)}\n\n"
            "Use the following document content as the main body of the PDF:\n"
            f"{extracted_text[:5000]}\n\n"
            "Return a complete, raw, syntactically valid PDF file as plain text.\n"
            "Make sure your response begins with '%PDF-1.4' and ends with '%%EOF'.\n"
            "Do not include any commentary, markdown, or additional formatting—only raw PDF code.\n"
        )

        response_text = ""
        for attempt in range(1, max_retries + 1):
            logger.info("🧠 Sending prompt to LLM (attempt %d/%d)...", attempt, max_retries)
            response = requests.post(
                f"{ollama_base_url}/api/generate",
                json={
                    "model": llm_name,
                    "prompt": prompt,
                    "stream": False
                }
            )
            logger.info("🌐 LLM HTTP status: %d", response.status_code)
            response.raise_for_status()

            response_data = response.json()
            response_text = response_data.get("response", "")
            logger.info("🌐 LLM raw response:\n%s", response_text)

            if response_text.startswith("%PDF") and response_text.strip().endswith("%%EOF"):
                logger.info("Received valid PDF response from LLM on attempt %d", attempt)
            else:
                logger.warning("LLM response is not valid PDF code, saving anyway as .pdf text file.")

        # Save to file: may not be needed or wanted ultimately (Alfresco question: stream the response for now, additionally)
        output_filename = f"/tmp/genai_{uuid.uuid4()}.pdf"
        with open(output_filename, "wb") as f:
            f.write(response_text.encode("utf-8"))

        logger.info("📄 PDF file written to: %s", output_filename)

        return StreamingResponse(
            io.BytesIO(response_text.encode("utf-8")),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="accessible_version_{file.filename}"'
            }
        )

    except Exception as e:
        logger.exception("🔥 Exception in /accessible-document-version (raw PDF mode)")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "status": "failure"}
        )

