# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Production FastAPI Server
FROM python:3.11-slim
WORKDIR /app

# Install system build dependencies and LibreOffice for headless multi-format conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libreoffice-nogui \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Pre-download open-source embedding and reranker models into container image layer
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
    SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True); \
    CrossEncoder('BAAI/bge-reranker-base')"

COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure persistent storage directories exist
RUN mkdir -p /app/backend/storage/vector_stores \
             /app/backend/storage/uploads \
             /app/backend/storage/data

WORKDIR /app/backend
EXPOSE 8000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

