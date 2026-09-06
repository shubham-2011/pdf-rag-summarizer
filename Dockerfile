# Pure Backend-Only Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install system build dependencies and LibreOffice for multi-format conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libreoffice-nogui \
    && rm -rf /var/lib/apt/lists/*

ENV HF_HOME=/root/.cache/huggingface
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r ./backend/requirements.txt

# Pre-download primary offline embedding models (reranker loads at runtime)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"

COPY backend/ ./backend/

RUN mkdir -p /app/backend/storage/vector_stores \
             /app/backend/storage/uploads \
             /app/backend/storage/data

WORKDIR /app/backend
EXPOSE 8000

ENV PORT=8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
