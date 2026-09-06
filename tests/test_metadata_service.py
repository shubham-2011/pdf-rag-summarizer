"""
tests/test_metadata_service.py
================================
Unit tests for MetadataService SQLite registry.

Covers:
  - DB initialisation (WAL mode, tables created)
  - register_document + get_document round-trip
  - find_by_hash (get_document_by_hash) deduplication
  - update_status lifecycle transitions
  - index_path persisted correctly via update_status
  - list_documents with and without status filter
  - save/get identity and synopsis
  - rebuild_registry_from_disk (scan from manifest + identity card)
"""

import json
import os
import sys
import uuid
import pytest

# Make backend importable
_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


# ---------------------------------------------------------------------------
# Fixture: isolated DB per test
# ---------------------------------------------------------------------------

@pytest.fixture()
def meta(tmp_path, monkeypatch):
    """Return a MetadataService instance wired to a private temp DB."""
    import services.metadata_service as ms_module
    db_path = str(tmp_path / "test_registry.db")
    monkeypatch.setattr(ms_module, "DB_PATH", db_path)

    from services.metadata_service import MetadataService
    MetadataService.init_db()
    return MetadataService


def _new_id():
    return str(uuid.uuid4())[:8]


def _register(meta, doc_id=None, content_hash=None, filename="sample.pdf",
               format_ext=".pdf", status="UPLOADED"):
    doc_id = doc_id or _new_id()
    content_hash = content_hash or uuid.uuid4().hex
    return meta.register_document(
        doc_id=doc_id,
        content_hash=content_hash,
        filename=filename,
        format_ext=format_ext,
        mime_type="application/pdf",
        size_bytes=1024,
        unit_count=1,
        unit_kind="page",
        storage_path=f"/tmp/{doc_id}.pdf",
        status=status,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_tables_created(self, meta, tmp_path):
        import sqlite3, services.metadata_service as ms_module
        conn = sqlite3.connect(ms_module.DB_PATH)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "documents" in tables
        assert "document_identity" in tables
        assert "document_synopsis" in tables
        assert "document_outline" in tables

    def test_wal_mode_enabled(self, meta, tmp_path):
        import sqlite3, services.metadata_service as ms_module
        conn = sqlite3.connect(ms_module.DB_PATH)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"


class TestRegisterAndGet:
    def test_register_returns_doc(self, meta):
        doc = _register(meta, doc_id="abc123")
        assert doc is not None
        assert doc["doc_id"] == "abc123"
        assert doc["status"] == "UPLOADED"

    def test_get_document_by_id(self, meta):
        _register(meta, doc_id="xyz999")
        result = meta.get_document("xyz999")
        assert result["doc_id"] == "xyz999"

    def test_get_nonexistent_returns_none(self, meta):
        assert meta.get_document("does_not_exist") is None


class TestDeduplication:
    def test_find_by_hash_returns_existing(self, meta):
        h = uuid.uuid4().hex
        _register(meta, content_hash=h, doc_id="dup1")
        found = meta.get_document_by_hash(h)
        assert found is not None
        assert found["doc_id"] == "dup1"

    def test_find_by_hash_missing_returns_none(self, meta):
        assert meta.get_document_by_hash("nonexistent_hash") is None

    def test_same_hash_idempotent(self, meta):
        """INSERT OR REPLACE with same content_hash should overwrite."""
        h = uuid.uuid4().hex
        _register(meta, content_hash=h, doc_id="first")
        # Re-register same hash under same doc_id -> should succeed via REPLACE
        _register(meta, content_hash=h, doc_id="first")
        assert meta.get_document_by_hash(h)["doc_id"] == "first"


class TestStatusTransitions:
    STATES = ["UPLOADED", "PARSING", "CHUNKING", "EMBEDDING", "INDEXED", "READY"]

    def test_full_lifecycle(self, meta):
        doc_id = "lifecycle01"
        _register(meta, doc_id=doc_id)
        for state in self.STATES[1:]:
            meta.update_status(doc_id, state)
            doc = meta.get_document(doc_id)
            assert doc["status"] == state

    def test_failed_state_stores_error(self, meta):
        doc_id = "fail_doc"
        _register(meta, doc_id=doc_id)
        meta.update_status(doc_id, "FAILED", error_message="Embedding model not found")
        doc = meta.get_document(doc_id)
        assert doc["status"] == "FAILED"
        assert "Embedding model not found" in doc["error_message"]

    def test_index_path_persisted(self, meta):
        doc_id = "indexed_doc"
        _register(meta, doc_id=doc_id)
        meta.update_status(doc_id, "INDEXED", index_path="/storage/chroma_db/indexed_doc", enforce_transitions=False)
        doc = meta.get_document(doc_id)
        assert doc["index_path"] == "/storage/chroma_db/indexed_doc"


class TestListDocuments:
    def test_list_all(self, meta):
        _register(meta, doc_id="listA")
        _register(meta, doc_id="listB")
        docs = meta.list_documents()
        ids = [d["doc_id"] for d in docs]
        assert "listA" in ids
        assert "listB" in ids

    def test_list_filtered_by_status(self, meta):
        _register(meta, doc_id="readyDoc", status="UPLOADED")
        meta.update_status("readyDoc", "READY", enforce_transitions=False)
        _register(meta, doc_id="failedDoc", status="UPLOADED")
        meta.update_status("failedDoc", "FAILED")

        ready = meta.list_documents(status="READY")
        failed = meta.list_documents(status="FAILED")
        assert any(d["doc_id"] == "readyDoc" for d in ready)
        assert all(d["doc_id"] != "failedDoc" for d in ready)
        assert any(d["doc_id"] == "failedDoc" for d in failed)


class TestIdentityAndSynopsis:
    def test_save_and_get_identity(self, meta):
        _register(meta, doc_id="idcard01")
        card = {
            "title": "Test Doc",
            "doc_type": "Technical",
            "domain": "Engineering",
            "purpose": "Testing",
            "key_entities": ["FAISS", "Nomic"],
            "authors": "A. Dev",
            "doc_date": "2026-01-01",
            "revision": "v1",
            "language": "en",
            "generated_by": "local_parser",
        }
        meta.save_identity("idcard01", card)
        result = meta.get_identity("idcard01")
        assert result["title"] == "Test Doc"
        assert "FAISS" in result["key_entities"]

    def test_save_and_get_synopsis(self, meta):
        _register(meta, doc_id="synop01")
        meta.save_synopsis(
            doc_id="synop01",
            synopsis="A test synopsis.",
            source_locators=[{"page": 1}],
            strategy="retrieval",
            generated_by="gemini",
        )
        result = meta.get_synopsis("synop01")
        assert result["synopsis"] == "A test synopsis."
        assert result["source_locators"][0]["page"] == 1

    def test_identity_nonexistent_returns_none(self, meta):
        assert meta.get_identity("ghost_doc") is None

    def test_synopsis_nonexistent_returns_none(self, meta):
        assert meta.get_synopsis("ghost_doc") is None


class TestRebuildFromDisk:
    def test_rebuild_from_manifests(self, meta, tmp_path):
        """rebuild_registry_from_disk should import docs from index manifests."""
        import services.metadata_service as ms_module

        # Create a fake vector store directory with two indexed docs
        vs_dir = str(tmp_path / "chroma_db")
        for doc_name in ["doc_a", "doc_b"]:
            doc_dir = os.path.join(vs_dir, doc_name)
            os.makedirs(doc_dir)
            manifest = {
                "doc_id": doc_name,
                "content_hash": uuid.uuid4().hex,
                "filename": f"{doc_name}.pdf",
                "format": "pdf",
                "size_bytes": 2048,
                "chunk_count": 5,
                "storage_path": f"/tmp/{doc_name}.pdf",
            }
            with open(os.path.join(doc_dir, "index_manifest.json"), "w") as f:
                json.dump(manifest, f)

        count = meta.rebuild_registry_from_disk(vs_dir)
        assert count == 2

        # Both docs should now be in the registry
        all_docs = meta.list_documents()
        ids = [d["doc_id"] for d in all_docs]
        assert "doc_a" in ids
        assert "doc_b" in ids

    def test_rebuild_empty_dir(self, meta, tmp_path):
        vs_dir = str(tmp_path / "empty_chroma")
        os.makedirs(vs_dir)
        count = meta.rebuild_registry_from_disk(vs_dir)
        assert count == 0

    def test_rebuild_nonexistent_dir(self, meta):
        count = meta.rebuild_registry_from_disk("/does/not/exist")
        assert count == 0
