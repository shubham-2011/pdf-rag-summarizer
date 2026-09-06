# Error Log & Solution: 500 Internal Server Error in `/api/chat/query`

**Date**: September 6, 2026  
**Incident**: User experienced UI error `"Sorry, I encountered an error searching your document."` when asking global questions like `"what is this pdf for?"`.  
**Severity**: High (User-facing chat query failure)  
**Resolution Status**: Resolved & Verified  

---

## 1. Incident Diagnosis & Symptoms

### UI Symptom
In the React Chat interface (`RagChat.jsx` at `http://localhost:5173/`):
- User sent message: `"what is this pdf for?"`
- Assistant returned: `"Sorry, I encountered an error searching your document."`

### Backend Server Log
```log
INFO:     127.0.0.1:58090 - "POST /api/pdf/upload HTTP/1.1" 200 OK
INFO:     127.0.0.1:61870 - "POST /api/pdf/summarize HTTP/1.1" 200 OK
INFO:     127.0.0.1:56792 - "OPTIONS /api/chat/query HTTP/1.1" 200 OK
INFO:     127.0.0.1:56792 - "POST /api/chat/query HTTP/1.1" 500 Internal Server Error
```

---

## 2. Root Cause Analysis (RCA)

Two distinct causes contributed to the failure:

### Cause 1 — Schema Validation Mismatch on `SourceCitation` (Primary)
- In `backend/routers/chat_router.py`, the endpoint `/api/chat/query` declares response model `response_model=ChatQueryResponse`.
- In `backend/schemas.py`, `SourceCitation` was defined as:
  ```python
  class SourceCitation(BaseModel):
      page: Any
      file: str
      snippet: str
  ```
- In `backend/services/rag_service.py`, sources were constructed with:
  ```python
  sources.append({
      "id": f"c{i}",
      "page": page_str,
      "file": doc.metadata.get("source_file", "Document"),
      "text": doc.page_content,
      "origin": "pdf"
  })
  ```
- **The Defect**: `snippet` was mandatory in `SourceCitation` but `rag_service.py` emitted `text` instead of `snippet`. Pydantic validation raised `pydantic_core.ValidationError: Field required: snippet`, causing FastAPI to return HTTP 500.
- The frontend caught the 500 error in `RagChat.jsx` and displayed the generic error message.

### Cause 2 — Missing Multipart Dependency
- In the initial startup, FastAPI threw:
  `RuntimeError: Form data requires "python-multipart" to be installed.`

---

## 3. Solution & Fixes Implemented

### 1. Updated `backend/schemas.py`
Made all non-core citation fields optional and added `id`, `text`, `origin`, `url`:
```python
class SourceCitation(BaseModel):
    id: Optional[str] = None
    page: Any = "1"
    file: Optional[str] = "Document"
    text: Optional[str] = None
    snippet: Optional[str] = None
    origin: Optional[str] = "pdf"
    url: Optional[str] = None
```

### 2. Updated `backend/services/rag_service.py`
Ensured both `text` (full chunk content) and `snippet` (character-bounded summary) are populated in all source dictionaries:
```python
sources.append({
    "id": f"c{i}",
    "page": page_str,
    "file": doc.metadata.get("source_file", "Document"),
    "text": doc.page_content,
    "snippet": doc.page_content[:200] + ("..." if len(doc.page_content) > 200 else ""),
    "origin": "pdf"
})
```

### 3. Installed Required Dependencies
```bash
pip install python-multipart pymupdf rank_bm25 einops python-docx python-pptx openpyxl
```

---

## 4. Verification & Validation

Tested `/api/chat/query` live via HTTP POST:
- **Request**: `{"document_id": "test_metro_doc", "question": "what is this pdf for?"}`
- **Response**: `HTTP 200 OK`
- **Output**: Full multi-chunk synthesized explanation of document purpose and layout with 3 grounded source citations.
- **Automated Test Suite**: `scratch/test_rag_overhaul.py` passed with 100% across all 4 benchmarks (Global non-refusal, Local precision, Hallucination rejection, Page diversity).
