import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from routers import pdf_router, chat_router

app = FastAPI(
    title="Document Intelligence Platform API",
    description="High-performance, lightweight FastAPI backend supporting multi-format document parsing, roadmap summarization, and RAG retrieval.",
    version="1.0.0"
)

# Enable GZip compression middleware (min size 1000 bytes) to save Railway network bandwidth
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Enable CORS for cross-origin frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pdf_router.router)
app.include_router(chat_router.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "Document Intelligence Platform API",
        "version": "1.0.0"
    }

# Mount production React build static files if present
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
frontend_dist = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "dist"))

if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
