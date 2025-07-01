FROM langchain/langchain

WORKDIR /app

# Install OS-level dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    poppler-utils \
    tesseract-ocr \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install Jupyter for document.ipynb running in endpoint conditions
RUN pip install jupyterlab

# Copy your app code
COPY document.py .
COPY document.ipynb .
COPY chains.py .
COPY utils.py .

# Optional: copy .env if used in container
# COPY .env .

# Healthcheck for container orchestration tools
HEALTHCHECK CMD curl --fail http://localhost:8506 || exit 1

# Start FastAPI app
ENTRYPOINT ["uvicorn", "document:app", "--host", "0.0.0.0", "--port", "8506", "--log-level", "debug"]
