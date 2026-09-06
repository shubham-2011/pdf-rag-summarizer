# Walkthrough: Free Embedding & Retrieval Stack + UI Fixes

I have successfully completed the migration of the RAG retrieval backend to the completely free, local FAISS and BM25 ensemble retriever stack. I have also implemented the Phase 1 UI updates you requested for the citation panel.

## Changes Made

### 1. UI Fix Roadmap (Phase 1)
- **Real Page Numbers**: Modified `rag_service.py` and `RagChat.jsx` to parse and render `page_label` from the metadata. Citations now display `p.1`, `p.2`, etc., corresponding to actual document pages rather than array indices.
- **Word-Boundary Truncation**: Added a `snippet()` helper function in `RagChat.jsx` that slices chunk text safely without cutting mid-word, appending an ellipsis gracefully.
- **Cited-Only Filtering**:
  - The system prompt now instructs the LLM to output citations in the form of `[c0]`, `[c1]`.
  - The frontend dynamically parses the `[c\d+]` markers from the LLM's Markdown answer and filters the citation panel to *only* display the sources that were actually cited by the LLM.

### 2. FAISS Migration & Reranking
- **Replaced Chroma with FAISS**: The `VectorService` has been completely rewritten to ingest documents into a `langchain_community.vectorstores.FAISS` docstore.
- **Ensemble Retrieval**: Implemented `build_retriever` which combines a Sparse (BM25) retriever and Dense (FAISS) retriever at a 50/50 weighting using `EnsembleRetriever`.
- **CrossEncoder Reranking**: The ensemble candidates are passed through a `ContextualCompressionRetriever` powered by `BAAI/bge-reranker-base`, significantly boosting semantic relevance.
- **Embedding Model**: As explicitly requested, the system now forces the use of `nomic-ai/nomic-embed-text-v1.5` for document embeddings.

## What to Test

> [!WARNING]
> Because we switched from ChromaDB to FAISS, your existing PDFs will need to be **re-uploaded** to trigger ingestion and create the new FAISS indices.

1. **Upload a PDF**: You will see a one-time download of the new `nomic` and `bge-reranker` models from HuggingFace in your backend logs.
2. **Ask a question**: Try a local/extractive question (e.g., "what is the transformer rating").
3. **Verify the UI**: Check that the answer includes `[c0]` style citations and that the citation panel only shows the corresponding sources, with correct word truncations and page numbers.

All changes are live and running on the development server.
