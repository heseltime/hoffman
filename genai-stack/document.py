import os
import base64
import pycurl
import json
from io import BytesIO
from urllib.parse import urlencode

import streamlit as st
from langchain.chains import RetrievalQA
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.callbacks.base import BaseCallbackHandler
from langchain.vectorstores.neo4j_vector import Neo4jVector
from streamlit.logger import get_logger
from chains import (
    load_embedding_model,
    load_llm,
)
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

import shutil

@app.post("/accessible-document-version")
async def new_version(
    file: UploadFile = File(...),
    metadata: str = Form(...)
):
    try:
        a11y_data = json.loads(metadata)

        print("📊 Copying uploaded file to disk")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            shutil.copyfileobj(file.file, temp_pdf)
            temp_path = temp_pdf.name

        print("📊 Received A11y metadata:", json.dumps(a11y_data, indent=2))
        print("📄 File saved at:", temp_path)

        pages_object_code = extract_page_object_code(temp_path)

        improved_pages = []
        for i, page_code in enumerate(pages_object_code):
            improved_code = get_improved_page_code(page_code, a11y_data, i + 1)
            improved_pages.append(improved_code)

        # Save LLM output for inspection
        for i, code in enumerate(improved_pages):
            try:
                filename = f"page_{i+1}_improved.json"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(code)
                logger.info(f"✅ Saved improved object code for page {i+1} → {filename}")
            except Exception as e:
                logger.error(f"❌ Failed to write page {i+1}: {e}")

        os.remove(temp_path)

        return JSONResponse(
            status_code=200,
            content={"message": "Improved object code generated", "pages": len(improved_pages), "model": llm_name}
        )

    except Exception as e:
        logger.error(f"❌ Exception in /accessible-document-version: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "status": "failure"}
        )


import fitz  # PyMuPDF

def extract_page_object_code(pdf_path: str) -> list[str]:
    """
    Returns a list of object-code strings, one per page.
    """
    doc = fitz.open(pdf_path)
    pages_object_code = []

    for i, page in enumerate(doc):
        rawdict = page.get_text("rawdict")
        pages_object_code.append(json.dumps(rawdict, indent=2))  # Optional: more LLM-friendly
    return pages_object_code

# Use LangChain wrapper as in your existing classify/summary endpoints
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

def get_improved_page_code(original_code: str, metadata: dict, page_number: int) -> str:
    prompt_template = PromptTemplate.from_template("""
        You are an AI assistant specializing in PDF accessibility remediation.

        Here is the accessibility metadata for page {page_number}:
        {metadata}

        Here is the original PDF object code of page {page_number}:
        {object_code}

        Improve the structure and add accessibility features such as tags, /Alt attributes for images, and logical reading order.
        Return only the corrected page object code in valid JSON format.
        """)

    chain = LLMChain(llm=llm, prompt=prompt_template)

    response = chain.run({
        "page_number": page_number,
        "metadata": json.dumps(metadata, indent=2),
        "object_code": original_code
    })

    return response.strip()
