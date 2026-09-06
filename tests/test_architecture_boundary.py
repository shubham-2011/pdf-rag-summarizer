import os
import unittest
from langchain_core.documents import Document
from backend.services.vector_service import (
    VectorService,
    NomicHuggingFaceEmbeddings,
    _assert_local_embeddings,
)

def test_hosted_embeddings_boundary_guard_raises_error():
    """Verify that hosted embeddings trigger the architecture boundary violation error."""
    class GoogleGenerativeAIEmbeddings:
        pass

    class OpenAIEmbeddings:
        pass

    try:
        _assert_local_embeddings(GoogleGenerativeAIEmbeddings())
        raise AssertionError("Failed to raise on GoogleGenerativeAIEmbeddings")
    except RuntimeError as e:
        assert "Architecture Boundary Violation" in str(e)

    try:
        _assert_local_embeddings(OpenAIEmbeddings())
        raise AssertionError("Failed to raise on OpenAIEmbeddings")
    except RuntimeError as e:
        assert "Architecture Boundary Violation" in str(e)


def test_nomic_asymmetric_prefixes():
    """Verify that Nomic embeddings apply search_document: and search_query: prefixes."""
    class DummyBaseEmbeddings:
        def __init__(self):
            self.last_docs = []
            self.last_query = ""

        def embed_documents(self, texts):
            self.last_docs = texts
            return [[0.1, 0.2] for _ in texts]

        def embed_query(self, text):
            self.last_query = text
            return [0.1, 0.2]

    emb = NomicHuggingFaceEmbeddings.__new__(NomicHuggingFaceEmbeddings)
    emb.doc_prefix = "search_document: "
    emb.query_prefix = "search_query: "
    emb._base = DummyBaseEmbeddings()

    docs = ["Transformer architecture overview", "search_document: Already prefixed text"]
    emb.embed_documents(docs)
    assert emb._base.last_docs[0] == "search_document: Transformer architecture overview"
    assert emb._base.last_docs[1] == "search_document: Already prefixed text"

    emb.embed_query("How does attention work?")
    assert emb._base.last_query == "search_query: How does attention work?"


def test_offline_retrieval_without_api_keys(tmp_path, monkeypatch):
    """Retrieval layer must complete parsing, indexing, and querying without any API keys."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    test_docs = [
        Document(
            page_content="Electrical power rating of transformers is specified in kVA.",
            metadata={"source_file": "manual.pdf", "page": 1, "page_label": 1}
        ),
        Document(
            page_content="Secondary winding voltage ratio determines step-up or step-down behavior.",
            metadata={"source_file": "manual.pdf", "page": 2, "page_label": 2}
        ),
    ]

    collection_name = "test_boundary_collection"
    
    # Ingest into local FAISS + BM25 index
    store = VectorService.create_collection(test_docs, collection_name=collection_name)
    assert store is not None

    # Build hybrid retriever and test query
    retriever = VectorService.build_retriever(collection_name=collection_name, chunks=test_docs, k=2, rerank=False)
    assert retriever is not None
    
    results = retriever.invoke("transformer kVA power rating")
    assert len(results) > 0
    contents = [r.page_content for r in results]
    assert any("kVA" in c for c in contents), f"Expected 'kVA' in retrieved chunks, got: {contents}"
    print(f" [PASSED] test_offline_retrieval_without_api_keys passed successfully. Retrieved {len(results)} chunks.")


if __name__ == "__main__":
    print("Running Architecture Boundary Tests...")
    test_hosted_embeddings_boundary_guard_raises_error()
    print(" [PASSED] test_hosted_embeddings_boundary_guard_raises_error")
    test_nomic_asymmetric_prefixes()
    print(" [PASSED] test_nomic_asymmetric_prefixes")
    test_offline_retrieval_without_api_keys(None, type("DummyMonkeypatch", (), {"delenv": lambda self, k, raising=False: os.environ.pop(k, None)})())
    print("\nALL ARCHITECTURE BOUNDARY TESTS PASSED 100%!")
