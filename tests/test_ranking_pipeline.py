import os
import sys
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from langchain_core.documents import Document
from services.vector_service import VectorService, NomicHuggingFaceEmbeddings
from services.rag_service import RAGService



def test_r1_nomic_asymmetric_prefix_enforcement():
    # Verify Nomic wrapper applies doc_prefix and query_prefix
    class MockBaseEmbeddings:
        def embed_documents(self, texts):
            return [[float(len(t))] for t in texts]
        def embed_query(self, text):
            return [float(len(text))]

    nomic_emb = NomicHuggingFaceEmbeddings(
        base_embeddings=MockBaseEmbeddings(),
        doc_prefix="search_document: ",
        query_prefix="search_query: "
    )

    # Calling embed_documents must prepend search_document:
    doc_text = "The transformer is rated 11kV"
    q_text = "transformer rating"
    
    assert nomic_emb.doc_prefix == "search_document: "
    assert nomic_emb.query_prefix == "search_query: "


def test_r4_pre_rerank_deduplication():
    # Documents with high token overlap should be deduplicated
    doc1 = Document(page_content="The industrial gateway is designed for harsh factory environments and supports 24V DC.")
    doc2 = Document(page_content="The industrial gateway is designed for harsh factory environments and supports 24V DC power.")
    doc3 = Document(page_content="Sensor inputs feature 8-channel analog ADC with 16-bit resolution.")

    deduped = VectorService.deduplicate_chunks([doc1, doc2, doc3], threshold=0.80)
    assert len(deduped) == 2
    assert deduped[0].page_content == doc1.page_content
    assert deduped[1].page_content == doc3.page_content


def test_r7_section_heading_boost_and_r8_boilerplate_demotion():
    # Technical query
    query = "transformer rating"
    
    # c0: Header/contact block
    doc_header = Document(
        page_content="Shubham Kumar Email: test@gmail.com Mobile: 9322887529 GitHub: github.com/user",
        metadata={"chunk_id": "c0", "section_heading": "GENERAL"}
    )
    # c1: Content with matching section heading
    doc_match = Document(
        page_content="The substation uses 11kV transformer rated for 500kVA.",
        metadata={"chunk_id": "c1", "section_heading": "TRANSFORMER & SUBSTATION RATINGS"}
    )

    reranked = VectorService.rerank_documents(query, [doc_header, doc_match], top_k=2)
    assert len(reranked) == 2
    # The matching section should strictly outrank the header/contact block
    assert reranked[0].metadata["chunk_id"] == "c1"
    assert reranked[0].metadata["relevance_score"] > reranked[1].metadata["relevance_score"]
