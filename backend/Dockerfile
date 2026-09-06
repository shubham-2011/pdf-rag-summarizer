FROM python:3.11-slim

WORKDIR /app

# Install system build dependencies and LibreOffice for headless multi-format conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libreoffice-nogui \
    && rm -rf /var/lib/apt/lists/*

# Set cache directory for HuggingFace models
ENV HF_HOME=/root/.cache/huggingface
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# Copy requirements and install (using CPU-optimized wheels for torch to keep image lean)
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Pre-download open-source models into container image
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
    SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True); \
    CrossEncoder('BAAI/bge-reranker-base')"

# Copy backend source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p /app/storage/vector_stores /app/storage/uploads /app/storage/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
