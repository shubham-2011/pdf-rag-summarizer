import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-1.5-flash")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Local Offline Embedding & Reranker Configuration
_raw_embed = os.getenv("EMBEDDING_MODEL", "")
EMBEDDING_MODEL = _raw_embed if (_raw_embed and "text-embedding" not in _raw_embed) else "nomic-ai/nomic-embed-text-v1.5"
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DOC_EMBED_PREFIX = "search_document: "
QUERY_EMBED_PREFIX = "search_query: "
RERANKER_MODEL = "BAAI/bge-reranker-base"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "backend", "storage", "vector_stores")
TEMP_UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "storage", "uploads")
METADATA_DB_PATH = os.path.join(BASE_DIR, "backend", "storage", "data", "registry.db")

os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)

