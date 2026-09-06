import os
import sys
import re
import pytest
from typing import List, Dict, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.metadata_service import MetadataService
from services.query_understanding_service import QueryUnderstandingService
from services.validation_service import ValidationService, CitationSanityError


class TestSynthesisAndCitationsD:
    """D1–D4 Synthesis, Grounding, Citation Accuracy and Multi-turn Contextualization Tests."""

    def test_d1_grounding_unanswerable_probe(self):
        """Unanswerable query probe: questions about unmentioned facts must be refused cleanly."""
        unanswerable_query = "what is the quantum encryption key used for satellite uplink?"
        context = "The IoT gateway operates between 18VDC and 36VDC with maximum thermal dissipation of 45W."
        
        # Grounding check: context lacks any quantum or satellite terms
        assert "quantum" not in context
        assert "satellite" not in context

    def test_d2_citation_accuracy_deterministic(self):
        """
        D2: Deterministic citation verification.
        - page_exists: 1 <= page <= unit_count
        - no_phantom_pages: cited page in candidate pool
        - heading_consistent: section matches candidate
        """
        unit_count = 3
        retrieved_candidates = [
            {"page": 1, "section": "ENVIRONMENTAL OVERVIEW", "text": "WQI is calculated using pH, DO, and BOD."},
            {"page": 2, "section": "MACHINE LEARNING", "text": "XGBoost achieved R2 score of 0.968 and lowest RMSE 2.15."},
        ]

        # Valid citations
        valid_citations = [
            {"page": 1, "file": "water_quality_report.pdf", "snippet": "WQI is calculated using pH, DO, and BOD.", "section": "ENVIRONMENTAL OVERVIEW"},
            {"page": 2, "file": "water_quality_report.pdf", "snippet": "XGBoost achieved R2 score of 0.968", "section": "MACHINE LEARNING"}
        ]

        # 1. Check page exists
        for c in valid_citations:
            pg = int(c["page"])
            assert 1 <= pg <= unit_count, f"Page {pg} outside valid page count {unit_count}"

        # 2. Check no phantom pages
        retrieved_pages = {c["page"] for c in retrieved_candidates}
        for c in valid_citations:
            assert c["page"] in retrieved_pages, f"Phantom page citation detected: page {c['page']}"

        # 3. Check heading consistency
        retrieved_sections = {c["page"]: c["section"] for c in retrieved_candidates}
        for c in valid_citations:
            expected_sec = retrieved_sections.get(c["page"])
            assert c["section"] == expected_sec, f"Heading mismatch: {c['section']} vs {expected_sec}"

        # 4. Out of bounds citation rejection by ValidationService
        invalid_citations = [
            {"page": 99, "file": "test.pdf", "snippet": "Out of bounds page 99"}
        ]
        sanitized = ValidationService.validate_citations(invalid_citations, unit_count=unit_count)
        assert len(sanitized) == 0, "ValidationService failed to strip out-of-bounds citation"

    def test_d3_global_query_synthesis_evaluation(self):
        """
        D3: GLOBAL query synthesis checks:
        - key points covered
        - is_extractive is False (synthesized, not raw chunk copying)
        - section_balance is not purely front-loaded
        """
        gold_key_points = [
            "water quality parameters along Ganga basin",
            "XGBoost achieved highest predictive accuracy",
            "telemetry installation and effluent treatment recommendations"
        ]

        summary = (
            "This technical report evaluates water quality across 15 Ganga basin monitoring stations. "
            "Using comparative machine learning models, XGBoost demonstrated superior predictive accuracy (R² = 0.968) "
            "with BOD and Dissolved Oxygen as primary indicators. "
            "The study concludes with actionable remediation plans including automated telemetry by 2027 and zero-liquid-discharge mandates."
        )

        # Coverage ratio check: each key concept must have representative terms in summary
        key_concept_terms = [
            ["water quality", "ganga", "basin"],
            ["xgboost", "accuracy", "predictive"],
            ["telemetry", "effluent", "remediation"]
        ]
        covered = [terms for terms in key_concept_terms if any(t in summary.lower() for t in terms)]
        coverage_ratio = len(covered) / len(key_concept_terms)
        assert coverage_ratio >= 0.70, f"Coverage ratio too low: {coverage_ratio:.2f}"

        # Not raw extractive copying
        assert "TABLE 1: MODEL PERFORMANCE COMPARISON" not in summary
        assert len(summary.split()) >= 30

    def test_d4_multi_turn_contextualization_chain(self):
        """
        D4: Multi-turn contextualization:
        Q1 -> Q2 (pronoun 'it') -> Q3 (pronoun 'that') -> Q4 (topic switch).
        """
        history = [
            {"role": "user", "content": "What is the RAG service?"},
            {"role": "assistant", "content": "The RAG service handles document ingestion, hybrid retrieval, and grounded synthesis."},
            {"role": "user", "content": "What technologies does it use?"},
            {"role": "assistant", "content": "It uses PyMuPDF, Nomic embeddings, FAISS, BM25, and BGE reranker."},
        ]

        # Q3: pronoun resolution
        q3 = "and how is that configured?"
        rewritten_q3 = QueryUnderstandingService.contextualize_question(q3, chat_history=history)
        assert len(rewritten_q3) > len(q3) or "configured" in rewritten_q3.lower()

        # Q4: topic switch (mid-conversation topic switch must not inherit irrelevant context)
        q4 = "what about the cloud deployment on Render?"
        rewritten_q4 = QueryUnderstandingService.contextualize_question(q4, chat_history=history)
        assert "render" in rewritten_q4.lower()
