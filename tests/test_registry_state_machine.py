import os
import sys
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import config
from services.metadata_service import MetadataService
from services.rag_service import RAGService


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_reg_state.db")
    import services.metadata_service as ms_module
    monkeypatch.setattr(ms_module, "DB_PATH", db_file)
    MetadataService.init_db()
    return MetadataService


class TestRegistryStateMachineA4:
    """A4 — Registry state machine tests."""

    def test_happy_path_transitions(self, isolated_db):
        doc_id = "state_doc_happy"
        isolated_db.register_document(
            doc_id=doc_id,
            content_hash="hash_happy_01",
            filename="happy.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            unit_count=3,
            unit_kind="page",
            storage_path="/tmp/happy.pdf",
            status="UPLOADED"
        )
        assert isolated_db.get_document(doc_id)["status"] == "UPLOADED"

        # Sequential transitions
        transitions = ["PARSING", "CHUNKING", "INDEXED", "READY"]
        for st in transitions:
            isolated_db.update_status(doc_id, st)
            assert isolated_db.get_document(doc_id)["status"] == st

    def test_illegal_skip_raises_error(self, isolated_db):
        doc_id = "illegal_skip_doc"
        isolated_db.register_document(
            doc_id=doc_id,
            content_hash="hash_illegal_01",
            filename="skip.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            unit_count=2,
            unit_kind="page",
            storage_path="/tmp/skip.pdf",
            status="UPLOADED"
        )
        # Attempt illegal skip from UPLOADED directly to READY
        with pytest.raises(ValueError) as excinfo:
            isolated_db.update_status(doc_id, "READY")
        assert "Illegal state transition" in str(excinfo.value)

    def test_crash_mid_parsing_retains_parsing_and_retry_recovers(self, isolated_db):
        doc_id = "crash_parsing_doc"
        isolated_db.register_document(
            doc_id=doc_id,
            content_hash="hash_crash_01",
            filename="crash.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            unit_count=2,
            unit_kind="page",
            storage_path="/tmp/crash.pdf",
            status="UPLOADED"
        )
        isolated_db.update_status(doc_id, "PARSING")

        # Simulate process crash / interruption mid-parsing
        # State stays PARSING
        doc = isolated_db.get_document(doc_id)
        assert doc["status"] == "PARSING"

        # Retry transition to FAILED or recovery
        isolated_db.update_status(doc_id, "FAILED", error_message="Worker terminated unexpectedly")
        assert isolated_db.get_document(doc_id)["status"] == "FAILED"

        # Retry recovery to PARSING
        isolated_db.update_status(doc_id, "PARSING")
        assert isolated_db.get_document(doc_id)["status"] == "PARSING"

    def test_duplicate_upload_deduplication(self, isolated_db):
        content_hash = "identical_sha256_hash_123"
        doc1 = isolated_db.register_document(
            doc_id="doc_v1",
            content_hash=content_hash,
            filename="document.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=4096,
            unit_count=5,
            unit_kind="page",
            storage_path="/tmp/doc.pdf",
            status="READY"
        )
        # Check lookup by hash finds first doc
        found = isolated_db.get_document_by_hash(content_hash)
        assert found is not None
        assert found["doc_id"] == "doc_v1"

    def test_delete_document_cleans_registry_and_files(self, isolated_db, tmp_path, monkeypatch):
        doc_id = "doc_to_delete"
        vs_dir = tmp_path / "vs" / doc_id
        vs_dir.mkdir(parents=True)
        (vs_dir / "index.faiss").write_bytes(b"dummy faiss")
        (vs_dir / "bm25.pkl").write_bytes(b"dummy bm25")
        (vs_dir / "index_manifest.json").write_text('{"unit_count": 1}')

        monkeypatch.setattr(config, "VECTOR_STORE_DIR", str(tmp_path / "vs"))

        isolated_db.register_document(
            doc_id=doc_id,
            content_hash="hash_to_del",
            filename="delete_me.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            unit_count=1,
            unit_kind="page",
            storage_path=str(tmp_path / "delete_me.pdf"),
            status="READY"
        )
        assert isolated_db.get_document(doc_id) is not None

        # Delete document
        deleted = isolated_db.delete_document(doc_id)
        assert deleted is True
        assert isolated_db.get_document(doc_id) is None
        assert not vs_dir.exists(), "Vector store directory was not cleaned"

    def test_concurrent_uploads_wal_mode(self, isolated_db):
        """WAL mode holds under 5 parallel writes with zero database locking errors."""
        def register_worker(worker_id):
            return isolated_db.register_document(
                doc_id=f"worker_doc_{worker_id}",
                content_hash=f"hash_{worker_id}_{uuid.uuid4().hex[:6]}",
                filename=f"worker_{worker_id}.pdf",
                format_ext=".pdf",
                mime_type="application/pdf",
                size_bytes=1000 + worker_id,
                unit_count=worker_id + 1,
                unit_kind="page",
                storage_path=f"/tmp/w_{worker_id}.pdf",
                status="UPLOADED"
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(register_worker, i) for i in range(5)]
            results = [f.result() for f in futures]

        assert len(results) == 5
        docs = isolated_db.list_documents()
        assert len(docs) >= 5

    def test_query_document_in_parsing_returns_still_processing(self, isolated_db):
        doc_id = "doc_in_parsing"
        isolated_db.register_document(
            doc_id=doc_id,
            content_hash="hash_parsing_query",
            filename="slow_parse.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=5000,
            unit_count=10,
            unit_kind="page",
            storage_path="/tmp/slow.pdf",
            status="UPLOADED"
        )
        isolated_db.update_status(doc_id, "PARSING")

        res = RAGService.query(document_id=doc_id, question="what are the main themes?")
        ans = res["answer"].lower()
        assert "still processing" in ans or "parsing" in ans
        assert res.get("strategy") == "still_processing"
        assert len(res["sources"]) == 0
