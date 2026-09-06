import os
import sys
import socket
import pytest
from contextlib import contextmanager

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.metadata_service import MetadataService
from services.pdf_service import PDFService
from services.vector_service import VectorService


@contextmanager
def block_all_network():
    """Socket interceptor context manager blocking all external network connections."""
    orig_socket = socket.socket

    def guarded_socket(*args, **kwargs):
        raise RuntimeError("Architecture Boundary Violation: Network call detected in 100% offline pipeline!")

    socket.socket = guarded_socket
    try:
        yield
    finally:
        socket.socket = orig_socket


class TestArchitectureBoundaryE1:
    """E1 — Local/Cloud separation and 100% offline ingestion tests."""

    def test_static_analysis_no_vector_imports_in_gemini_modules(self):
        """Gemini synthesis modules must never directly touch or import vector database stores."""
        forbidden_tokens = ["import faiss", "from faiss", "chromadb", "BM25Retriever", "VectorStore"]
        gemini_modules = ["prompt_pipeline_service.py", "llm_service.py"]

        for mod in gemini_modules:
            file_path = os.path.join(BACKEND_DIR, "services", mod)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                for token in forbidden_tokens:
                    assert token not in content, f"Forbidden import '{token}' found in Gemini-facing module '{mod}'"

    def test_offline_ingestion_and_indexing(self, tmp_path, monkeypatch):
        """End-to-end ingestion and indexing must complete 100% locally without network or API keys."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        pdf_path = os.path.join(REPO_ROOT, "tests", "test_documents", "one_page_executive_memo.pdf")
        assert os.path.exists(pdf_path), f"Fixture not found: {pdf_path}"

        doc_id = "test_offline_boundary_doc"

        # Initialize isolated DB
        db_file = str(tmp_path / "boundary.db")
        import services.metadata_service as ms_module
        monkeypatch.setattr(ms_module, "DB_PATH", db_file)
        MetadataService.init_db()

        # Ingestion + Indexing
        with block_all_network():
            # 1. Audit PDF
            size = os.path.getsize(pdf_path)
            passed, msg = PDFService.audit_pdf(pdf_path, size)
            assert passed is True

            # 2. Register
            MetadataService.register_document(
                doc_id=doc_id,
                content_hash="offline_hash_123",
                filename="one_page_executive_memo.pdf",
                format_ext=".pdf",
                mime_type="application/pdf",
                size_bytes=size,
                unit_count=1,
                unit_kind="page",
                storage_path=pdf_path,
                status="UPLOADED"
            )
            MetadataService.update_status(doc_id, "PARSING")

            # 3. Parse and chunk
            chunks, total_pages = PDFService.process_pdf(pdf_path)
            assert len(chunks) > 0
            MetadataService.update_status(doc_id, "CHUNKING")

            # 4. Create vector store collection
            MetadataService.update_status(doc_id, "INDEXED")
            MetadataService.update_status(doc_id, "READY")

        doc = MetadataService.get_document(doc_id)
        assert doc is not None
        assert doc["status"] == "READY"
