# Migration to Free Embedding & Retrieval Stack

This plan covers migrating the RAG retrieval backend from ChromaDB to a fully local FAISS + BM25 ensemble retriever, followed by cross-encoder reranking. We will also transition to `nomic-ai/nomic-embed-text-v1.5` as the default embedding model per your request.

## User Review Required

> [!WARNING]
> **Data Migration & Deletion**
> Switching from Chroma to FAISS means the existing vector store index is incompatible. The existing Chroma database in `faiss_index` or `vector_store` will need to be deleted, and all PDFs will require re-indexing.

> [!IMPORTANT]
> **Dependency Installations**
> We will need to run `pip install faiss-cpu sentence-transformers rank_bm25` in the backend environment.

## Open Questions

1. Do you want to use Groq or Ollama for the LLM inference as suggested in the document, or stick to the current Gemini setup via the API key? (Currently we use Gemini 1.5 Flash).
2. The document mentions using `BAAI/bge-small-en-v1.5` but you explicitly requested `nomic-ai/nomic-embed-text-v1.5`. I will set `nomic-ai/nomic-embed-text-v1.5` as the primary embedding model, which is ~550MB to download on first run. Is this correct?

## Proposed Changes

### Backend Dependencies
- Run `pip install faiss-cpu sentence-transformers rank_bm25`

### Services

#### [MODIFY] [vector_service.py](file:///d:/Program/Projects/pdf-rag-summarizer/backend/services/vector_service.py)
- Replace `langchain_chroma.Chroma` with `langchain_community.vectorstores.FAISS`.
- Implement `build_retriever` combining `FAISS` and `BM25Retriever` using `EnsembleRetriever`.
- Add `CrossEncoderReranker` with `BAAI/bge-reranker-base` to rerank the ensemble results.
- Implement the ingestion pipeline to correctly map `c{i}` and `page_label` into the `Document` metadata before adding to FAISS.
- Force `nomic-ai/nomic-embed-text-v1.5` as the embedding model.

#### [MODIFY] [rag_service.py](file:///d:/Program/Projects/pdf-rag-summarizer/backend/services/rag_service.py)
- Refactor `compute_hybrid_rrf` to use the new `ContextualCompressionRetriever` from `VectorService` instead of manually doing RRF scoring between BM25 and Chroma.
- Ensure the `retrieve` logic maps the retrieved documents directly into the required UI format `[c0]`, etc.

## Verification Plan

### Automated Tests
- Run `pytest` to ensure all extraction and routing logic still functions correctly.

### Manual Verification
- Upload a new PDF to trigger FAISS ingestion.
- Ask a local/extractive question (e.g. "what is the transformer rating") to verify that the ensemble retriever + reranker pipeline returns highly relevant chunks.
- Verify that the frontend citation panel receives correct `c{i}` IDs and 1-indexed pages.
