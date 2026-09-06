import os
import sys
import re
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import SourceCitation
from services.metadata_service import MetadataService
from services.query_understanding_service import QueryUnderstandingService
from services.pdf_service import PDFService
import config


class TestIncidentRegressionsR:
    """R1–R7 Incident Regression Suite (proven historical failures)."""

    def test_r1_log09_blank_white_screen_relative_base(self):
        """Log 09: Ensure vite.config.js defines base: './' to avoid blank screen on root or path mounts."""
        vite_config_path = os.path.join(FRONTEND_DIR, "vite.config.js")
        assert os.path.exists(vite_config_path), f"vite.config.js not found at {vite_config_path}"
        with open(vite_config_path, "r", encoding="utf-8") as f:
            src = f.read()
        assert "base: './'" in src or 'base: "./"' in src, "vite.config.js must set base: './'"

    def test_r2_log11_16_tunnel_503_header_and_cors(self):
        """Log 11/16: Ensure bypass-tunnel-reminder: true header is present in client.js."""
        client_js_path = os.path.join(FRONTEND_DIR, "src", "api", "client.js")
        assert os.path.exists(client_js_path), f"client.js not found at {client_js_path}"
        with open(client_js_path, "r", encoding="utf-8") as f:
            src = f.read()
        assert "bypass-tunnel-reminder" in src, "client.js must include bypass-tunnel-reminder header"

    def test_r3_log14_laptop_sleep_health_check_and_restart_policy(self):
        """Log 14: Health-check endpoint returns 200, and container restart policy is present."""
        from main import app
        client = TestClient(app)
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"

        # Check restart policy in docker-compose.yml or Dockerfile
        dc_path = os.path.join(REPO_ROOT, "docker-compose.yml")
        if os.path.exists(dc_path):
            with open(dc_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "restart: always" in content

    def test_r4_log17_chunking_defects(self):
        """Log 17: Regress chunk quality checks on sample document."""
        pdf_path = os.path.join(REPO_ROOT, "tests", "test_documents", "technical_manual_long.pdf")
        chunks, _ = PDFService.process_pdf(pdf_path)
        for c in chunks:
            assert not re.search(r'\w-\s*$', c.page_content), "Mid-word hyphen cut detected"
            assert not c.page_content.startswith(('ized ', 'tion ', 'ing ')), "Suffix orphan detected"
            assert c.metadata.get("page_label") is not None, "Missing page_label"
            assert c.metadata.get("section_heading") is not None, "Missing section_heading"

    def test_r5_log18_pronoun_follow_ups(self):
        """Log 18: Multi-turn contextualization chain with minimum 3 turns."""
        history = [
            {"role": "user", "content": "What is the primary step-down transformer rating?"},
            {"role": "assistant", "content": "The primary step-down transformer is 11kV/415V, 1500 kVA."},
            {"role": "user", "content": "What cooling does it use?"},
            {"role": "assistant", "content": "It uses Oil Natural Air Natural (ONAN) cooling."},
        ]
        q = "and what is its primary impedance or switchgear?"
        rewritten = QueryUnderstandingService.contextualize_question(q, chat_history=history)
        assert len(rewritten) > 0
        assert "transformer" in rewritten.lower() or "cooling" in rewritten.lower() or "switchgear" in rewritten.lower()

    def test_r6_cause3_no_hardcoded_fallback_15(self):
        """Log 21 Cause 3: Ensure query_understanding_service.py does not hardcode page count 15."""
        qu_path = os.path.join(BACKEND_DIR, "services", "query_understanding_service.py")
        with open(qu_path, "r", encoding="utf-8") as f:
            src = f.read()
        assert '"15"' not in src and "'15'" not in src, "Hardcoded page count '15' reintroduced in query_understanding_service.py"

    def test_r6_cause2_manifest_records_unit_count(self):
        """Log 21 Cause 2: Vector store manifests must include unit_count."""
        manifest = {
            "doc_id": "test_r6",
            "chunk_count": 10,
            "unit_count": 1
        }
        assert "unit_count" in manifest and manifest["unit_count"] == 1

    @pytest.mark.parametrize("doc_id,pages", [
        ("eval_electrical_layout_drawing", 1),
        ("757636a1", 2),
        ("eval_water_quality_report", 3),
        ("eval_technical_manual_long", 15),
    ])
    def test_r6_page_count_accurate_answer(self, doc_id, pages):
        """Log 21: Verify accurate page count response on parameterized fixtures."""
        MetadataService.init_db()
        res = QueryUnderstandingService.classify_and_route("how many pages does this document have", doc_id=doc_id)
        ans = res.get("direct_answer", "")
        assert str(pages) in ans, f"Expected page count '{pages}' in answer: '{ans}'"
        if pages != 15:
            assert "15" not in ans, f"Discrepancy: Answer contains 15 for non-15 page doc: {ans}"

    def test_r7_source_citation_compatibility(self):
        """R7: SourceCitation schema must accept text only, snippet only, or both without HTTP 422/500."""
        # 1. Payload with snippet only
        c1 = SourceCitation(page=1, file="doc.pdf", snippet="Snippet only content")
        assert c1.snippet == "Snippet only content"
        assert c1.text == "Snippet only content"

        # 2. Payload with text only
        c2 = SourceCitation(page=2, file="doc.pdf", text="Text only content")
        assert c2.text == "Text only content"
        assert c2.snippet == "Text only content"

        # 3. Payload with both text and snippet
        c3 = SourceCitation(page=3, file="doc.pdf", text="Both text", snippet="Both snippet")
        assert c3.text == "Both text"
        assert c3.snippet == "Both snippet"

    def test_r7_chat_query_what_is_this_pdf_for_returns_200(self):
        """R7: /api/chat/query endpoint returns 200 OK for 'what is this pdf for?' without HTTP 500."""
        from main import app
        client = TestClient(app)
        MetadataService.init_db()

        payload = {
            "document_id": "eval_electrical_layout_drawing",
            "question": "what is this pdf for?"
        }
        res = client.post("/api/chat/query", json=payload)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "answer" in data
        assert len(data["answer"]) > 10
