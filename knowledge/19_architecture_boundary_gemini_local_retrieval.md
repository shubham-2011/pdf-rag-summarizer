# 🏛️ Architecture Boundary — Gemini for Generation, Local for Retrieval

**Permanent Decision**: Gemini handles generation and conversational synthesis only. Document embedding, indexing, and retrieval remain 100% local and offline.

---

## 1. The Architectural Line

```
┌───────────────────────── LOCAL / OFFLINE ─────────────────────────┐
│                                                                   │
│  Parse (PyMuPDF) → Chunk → Embed (Nomic) → FAISS + BM25 → BGE     │
│                                                                   │
│  • 100% Offline / Runs on CPU                                     │
│  • No network connection required for indexing                    │
│  • No API keys required for ingestion                             │
│  • Asymmetric prefixes enforced (search_document / search_query)  │
└──────────────────────────────────┬────────────────────────────────┘
                                   │
                                   │ Retrieved Chunks & Page Citations (Text)
                                   ▼
┌───────────────────────── GEMINI (Cloud API) ───────────────────────┐
│                                                                   │
│  Intent Classification → Query Normalization → Answer Synthesis   │
│                                                                   │
│  • Text in, text out                                              │
│  • Never touches or instantiates the vector index                 │
└───────────────────────────────────────────────────────────────────┘
```

| Concern | Owner | Policy |
|---|---|---|
| PDF / Office parsing | PyMuPDF, python-docx, python-pptx | Local / Offline |
| Chunking & Layout | Local Semantic Splitter | Local / Offline |
| **Embedding** | `nomic-embed-text-v1.5` | **Strictly Local, Never Cloud/Gemini** |
| Vector Index | FAISS (Local Disk) | Local / Offline |
| Keyword Index | BM25 (`rank_bm25`) | Local / Offline |
| Reranking | `BAAI/bge-reranker-base` | Local / Offline |
| Intent Classification | Gemini (Flash) | Cloud API |
| Query Normalization | Gemini (Flash) | Cloud API |
| Answer Synthesis | Gemini (Flash / Pro) | Cloud API |
| Document Roadmap & Summaries | Gemini (Flash / Pro) | Cloud API |

---

## 2. Rationale & Economic Justification

1. **Volume Economics**: Ingesting a 200-page document produces thousands of chunk embeddings, and every re-index produces thousands more. Generation is low-volume (1 call per user query). Putting high-volume embedding on local CPU and low-volume synthesis on cloud LLMs is economically optimal.
2. **Eliminating Index Invalidation**: Hosted embedding version changes or endpoint retirements invalidate stored vector indices. Keeping local `nomic-embed-text-v1.5` weights ensures 100% deterministic vectors across the application lifecycle.
3. **Decoupled Generation Flexibility**: Cloud LLM providers (Gemini Flash, Pro, or local open-source models) can be swapped via configuration without touching stored FAISS vector indices.

---

## 3. Hard Boundary Rules

1. **Zero Hosted Embeddings**: No `GoogleGenerativeAIEmbeddings`, `OpenAIEmbeddings`, or `CohereEmbeddings` may ever be instantiated in the vector store pipeline.
2. **Clean Dependency Separation**: `backend/services/vector_service.py` must never import from `llm_service.py`, `google-genai`, or `langchain-google-genai`.
3. **Nomic Asymmetric Prefixes**:
   - `search_document: ` for all indexed chunks.
   - `search_query: ` for all query embeddings.
4. **Offline Ingestion Guarantee**: Document parsing, chunking, and FAISS indexing must succeed on a completely offline machine.

---

## 4. Global Query Strategy

| Query Intent | Document Scope | Processing Path | Rationale |
|---|---|---|---|
| **Global / Macro Summary** | Small ($\le 50\text{ pages}$) | **Full Document Context $\rightarrow$ Gemini** | Reads entire text in Gemini's large context window, eliminating fragment reassembly issues. |
| **Global Roadmap / Outline** | Large ($> 50\text{ pages}$) | **Document Identity Card + Top Section Chunks** | Structural macro-overview without exceeding context limits. |
| **Granular / Fact-Finding** | Any Document | **Local Hybrid Ensemble (FAISS + BM25) + BGE Reranker** | Retrieves top 6 precise chunks with exact page numbers for grounded citation answers. |

---

## 5. Failure Isolation Matrix

| Failure Event | System Impact | Unaffected Components |
|---|---|---|
| Gemini API Outage / Rate Limit | Chat returns clean provider error | Document upload, audit, and FAISS indexing work normally |
| API Key Missing / Expired | Chat displays API key prompt | Retrieval, FAISS store, and BM25 index remain fully queryable |
| FAISS Index Corruption | Single document index rebuilt locally | Other document collections and LLM synthesis layer |
| Offline / No Internet | Ingestion and local indexing succeed | Cloud chat synthesis (requires reconnection) |
