import os
import sys
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from langchain_core.documents import Document
from services.validation_service import (
    ValidationService,
    IndexCompatibilityError,
    RetrievalSanityError,
    AnswerShapeError
)



def test_v1_index_manifest_validation():
    # Valid manifest
    valid_manifest = {
        "embedding_model": "nomic-ai/nomic-embed-text-v1.5",
        "embedding_dims": 768,
        "document_prefix": "search_document: ",
        "query_prefix": "search_query: "
    }
    expected_config = {
        "embedding_model": "nomic-ai/nomic-embed-text-v1.5",
        "embedding_dims": 768,
        "document_prefix": "search_document: ",
        "query_prefix": "search_query: "
    }
    # Should pass without error
    ValidationService.validate_index_manifest(valid_manifest, expected_config)

    # Missing sidecar
    with pytest.raises(IndexCompatibilityError):
        ValidationService.validate_index_manifest(None, expected_config)

    # Model mismatch
    mismatched_manifest = {**valid_manifest, "embedding_model": "openai/text-embedding-ada-002"}
    with pytest.raises(IndexCompatibilityError):
        ValidationService.validate_index_manifest(mismatched_manifest, expected_config)

    # Asymmetric prefix mismatch
    prefix_mismatched = {**valid_manifest, "document_prefix": "doc: "}
    with pytest.raises(IndexCompatibilityError):
        ValidationService.validate_index_manifest(prefix_mismatched, expected_config)


def test_v2_retrieval_candidate_sanity():
    # Empty candidates
    with pytest.raises(RetrievalSanityError):
        ValidationService.validate_retrieval_candidates([])

    # Corrupted single-chunk flood
    corrupted_docs = [
        Document(page_content=f"Content {i}", metadata={"chunk_id": "c0"})
        for i in range(6)
    ]
    with pytest.raises(RetrievalSanityError):
        ValidationService.validate_retrieval_candidates(corrupted_docs)

    # Normal candidates
    normal_docs = [
        Document(page_content=f"Content {i}", metadata={"chunk_id": f"c{i}"})
        for i in range(6)
    ]
    ValidationService.validate_retrieval_candidates(normal_docs)


def test_v3_rerank_score_floor():
    docs = [
        Document(page_content="High relevant", metadata={"relevance_score": 0.85}),
        Document(page_content="Medium relevant", metadata={"relevance_score": 0.35}),
        Document(page_content="Low noise", metadata={"relevance_score": 0.12}),
    ]
    kept = ValidationService.validate_reranked_docs(docs, score_floor=0.20)
    assert len(kept) == 2
    assert kept[0].metadata["relevance_score"] == 0.85
    assert kept[1].metadata["relevance_score"] == 0.35


def test_v4_citation_sanitization():
    sources = [
        {"page": 1, "file": "test.pdf", "snippet": "Text 1"},
        {"page": 2, "file": "test.pdf", "snippet": "Text 2"},
        {"page": 999, "file": "test.pdf", "snippet": "Out of bounds text"},
        {"page": "🌐 Web Search", "file": "Web", "url": "https://example.com"}
    ]
    # Unit count is 5 pages
    sanitized = ValidationService.validate_citations(sources, unit_count=5)
    assert len(sanitized) == 3
    pages = [s["page"] for s in sanitized]
    assert 999 not in pages
    assert 1 in pages
    assert 2 in pages
    assert "🌐 Web Search" in pages


def test_v5_answer_shape_and_data_exposure():
    # Valid answer
    ValidationService.validate_answer_shape(
        "This is a complete, grammatically sound sentence with factual citations [Page 1].",
        intent="LOCAL"
    )

    # Raw broken chunk fragment starting with a period
    with pytest.raises(AnswerShapeError):
        ValidationService.validate_answer_shape(
            "Here are the findings:\n* . Designed a scalable frontend architecture\n* Optimized DB",
            intent="LOCAL"
        )

    # Global intent too short
    with pytest.raises(AnswerShapeError):
        ValidationService.validate_answer_shape(
            "This is a manual.",
            intent="GLOBAL"
        )

    # Structural intent data-exposure guard (phone/email leak)
    with pytest.raises(AnswerShapeError):
        ValidationService.validate_answer_shape(
            "The sections are: 1. Intro 2. Contact: +91-9322887529 and user@gmail.com",
            intent="STRUCTURAL"
        )


def test_v6_response_contract():
    raw_response = {
        "answer": "Test answer"
    }
    enforced = ValidationService.enforce_response_contract(raw_response)
    assert "answer" in enforced
    assert "sources" in enforced
    assert isinstance(enforced["sources"], list)
    assert "served_by" in enforced
    assert "finish_reason" in enforced
    assert "latency_ms" in enforced
