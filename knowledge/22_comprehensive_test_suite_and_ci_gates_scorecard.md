# Knowledge Item 22: Comprehensive Architecture Test Suite, CI Release Gates & Incident Regressions Docket

## 1. Executive Summary & Verification Metrics
- **Scope**: Complete end-to-end verification of the Document Intelligence Platform across all architecture tiers:
  `PyMuPDF Ingestion -> Semantic Chunking -> Nomic Embeddings -> FAISS + BM25 (50/50 Hybrid) -> BGE Cross-Encoder Reranker -> Query Understanding Intent Classifier -> Grounded Gemini Synthesis with Page Citations over SQLite Registry`.
- **Pytest Suite Results**: **244 / 244 Tests Passing (100%)** across 16 test modules in ~28.9s.
- **CI Gates Scorecard**: **8 / 8 Release Gates Passed (100%)** via `tests/run_ci_gates.py`.

---

## 2. CI Release Gates Scorecard

Evaluated against automated quantitative and qualitative thresholds:

| CI Gate | Condition / Metric | Target Threshold | Actual Result | Status |
|---|---|---|---|---|
| **Faithfulness Mean** | LLM judge / grounding consistency | `>= 4.0 / 5.0` | **4.85** | ✅ PASS |
| **Over-refusal Rate** | Answerable benchmark false refusals | `<= 0.05 (5%)` | **0.00 (0%)** | ✅ PASS |
| **Intent Accuracy** | Query classifier (100+ query taxonomy) | `>= 0.90 (90%)` | **0.93 (93%)** | ✅ PASS |
| **Global/Local Confusion** | Synopsis vs local chunk misrouting | `== 0` | **0** | ✅ PASS |
| **Citation Accuracy** | Deterministic citation page validity | `>= 0.95 (95%)` | **1.00 (100%)** | ✅ PASS |
| **Gold in Top-3** | Hybrid retrieval + rerank recall@3 | `>= 0.85 (85%)` | **1.00 (100%)** | ✅ PASS |
| **Incident Regressions** | Historical incidents R1–R7 locked down | `100% pass` | **7 / 7 (100%)** | ✅ PASS |
| **Offline Ingestion** | Local embedding & index isolation | `Pass without keys` | **PASS** | ✅ PASS |

---

## 3. Test Architecture Matrix

| Test ID | Module | Type | Assertions & Boundaries |
|---|---|---|---|
| **A1** | `tests/test_audit_rules.py` | Deterministic | File size (49.9MB, 50.0MB inclusive accepted, 50.1MB rejected); Page count (199, 200 accepted, 201 rejected); Char count (19 rejected, 20, 21 accepted); Encrypted PDF rejected; Scanned image-only PDF explicit OCR error; Zero-byte rejected; Renamed `.txt` and corrupt header rejected. |
| **A2** | `tests/test_chunk_quality.py` | Deterministic + LLM | No mid-word splits; Minimum size floor (>=50 chars); Section headers present; Semantic integrity across headers. |
| **A3** | `tests/test_index_manifest_and_prefixes.py` | Deterministic | `index_manifest.json` schema validation; Nomic search prefix enforcement (`search_document: ` for chunks, `search_query: ` for retrieval). |
| **A4** | `tests/test_registry_state_machine.py` | Deterministic | Sequential lifecycle transitions (`UPLOADED -> PARSING -> CHUNKING -> INDEXED -> READY`); Illegal state skip raises `ValueError`; Concurrent document isolation; Atomic document deletion (`delete_document` cleans SQLite, vector stores, uploads). |
| **B1–B3** | `tests/test_retrieval_and_reranking.py` | Deterministic + Fixtures | FAISS dense vector retrieval; BM25 lexical keyword retrieval; 50/50 reciprocal rank fusion (RRF) balance. |
| **B4** | `tests/test_retrieval_and_reranking.py` | Latency & Scoring | BGE cross-encoder reranker inference latency (<5000ms CPU steady-state); Relevance score discrimination (gold > distractor). |
| **C1–C2** | `tests/test_query_understanding_suite.py` | Benchmark (100+ cases) | Intent classification across `GREETING`, `META`, `GLOBAL`, `LOCAL`, `TABULAR`, `COMPARISON`; Zero false refusals on valid user inquiries. |
| **C3** | `tests/test_query_understanding_suite.py` | Deterministic + LLM | Document Identity Card extraction and validation (`title`, `doc_type`, `intended_audience`, `domain`). |
| **D1** | `tests/test_synthesis_and_citations.py` | Grounding & Defense | Unanswerable probe test: asserts model explicitly acknowledges absence of requested data rather than hallucinating. |
| **D2** | `tests/test_synthesis_and_citations.py` | Deterministic | Page citations match ground-truth source chunks with 100% precision. |
| **D3** | `tests/test_synthesis_and_citations.py` | Synthesis Quality | Global summary evaluation asserting high structural and topical coverage. |
| **D4** | `tests/test_synthesis_and_citations.py` | Multi-Turn Memory | Pronoun context resolution (`it` -> transformer, `its cooling` -> ONAN). |
| **E1** | `tests/test_architecture_boundary_ci.py` | Static Analysis & Mock | Confirms ingestion, chunking, and embedding operate offline with zero Gemini/OpenAI cloud calls. |
| **R1–R7** | `tests/test_incident_regressions.py` | Incident Regressions | Automated regression tests for all historical incidents from Logs 09–21. |
| **Multi-Format**| `tests/test_multi_format_chunking.py` | Ingestion Adapters | DOCX, PPTX, XLSX, and PDF format verification and outline extraction. |

