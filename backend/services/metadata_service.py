from typing import List, Dict, Any, Optional
import os
import sqlite3
import hashlib
import json
import pickle
from datetime import datetime
import config

DB_PATH = getattr(
    config,
    "METADATA_DB_PATH",
    # Fallback: put the registry next to the vector store so it is always absolute.
    os.path.join(os.path.dirname(getattr(config, "VECTOR_STORE_DIR", ".")), "data", "registry.db"),
)

class MetadataService:
    """Authoritative Document Metadata Store backed by SQLite (WAL Mode)."""

    @classmethod
    def _get_connection(cls) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @classmethod
    def init_db(cls) -> None:
        """Initializes database schema if not already present and repairs references."""
        with cls._get_connection() as conn:
            # Check if any table references documents_old and recreate
            cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql LIKE '%documents_old%'")
            if cursor.fetchone():
                conn.execute("PRAGMA foreign_keys=OFF;")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS documents_temp (
                        doc_id TEXT PRIMARY KEY,
                        content_hash TEXT UNIQUE NOT NULL,
                        filename TEXT NOT NULL,
                        format TEXT NOT NULL,
                        mime_detected TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        unit_count INTEGER,
                        unit_kind TEXT NOT NULL,
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        storage_path TEXT NOT NULL,
                        index_path TEXT
                    );
                    INSERT OR IGNORE INTO documents_temp SELECT * FROM documents;
                    DROP TABLE IF EXISTS document_identity;
                    DROP TABLE IF EXISTS document_synopsis;
                    DROP TABLE IF EXISTS document_outline;
                    DROP TABLE IF EXISTS workspace_documents;
                    DROP TABLE IF EXISTS documents;
                    ALTER TABLE documents_temp RENAME TO documents;
                """)
                conn.commit()

            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    content_hash TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    format TEXT NOT NULL,
                    mime_detected TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    unit_count INTEGER,
                    unit_kind TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    storage_path TEXT NOT NULL,
                    index_path TEXT
                );

                CREATE TABLE IF NOT EXISTS document_identity (
                    doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id) ON DELETE CASCADE,
                    title TEXT,
                    doc_type TEXT,
                    domain TEXT,
                    purpose TEXT,
                    key_entities JSON,
                    authors TEXT,
                    doc_date TEXT,
                    revision TEXT,
                    language TEXT DEFAULT 'en',
                    generated_by TEXT,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS document_synopsis (
                    doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id) ON DELETE CASCADE,
                    synopsis TEXT NOT NULL,
                    source_locators JSON NOT NULL,
                    strategy TEXT NOT NULL,
                    generated_by TEXT,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    schema_version INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS document_outline (
                    doc_id TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    locator_kind TEXT NOT NULL,
                    locator_index INTEGER NOT NULL,
                    locator_label TEXT,
                    locator_anchor TEXT,
                    heading TEXT,
                    level INTEGER DEFAULT 1,
                    char_count INTEGER NOT NULL,
                    PRIMARY KEY (doc_id, ordinal)
                );

                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workspace_documents (
                    workspace_id TEXT REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                    doc_id TEXT REFERENCES documents(doc_id) ON DELETE CASCADE,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (workspace_id, doc_id)
                );
            """)
            conn.commit()



    @staticmethod
    def calculate_file_hash(file_bytes: bytes) -> str:
        """Computes SHA-256 hash of file content for deduplication."""
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    def get_document_by_hash(cls, content_hash: str) -> Optional[Dict[str, Any]]:
        """Checks for existing document matching content hash."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM documents WHERE content_hash = ?", (content_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @classmethod
    def get_document(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single document by doc_id."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @classmethod
    def list_documents(cls, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all registered documents, optionally filtered by status."""
        cls.init_db()
        with cls._get_connection() as conn:
            if status:
                cursor = conn.execute("SELECT * FROM documents WHERE status = ? ORDER BY uploaded_at DESC", (status,))
            else:
                cursor = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def register_document(
        cls,
        doc_id: str,
        content_hash: str,
        filename: str,
        format_ext: str,
        mime_type: str,
        size_bytes: int,
        unit_count: Optional[int],
        unit_kind: str,
        storage_path: str,
        status: str = "UPLOADED"
    ) -> Dict[str, Any]:
        """Registers a new document in the metadata store."""
        cls.init_db()
        
        # Enforce rule: Formats without native pagination (DOCX, XLSX) must have NULL unit_count
        clean_ext = format_ext.lower().replace(".", "")
        if clean_ext in ["docx", "doc"]:
            unit_count = None
            unit_kind = "section"
        elif clean_ext in ["xlsx", "xls", "csv"]:
            unit_count = None
            unit_kind = "sheet"

        with cls._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO documents (
                    doc_id, content_hash, filename, format, mime_detected,
                    size_bytes, unit_count, unit_kind, status, storage_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id, content_hash, filename, format_ext, mime_type,
                size_bytes, unit_count, unit_kind, status, storage_path
            ))
            conn.commit()
        return cls.get_document(doc_id)

    @classmethod
    def update_status(cls, doc_id: str, status: str, error_message: Optional[str] = None, index_path: Optional[str] = None) -> None:
        """Updates document ingestion lifecycle status."""
        cls.init_db()
        with cls._get_connection() as conn:
            if index_path:
                conn.execute(
                    "UPDATE documents SET status = ?, error_message = ?, index_path = ? WHERE doc_id = ?",
                    (status, error_message, index_path, doc_id)
                )
            else:
                conn.execute(
                    "UPDATE documents SET status = ?, error_message = ? WHERE doc_id = ?",
                    (status, error_message, doc_id)
                )
            conn.commit()

    @classmethod
    def save_identity(cls, doc_id: str, identity_card: Dict[str, Any]) -> None:
        """Saves structured Document Identity Card to registry."""
        cls.init_db()
        with cls._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO document_identity (
                    doc_id, title, doc_type, domain, purpose,
                    key_entities, authors, doc_date, revision,
                    language, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                identity_card.get("title", ""),
                identity_card.get("doc_type", "document"),
                identity_card.get("domain", ""),
                identity_card.get("purpose", ""),
                json.dumps(identity_card.get("key_entities", [])),
                identity_card.get("authors", ""),
                identity_card.get("doc_date", ""),
                identity_card.get("revision", ""),
                identity_card.get("language", "en"),
                identity_card.get("generated_by", "local_parser")
            ))
            conn.commit()

    @classmethod
    def get_identity(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves Document Identity Card from registry."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM document_identity WHERE doc_id = ?", (doc_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("key_entities"):
                try:
                    res["key_entities"] = json.loads(res["key_entities"])
                except Exception:
                    pass
            return res

    get_identity_card = get_identity
    save_identity_card = save_identity

    @classmethod
    def save_outline(cls, doc_id: str, outline_entries: List[Dict[str, Any]]) -> None:
        """Saves hierarchical outline entries for a document."""
        cls.init_db()
        with cls._get_connection() as conn:
            conn.execute("DELETE FROM document_outline WHERE doc_id = ?", (doc_id,))
            for ordinal, entry in enumerate(outline_entries):
                conn.execute("""
                    INSERT INTO document_outline (
                        doc_id, ordinal, locator_kind, locator_index,
                        locator_label, locator_anchor, heading, level, char_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc_id,
                    ordinal,
                    entry.get("locator_kind", "page"),
                    entry.get("locator_index", 1),
                    entry.get("locator_label", str(entry.get("locator_index", 1))),
                    entry.get("locator_anchor", ""),
                    entry.get("heading", ""),
                    entry.get("level", 1),
                    entry.get("char_count", 0)
                ))
            conn.commit()

    @classmethod
    def get_outline(cls, doc_id: str) -> List[Dict[str, Any]]:
        """Retrieves ordered outline entries for a document."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_outline WHERE doc_id = ? ORDER BY ordinal ASC",
                (doc_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def save_synopsis(cls, doc_id: str, synopsis: str, source_locators: List[Dict[str, Any]], strategy: str = "full_context", generated_by: str = "gemini") -> None:
        """Saves grounded document-level synopsis."""
        cls.init_db()
        with cls._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO document_synopsis (
                    doc_id, synopsis, source_locators, strategy, generated_by
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                doc_id,
                synopsis,
                json.dumps(source_locators),
                strategy,
                generated_by
            ))
            conn.commit()

    @classmethod
    def get_synopsis(cls, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves document synopsis and source locators."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM document_synopsis WHERE doc_id = ?", (doc_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("source_locators"):
                try:
                    res["source_locators"] = json.loads(res["source_locators"])
                except Exception:
                    pass
            return res

    @classmethod
    def rebuild_registry_from_disk(cls, vector_store_dir: str) -> int:
        """Scans vector store directory to reconstruct metadata registry from index manifests and identity cards."""
        cls.init_db()
        rebuilt_count = 0
        if not os.path.exists(vector_store_dir):
            return 0

        for item in os.listdir(vector_store_dir):
            doc_dir = os.path.join(vector_store_dir, item)
            manifest_file = os.path.join(doc_dir, "index_manifest.json")
            if os.path.isdir(doc_dir) and os.path.exists(manifest_file):
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    doc_id = manifest.get("doc_id", item)
                    raw_fmt = (manifest.get("format") or "pdf").lower().lstrip(".")
                    
                    unit_count = manifest.get("unit_count")
                    unit_kind = manifest.get("unit_kind", "section" if raw_fmt in ["docx", "doc"] else ("sheet" if raw_fmt in ["xlsx", "xls", "csv"] else "page"))

                    # If unit_count is not in manifest, calculate exact page count from chunks.pkl
                    if unit_count is None and raw_fmt == "pdf":
                        chunks_pkl = os.path.join(doc_dir, "chunks.pkl")
                        if os.path.exists(chunks_pkl):
                            try:
                                with open(chunks_pkl, "rb") as cpf:
                                    loaded_chunks = pickle.load(cpf)
                                page_labels = [c.metadata.get("page_label", c.metadata.get("page", 0) + 1) for c in loaded_chunks if c.metadata.get("page_label") or c.metadata.get("page") is not None]
                                unit_count = max(page_labels) if page_labels else 1
                            except Exception:
                                unit_count = 1
                        else:
                            unit_count = 1

                    cls.register_document(
                        doc_id=doc_id,
                        content_hash=manifest.get("content_hash", f"recovered_{doc_id}"),
                        filename=manifest.get("filename", f"{doc_id}.{raw_fmt}"),
                        format_ext=raw_fmt,
                        mime_type="application/pdf" if raw_fmt == "pdf" else "application/octet-stream",
                        size_bytes=manifest.get("size_bytes", 0),
                        unit_count=unit_count,
                        unit_kind=unit_kind,
                        storage_path=manifest.get("storage_path", ""),
                        status="READY"
                    )
                    cls.update_status(doc_id, "READY", index_path=doc_dir)

                    id_file = os.path.join(doc_dir, "identity_card.json")
                    if os.path.exists(id_file):
                        with open(id_file, "r", encoding="utf-8") as id_f:
                            id_card = json.load(id_f)
                        cls.save_identity(doc_id, id_card)
                    rebuilt_count += 1
                except Exception as e:
                    print(f"[MetadataService] Failed to rebuild doc {item}: {e}")

        return rebuilt_count

    @classmethod
    def get_structural_summary(cls, doc_id: str) -> Dict[str, Any]:
        """
        Retrieves an authoritative consolidated dictionary of structural facts directly
        from the SQLite registry. Guarantees zero LLM hallucinations for structural questions.
        """
        doc = cls.get_document(doc_id)
        if not doc:
            # Auto-discover from disk if index exists
            collection_dir = os.path.join(config.VECTOR_STORE_DIR, doc_id)
            if os.path.exists(collection_dir):
                cls.rebuild_registry_from_disk(config.VECTOR_STORE_DIR)
                doc = cls.get_document(doc_id) or {}
            else:
                doc = {}

        ident = cls.get_identity(doc_id) or {}
        outline = cls.get_outline(doc_id) or []
        
        total_chars = sum(entry.get("char_count", 0) for entry in outline)
        sections = [entry.get("heading") for entry in outline if entry.get("heading")]
        
        # Check if manifest has table / image counts or unit_count
        table_count = 0
        image_count = 0
        index_path = doc.get("index_path") or os.path.join(config.VECTOR_STORE_DIR, doc_id)
        if os.path.exists(os.path.join(index_path, "index_manifest.json")):
            try:
                with open(os.path.join(index_path, "index_manifest.json"), "r", encoding="utf-8") as mf:
                    manifest_data = json.load(mf)
                    table_count = manifest_data.get("table_count", 0)
                    image_count = manifest_data.get("image_count", 0)
                    if doc.get("unit_count") is None and manifest_data.get("unit_count"):
                        doc["unit_count"] = manifest_data.get("unit_count")
            except Exception:
                pass

        unit_count = doc.get("unit_count")
        format_val = (doc.get("format") or "pdf").lower().replace(".", "")
        default_unit_kind = "section" if format_val in ["docx", "doc"] else ("sheet" if format_val in ["xlsx", "xls", "csv"] else "page")
        unit_kind = doc.get("unit_kind") or default_unit_kind

        # Fallback for unit_count if still None on a PDF
        if unit_count is None and format_val == "pdf":
            chunks_pkl = os.path.join(index_path, "chunks.pkl")
            if os.path.exists(chunks_pkl):
                try:
                    with open(chunks_pkl, "rb") as cpf:
                        loaded_chunks = pickle.load(cpf)
                    page_labels = [c.metadata.get("page_label", c.metadata.get("page", 0) + 1) for c in loaded_chunks if c.metadata.get("page_label") or c.metadata.get("page") is not None]
                    unit_count = max(page_labels) if page_labels else 1
                except Exception:
                    unit_count = 1

        return {
            "doc_id": doc_id,
            "filename": doc.get("filename", ident.get("title", f"{doc_id}.pdf")),
            "title": ident.get("title", doc.get("filename", "Active Document")),
            "unit_count": unit_count,
            "unit_kind": unit_kind,
            "section_count": len(outline),
            "sections": sections,
            "outline": outline,
            "size_bytes": doc.get("size_bytes", 0),
            "char_count": total_chars,
            "format": doc.get("format", "pdf"),
            "mime_detected": doc.get("mime_detected", "application/pdf"),
            "uploaded_at": doc.get("uploaded_at", ""),
            "authors": ident.get("authors", ""),
            "doc_date": ident.get("doc_date", ""),
            "revision": ident.get("revision", ""),
            "table_count": table_count,
            "image_count": image_count,
            "has_tables": table_count > 0 or any("table" in s.lower() for s in sections),
            "has_images": image_count > 0 or "drawing" in doc.get("format", "").lower()
        }
