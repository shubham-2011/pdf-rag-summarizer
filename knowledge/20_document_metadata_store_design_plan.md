# 🏛️ Design Plan — Document Metadata Store

**Purpose**: A single authoritative record of every ingested document, separate from the vector index.  
**Scope**: System design, data tiers, schema specification, ingestion state machine, consistency rules, and implementation phasing.

---

## 1. Problem Statement & Motivation

Prior to this specification, document metadata and state were scattered and partly implicit across the stack:

| What | Previous State | Problem |
|---|---|---|
| Which documents exist | Filesystem directory listing | No status, no provenance, no transaction safety |
| Page / Locator per chunk | FAISS docstore metadata | Correct place, but unvalidated |
| BM25 corpus | `chunks.pkl` sidecar / docstore rebuild | Not discoverable, no strict schema |
| **Embedding model used for index** | **Unrecorded** | **Silent retrieval corruption on model/dim change** |
| Document identity / synopsis | Ephemeral or recomputed per query | Inconsistent quality, unnecessary latency |
| Ingestion lifecycle status | Inferred from directory existence | Crashed/half-written indices falsely treated as ready |
| Chat history | Browser `localStorage` | Device-locked, not queryable, no evaluation dataset |

### The Critical Gap: Index Manifest
The most critical vulnerability is the lack of an immutable record of **which embedding model and prefix configuration built a given index**. Loading a Nomic-built index with another model (or without asymmetric prefixes) produces zero runtime errors while silently corrupting retrieval rank precision.

---

## 2. Three Tiers of Metadata Separation

```
┌──────────────────────────────────────────────────────────────────┐
│                   TIER 1: DOCUMENT REGISTRY                      │
│                  (SQLite: metadata.db / WAL)                     │
│  • documents (doc_id, hash, status, unit_count, format)          │
│  • document_identity (title, domain, purpose, key_entities)     │
│  • document_synopsis (synopsis, source_locators, strategy)       │
│  • document_outline (sections, headings, locators, char_count)   │
│  • workspaces & workspace_documents                              │
└─────────────────────────────────┬────────────────────────────────┘
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
┌───────────────────────────┐                   ┌───────────────────────────┐
│  TIER 2: CHUNK METADATA   │                   │  TIER 3: INDEX MANIFEST   │
│ (FAISS Docstore / Vectors)│                   │   (index_manifest.json)   │
│                           │                   │                           │
│ • doc_id, chunk_id        │                   │ • doc_id, embedding_model │
│ • locator (page / block)  │                   │ • embedding_dims (768)    │
│ • section_heading         │                   │ • doc/query prefixes      │
│ • block_type (text/table) │                   │ • normalized, chunk_count │
│                           │                   │ • builder_version         │
│ (Denormalized for zero-   │                   │ (Checked BEFORE loading   │
│  latency citation hotpath)│                   │  index into memory)       │
└───────────────────────────┘                   └───────────────────────────┘
```

---

## 3. Storage Architecture: SQLite with WAL

- **Engine**: SQLite (zero-ops, single-file, embedded in Python standard library).
- **Location**: `backend/data/metadata.db` alongside `vector_stores/`.
- **Concurrency & Locking Mitigations**:
  - `PRAGMA journal_mode=WAL;`
  - `PRAGMA busy_timeout=5000;` (5-second wait on lock contention)
  - `PRAGMA synchronous=NORMAL;`
  - Single-service write access in FastAPI backend.

---

## 4. Database & File Schemas

### 4.1 `documents` (Ingestion Master Table)
```sql
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    content_hash TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    mime_detected TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    unit_count INTEGER NOT NULL,
    unit_kind TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    error_message TEXT,
    storage_path TEXT NOT NULL,
    index_path TEXT
);
```

### 4.2 `document_identity` (Structural & Semantic Identity Card)
```sql
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
```

