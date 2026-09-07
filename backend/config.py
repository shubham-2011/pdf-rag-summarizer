import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.5-flash-lite")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "gemini-3.5-flash-lite")
LLM_SYNTHESIS_MODEL = os.getenv("LLM_SYNTHESIS_MODEL", "gemini-3.5-flash-lite")
PROMPT_PIPELINE_ENABLED = os.getenv("PROMPT_PIPELINE_ENABLED", "false").lower() in ("true", "1", "yes")
PIPELINE_RERANK_SCORE_FLOOR = float(os.getenv("PIPELINE_RERANK_SCORE_FLOOR", "4.0"))
PIPELINE_MAX_RETRIES = int(os.getenv("PIPELINE_MAX_RETRIES", "2"))


# Local Offline Embedding & Reranker Configuration
_raw_embed = os.getenv("EMBEDDING_MODEL", "")
EMBEDDING_MODEL = _raw_embed if (_raw_embed and "text-embedding" not in _raw_embed) else "nomic-ai/nomic-embed-text-v1.5"
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DOC_EMBED_PREFIX = "search_document: "
QUERY_EMBED_PREFIX = "search_query: "
RERANKER_MODEL = "BAAI/bge-reranker-base"

# PDF Audit Threshold Constraints
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_PAGE_COUNT = 200
MIN_TEXT_CHARS = 20

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Multi-Format Ingestion Adapter Configuration
MULTIFORMAT_ENABLED = os.getenv("MULTIFORMAT_ENABLED", "true").lower() in ("true", "1", "yes")
MULTIFORMAT_FORMATS = [f.strip().lower() for f in os.getenv("MULTIFORMAT_FORMATS", "docx,pptx,doc,ppt").split(",") if f.strip()]
LIBREOFFICE_PATH = os.getenv("LIBREOFFICE_PATH", "")
CONVERSION_TIMEOUT_SECONDS = int(os.getenv("CONVERSION_TIMEOUT_SECONDS", "120"))
CONVERSION_SEMAPHORE_LIMIT = int(os.getenv("CONVERSION_SEMAPHORE_LIMIT", "2"))
RAG_DISABLE_CONVERTER = os.getenv("RAG_DISABLE_CONVERTER", "0").lower() in ("1", "true", "yes")
CANONICAL_RENDERER = os.getenv("CANONICAL_RENDERER", "libreoffice")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "storage", "vector_stores")
TEMP_UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "uploads")
METADATA_DB_PATH = os.path.join(BASE_DIR, "storage", "data", "registry.db")

os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(METADATA_DB_PATH), exist_ok=True)


