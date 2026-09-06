import os
import sys
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.main import app
from backend.services.metadata_service import MetadataService
from backend.services.vector_service import VectorService
from backend.services.query_understanding_service import QueryUnderstandingService
from audit.make_fixtures import make_docx_fixture, make_pptx_fixture, make_xlsx_fixture, make_pdf_fixture


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestDocxFormatAuditAndDisplay:
    """
    Comprehensive verification for multi-format auditing and honest unit semantics.
    Guarantees no false precision, no fabricated page counts, and full container extraction.
    """

    def test_docx_upload_preserves_docx_format_and_honest_units(self, client, tmp_path):
        docx_path = make_docx_fixture()
        
        with open(docx_path, "rb") as f:
            resp = client.post("/api/pdf/upload", files={"file": ("test_audit_sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        doc_id = data["document_id"]
        
        # 1. API Upload Response assertions
        assert data["format"] == "docx"
        assert data["unit_name"] == "paragraphs"
        assert data["total_pages"] == 0 or data["total_pages"] is None, "DOCX must never report total_pages"
        assert "paragraphs" in data["details"].lower()
        assert "tables" in data["details"].lower()
        assert "DOCX audit passed" in data["message"]
        
        # 2. SQLite Metadata Registry assertions
        doc_meta = MetadataService.get_document(doc_id)
        assert doc_meta is not None
        assert doc_meta["format"] == "docx"
        assert doc_meta["unit_kind"] == "paragraph"
        assert doc_meta["unit_count"] is None, "DOCX unit_count in registry must be None"
        
        # 3. Vector Manifest assertions
        manifest = VectorService.validate_index_manifest(doc_id)
        assert manifest["format"] == "docx"
        assert manifest["unit_kind"] == "paragraph"
        assert manifest["unit_count"] is None, "DOCX unit_count in manifest must be None"
        
        # 4. Structural Query Answering - Honest Answer assertions
        route = QueryUnderstandingService.classify_and_route("How many pages does this document have?", doc_id=doc_id)
        answer = route["direct_answer"]
        assert "no fixed page" in answer.lower(), f"Answer must explain Word documents have no fixed page count. Got: {answer}"
        assert "exactly" not in answer.lower() or "pages" not in answer.lower(), f"Must not assert exact page count. Got: {answer}"
        assert "paragraphs" in answer.lower()
        assert "tables" in answer.lower()

    def test_all_containers_extracted_without_loss(self):
        docx_path = make_docx_fixture()
        from backend.services.document_service import DocumentService
        
        docs, units = DocumentService.process_document(docx_path)
        combined = "\n\n".join([d.page_content for d in docs])
        
        # Assert each planted canary from each container type is extracted
        assert "CANARY_DOCX_PARAGRAPH_ALPHA" in combined, "Body paragraph lost"
        assert "CANARY_DOCX_PARAGRAPH_BETA" in combined, "Body paragraph lost"
        assert "CANARY_DOCX_TABLE_METRIC_ROW1" in combined, "Table row 1 lost"
        assert "CANARY_DOCX_TABLE_METRIC_ROW2" in combined, "Table row 2 lost"
        assert "CANARY_DOCX_HEADER_SEC1" in combined, "Header lost"
        assert "CANARY_DOCX_FOOTER_SEC1" in combined, "Footer lost"
        assert "CANARY_DOCX_TEXTBOX_CALLOUT" in combined, "Text box lost"

    def test_pptx_slide_semantics_honest_answer(self, client):
        pptx_path = make_pptx_fixture()
        with open(pptx_path, "rb") as f:
            resp = client.post("/api/pdf/upload", files={"file": ("presentation.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")})
        
        assert resp.status_code == 200
        data = resp.json()
        doc_id = data["document_id"]
        
        assert data["format"] == "pptx"
        assert data["unit_name"] == "slides"
        
        route = QueryUnderstandingService.classify_and_route("How many pages does this document have?", doc_id=doc_id)
        answer = route["direct_answer"]
        assert "slide" in answer.lower()
        assert "no page count" in answer.lower()

    def test_pdf_native_page_semantics_exact_answer(self, client):
        pdf_path = make_pdf_fixture()
        with open(pdf_path, "rb") as f:
            resp = client.post("/api/pdf/upload", files={"file": ("manual.pdf", f, "application/pdf")})
        
        assert resp.status_code == 200
        data = resp.json()
        doc_id = data["document_id"]
        
        assert data["format"] == "pdf"
        assert data["total_pages"] == 2
        
        route = QueryUnderstandingService.classify_and_route("How many pages does this document have?", doc_id=doc_id)
        answer = route["direct_answer"]
        assert "exactly 2 pages" in answer.lower()
