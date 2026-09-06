# 📝 Change & Decision Log (Memory Storage)

## Log Entry: 2026-07-27
### Changes & Architecture Evolution
1. **Repository Restructuring**: Created dedicated `knowledge/` memory directory storing full architecture docs, master roadmap, API contracts, and decision history.
2. **FastAPI Backend Infrastructure**:
   - Built a modular FastAPI backend in `backend/`.
   - Separated services: `pdf_service.py`, `vector_service.py`, `summarizer_service.py`, `rag_service.py`.
   - Implemented CORS middleware supporting React frontend integration (`http://localhost:5173`).
   - Standardized Pydantic schemas for request/response payloads.
3. **React Frontend (Vite UI)**:
   - Built a modern, tabbed single-page application using React & CSS.
   - Components created:
     - `PdfUploader`: Drag & drop upload with loading progress.
     - `SummaryRoadmapView`: Formatted markdown rendering for summary & action roadmap.
     - `RagChat`: Real-time Q&A interface with interactive source citation expanders.

## Log Entry: 2026-09-06
### Comprehensive Architecture Test Suite, CI Release Gates & Incident Regressions
1. **Complete Test Suite Implementation (244 / 244 Tests Passing)**:
   - **Section A (A1–A4)**: Ingestion audit boundaries, semantic chunk quality, vector index manifest & Nomic search prefixes, registry state machine (`UPLOADED -> PARSING -> CHUNKING -> INDEXED -> READY`) and atomic document deletion.
   - **Section B (B1–B4)**: Hybrid retrieval (FAISS + BM25 50/50 balance) and BGE cross-encoder reranking latency & scoring validation.
   - **Section C (C1–C3)**: Query understanding intent classifier benchmark (100+ cases across GREETING, META, GLOBAL, LOCAL, TABULAR, COMPARISON), Document Identity Card validation.
   - **Section D (D1–D4)**: Grounded Gemini synthesis, unanswerable probe hallucination defense, page citation accuracy, global synopsis synthesis, and multi-turn pronoun contextualization.
   - **Section E (E1)**: Local/Cloud architecture boundary static analysis and offline ingestion verification (zero external API calls during ingestion/retrieval).
   - **Section R (R1–R7)**: Incident regression guards permanently locking down Log 09 blank screen, Log 11/16 tunnel 503, Log 14 sleep outage/Docker restart, Log 17 chunk cuts, Log 18 pronoun resolution, Log 21 page count defect, and migration HTTP 500 citation deserialization.
2. **CI Release Scorecard Runner (`tests/run_ci_gates.py`)**:
   - Built offline evaluator for automated CI gating across 8 release thresholds with 100% pass rate.
3. **Core Pipeline Fixes & Hardening**:
   - `backend/schemas.py`: `SourceCitation` accepts both `text` and `snippet` fields.
   - `backend/services/pdf_service.py`: Enforced `%PDF` magic bytes and descriptive scanned-image OCR rejection messages.
   - `backend/services/metadata_service.py`: State machine transition enforcement and full cascaded document deletion (`delete_document`).
   - `backend/services/rag_service.py`: Intermediate document processing status guard.
   - `backend/services/query_understanding_service.py`: Enhanced pattern recognition for intent classification without false refusals.
   - `frontend/src/api/client.js`: Default `bypass-tunnel-reminder: true` request header.
   - `config.py`: Root configuration synchronized with backend constraints.
