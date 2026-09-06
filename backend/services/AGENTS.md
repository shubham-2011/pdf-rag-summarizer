# backend/services/AGENTS.md

Ownership map and known traps for each backend service. Read before touching any service file.

## Ownership Map

| Service | Responsibility | Never does |
|---|---|---|
| `pdf_service.py` | PyMuPDF parsing, hierarchical semantic chunking, layout analysis | Never calls cloud LLMs or vector stores |
| `document_service.py` | Multi-format parsing (DOCX, PPTX, XLSX) and metadata extraction | Never asserts page counts for non-PDFs |
| `ingest_adapter.py` | Format detection, conversion orchestration, and container extraction | Never silently drops tables or headers |
| `vector_service.py` | FAISS index, BM25 retriever, Nomic embeddings, BGE reranker | Never imports cloud LLMs (Gemini / OpenAI) |
| `metadata_service.py` | SQLite registry, state machine lifecycle, Identity Cards | Never permits illegal state machine skips |
| `query_understanding_service.py`| Intent classifier, pronoun context, deterministic metadata routing | Never routes structural/greetings to retrieval |
| `rag_service.py` | Hybrid search assembly, synthesis prompt framing, citation formatting | Never mixes retrieval into cloud generation |
| `llm_service.py` | Gemini 1.5 / 3.5 API client, grounded prompt synthesis | Never imports local vector indices |
| `validation_service.py` | Ingestion audit rules, pre-check constraints | Never claims to validate post-synthesis facts |

---

## Known Traps by Service

### `vector_service.py`
- **Trap: Asymmetric Embedding Prefixes are Mandatory.**
  - Always use `search_document: ` when embedding chunks at index time.
  - Always use `search_query: ` when embedding user queries at search time.
  - *Failure mode*: Dropping or swapping prefixes silent degraded recall by up to 20% with zero runtime errors.
- **Trap: Manifest is a Tripwire, not Config.**
  - `index_manifest.json` checks model name, dimension (768 for Nomic), and distance metric.
  - Never edit `index_manifest.json` by hand; rebuild the collection if configuration changes.

### `document_service.py` & `ingest_adapter.py`
- **Trap: DOCX Has No Fixed Page Count.**
  - Never report "pages" for `.docx`. Read `unit_name` and `unit_count` (`paragraphs`, `sections`, `tables`).
  - Report the honest answer: Word documents have no fixed page count without a layout renderer.
- **Trap: Multi-Container Extraction.**
  - `document.paragraphs` does NOT contain tables, headers, footers, or text boxes.
  - All containers must be extracted to prevent silent data loss (especially metric tables).

### `metadata_service.py`
- **Trap: State Machine Lifecycle Transitions.**
  - Allowed transitions: `UPLOADED → PARSING → CHUNKING → INDEXED → READY`.
  - Illegal skips (e.g. `UPLOADED → READY`) must raise `ValueError`.
  - Every document must be registered immediately upon upload.

### `query_understanding_service.py`
- **Trap: No Hardcoded Document Facts.**
  - Never fallback to a hardcoded `15` or any static page number.
  - If a document is a `.docx`, `.xlsx`, or `.pptx`, format answers using its real units (`paragraphs`, `sheets`, `slides`).
- **Trap: Bypass Retrieval for Structural and Greeting Queries.**
  - Queries like "how many pages", "list sections", "hello", "thank you" must be answered directly from metadata/conversational templates. Passing them to vector retrieval creates false-refusal hallucinations.

### `rag_service.py` & `llm_service.py`
- **Trap: Synthesis Prompt is the Single Grounding Defense.**
  - There is no automatic downstream fact-checking or retry loop. The system prompt constraints (cite exact page numbers, acknowledge unanswerable probes) are the only defense against hallucinations.
