# Knowledge Item: Defect 3 — Page Count Discrepancy & Registry Synchronization

## 1. Issue Description & Symptoms
- **Symptom**: When asking structural questions like `"How many pages does this document have?"` in the chat UI, the system replied:
  `"This document contains exactly 15 pages."`
  even when the uploaded PDF was a 1-page drawing, 2-page resume (`Shubham_Resume.pdf`), or 3-page report.
- **Impact**: Incorrect metadata returned to users, causing loss of trust in the grounded document intelligence capabilities.

---

## 2. Root Cause Analysis
1. **Unregistered Upload Route**:
   - In `backend/routers/pdf_router.py`, the `upload_pdf` endpoint created the vector index and processed chunks, but never called `MetadataService.register_document(...)` or `MetadataService.save_identity(...)`.
2. **Missing `unit_count` in Manifest & Rebuild Fallback**:
   - `index_manifest.json` originally stored only `chunk_count`, not `unit_count` (total pages).
   - When `MetadataService.rebuild_registry_from_disk(...)` ran, it fell back to using `chunk_count` or failed silently due to an unimported module, causing documents to have either chunk-count page counts or missing records.
3. **Hardcoded Fallback in Query Understanding**:
   - In `backend/services/query_understanding_service.py`, if `unit_count` was missing from `struct_summary`, the code evaluated:
     `unit_count = doc_meta.get("unit_count") if doc_meta else 15`
     and formatted `f"This document contains exactly {unit_count or 15} pages."`.

---

## 3. Permanent Architectural Fixes Applied
1. **Sidecar Manifest & Ingestion Synchronization**:
   - Updated [backend/services/vector_service.py](file:///d:/Program/Projects/pdf-rag-summarizer/backend/services/vector_service.py) `save_index_manifest` and `create_collection` to compute and persist `unit_count`, `unit_kind`, `filename`, and `format` into `index_manifest.json`.
2. **Upload Route Full Registration**:
   - In [backend/routers/pdf_router.py](file:///d:/Program/Projects/pdf-rag-summarizer/backend/routers/pdf_router.py), every uploaded document is immediately registered into SQLite (`documents`, `document_identity`, and `document_outline`).
3. **Dynamic Registry Auto-Discovery & Chunk Inspection**:
   - In [backend/services/metadata_service.py](file:///d:/Program/Projects/pdf-rag-summarizer/backend/services/metadata_service.py):
     - Added `import pickle`.
     - In `rebuild_registry_from_disk` and `get_structural_summary`, if `unit_count` is missing, it dynamically loads `chunks.pkl` and computes `max(page_labels)` accurately.
4. **Clean Grammar & Zero Hardcoding in Query Routing**:
   - In [backend/services/query_understanding_service.py](file:///d:/Program/Projects/pdf-rag-summarizer/backend/services/query_understanding_service.py), eliminated all hardcoded `15` fallbacks. Added proper singular/plural grammar formatting (`1 page` vs `N pages`, `1 section` vs `N sections`).

---

## 4. Regression Prevention & Test Suite Guard
- Added `TestDefect3` in [tests/test_defects.py](file:///d:/Program/Projects/pdf-rag-summarizer/tests/test_defects.py):
  - `test_defect_3_registered_page_counts_match_chunks`: Validates 1-page, 2-page, 3-page, and 15-page documents.
  - `test_defect_3_page_count_query_answers_accurately`: Validates exact string and grammar output.
  - `test_defect_3_auto_discovery_for_unregistered_collection`: Validates dynamic chunk recovery.
- Entire test suite passes **17 / 17 tests (100%)**.