### 4.3 `document_synopsis` (Grounded Global Summary)
```sql
CREATE TABLE IF NOT EXISTS document_synopsis (
    doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id) ON DELETE CASCADE,
    synopsis TEXT NOT NULL,
    source_locators JSON NOT NULL,
    strategy TEXT NOT NULL,
    generated_by TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_version INTEGER DEFAULT 1
);
```

### 4.4 `document_outline` (Hierarchical Structure & Sections)
```sql
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
```

### 4.5 `index_manifest.json` (Per-Collection Sidecar)
Stored at `<VECTOR_STORE_DIR>/<doc_id>/index_manifest.json`:
```json
{
  "doc_id": "doc_12345",
  "embedding_model": "nomic-ai/nomic-embed-text-v1.5",
  "embedding_dims": 768,
  "document_prefix": "search_document: ",
  "query_prefix": "search_query: ",
  "normalized": true,
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "splitter_version": "human_centric_v2",
  "chunk_count": 42,
  "bm25_indexed": true,
  "built_at": "2026-09-06T15:00:00Z",
  "builder_version": "1.0.0"
}
```

**Load Rule**: Compare `index_manifest.json` with active system config. If `embedding_model`, `embedding_dims`, or `prefixes` mismatch $\rightarrow$ **refuse to load index, raise `IncompatibleIndexError`, and flag document as `STALE`.**

### 4.6 `workspaces` & `workspace_documents`
```sql
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
```

---

## 5. Ingestion State Machine

```
UPLOADED ──► VALIDATING ──► PARSING ──► CHUNKING ──► EMBEDDING ──► INDEXED
    │             │            │           │            │             │
    └─────────────┴────────────┴───────────┴────────────┴─────────────┴──► FAILED
                                                                          
INDEXED ──► ENRICHING ──► READY        (Identity Card + Synopsis; non-blocking)
READY   ──► STALE                      (Manifest mismatch on config change)
```

1. **`READY` Constraint**: Only documents in `READY` (or `INDEXED` fallback) can be queried.
2. **Non-blocking `ENRICHING`**: Local retrieval is usable as soon as `INDEXED` completes. Gemini-powered identity card and synopsis enrichment execute asynchronously.
3. **Deterministic `FAILED` States**: Pre-audit failures (size, encryption, empty, scanned/zero-text) set explicit error codes.
4. **Deduplication**: `content_hash` collision reuses existing index without redundant embedding calls.

---

## 6. Implementation Phasing Matrix

| Phase | Target Deliverable | Core Value |
|---|---|---|
| **Phase 1** | `index_manifest.json` sidecar + load-time verification check | **Stops silent retrieval corruption on model/dim mismatch.** |
| **Phase 2** | `documents` master table + Ingestion state machine | Prevents querying half-written/corrupt indices. |
| **Phase 3** | `document_identity` schema & persistence | Unlocks META intent queries, typo expansion, and classifier context. |
| **Phase 4** | `document_synopsis` schema with `source_locators` | Citable macro-level global answers. |
| **Phase 5** | `document_outline` schema | Enables section-scoped summarization & queries. |
| **Phase 6** | `workspaces` multi-doc relationships | Multi-document collection isolation. |
| **Phase 7** | Server-side `chat_messages` + user feedback | Captures real evaluation datasets from user thumbs up/down. |

---

## 7. Verification & Test Suite Requirements

1. **Model Mismatch Rejection**: Loading an index built with `nomic-v1.5` under a different configuration must raise a named exception with mismatched attributes.
2. **Missing Prefix Detection**: Manifests missing `document_prefix` fail validation rather than defaulting silently.
3. **Interrupted Index Isolation**: A crash during embedding leaves document in `FAILED` / `EMBEDDING`, preventing retrieval.
4. **Deduplication Test**: Re-uploading identical file bytes reuses existing `doc_id` and index.
5. **Registry Recovery**: Deleting `metadata.db` and scanning index directories allows full registry reconstruction from `index_manifest.json` and `identity_card.json`.