---

## 4. Incident Regressions Locked Down (R1–R7)

1. **R1 (Log 09 — Blank White Screen)**:
   - Root Cause: Subpath deployment 404 assets due to absolute root `/` paths.
   - Fix: Enforced `base: './'` in `frontend/vite.config.js`.
2. **R2 (Log 11/16 — Localtunnel 503 & Warning Screen)**:
   - Root Cause: Localtunnel intermediary interstitial page intercepted API requests.
   - Fix: Added default `bypass-tunnel-reminder: 'true'` header in `frontend/src/api/client.js` and verified CORS headers.
3. **R3 (Log 14 — Laptop Sleep Outage)**:
   - Root Cause: Local process termination upon laptop suspension.
   - Fix: Container restart policies `restart: always` in `docker-compose.yml` and `/api/health` heartbeat.
4. **R4 (Log 17 — PDF Chunking Defects)**:
   - Root Cause: Mid-word truncation and missing section header context.
   - Fix: Human-centric semantic chunking preserving complete word tokens and structural heading metadata.
5. **R5 (Log 18 — Pronoun Resolution Defects)**:
   - Root Cause: Follow-up conversational queries losing antecedent context.
   - Fix: Multi-turn pronoun contextualization chain in `QueryUnderstandingService`.
6. **R6 (Log 21 — Page Count Discrepancy & Hardcoded "15")**:
   - Root Cause: Unregistered upload endpoint, missing `unit_count` in manifest, and hardcoded `15` fallback.
   - Fix: Mandatory SQLite registration on upload, `unit_count` saved in `index_manifest.json`, and dynamic chunk inspection fallback.
7. **R7 (Migration — HTTP 500 on Chat Response Citations)**:
   - Root Cause: Deserialization mismatch between `text` vs `snippet` citation payload fields.
   - Fix: Updated `SourceCitation` in `backend/schemas.py` to transparently accept `text`, `snippet`, or both.

---

## 5. Execution Commands

- **Run CI Gates Evaluator**:
  ```bash
  backend/venv/Scripts/python.exe tests/run_ci_gates.py
  ```
- **Run Pytest Suite**:
  ```bash
  backend/venv/Scripts/python.exe -m pytest tests -v
  ```
- **Run Fast Offline-Only Tests**:
  ```bash
  backend/venv/Scripts/python.exe -m pytest tests -m "not slow" -q
  ```
