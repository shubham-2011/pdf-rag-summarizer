import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document

# Path setup
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.prompt_pipeline_service import PromptPipelineService
from services.validation_service import ValidationService


class TestPrompt1QueryProcessing:
    def test_p1_format_history_block(self):
        history = [
            {"user": "What is the refund window?", "assistant": "30 days from delivery."},
            {"user": "Does that apply to sale items?", "assistant": "No, sale items are final."}
        ]
        formatted = PromptPipelineService.format_history_block(history)
        assert 'user: "What is the refund window?"' in formatted
        assert 'assistant: "30 days from delivery."' in formatted
        assert 'user: "Does that apply to sale items?"' in formatted

    def test_p1_empty_history(self):
        formatted = PromptPipelineService.format_history_block([])
        assert formatted == "(empty)"

    def test_p1_fallback_when_no_llm(self):
        res = PromptPipelineService.process_query("What is the pump flow rate?", api_key="")
        assert res["standalone_question"] == "What is the pump flow rate?"
        assert "search_queries" in res
        assert res["needs_retrieval"] is True


class TestPrompt2Reranking:
    def test_p2_format_documents_block(self):
        docs = [
            Document(page_content="Pump flow rate is 45 L/min.", metadata={"page": 1}),
            Document(page_content="Operating voltage is 240V AC.", metadata={"page": 2})
        ]
        block = PromptPipelineService.format_documents_block(docs)
        assert '<doc id="1">Pump flow rate is 45 L/min.</doc>' in block
        assert '<doc id="2">Operating voltage is 240V AC.</doc>' in block

    def test_p2_score_floor_filtering(self):
        docs = [
            Document(page_content="Doc 1", metadata={"page": 1}),
            Document(page_content="Doc 2", metadata={"page": 2}),
            Document(page_content="Doc 3", metadata={"page": 3}),
            Document(page_content="Doc 4", metadata={"page": 4})
        ]
        # Mock fast_model to return scores: Doc 1: 8, Doc 2: 7, Doc 3: 2 (below 4), Doc 4: 1 (below 4)
        mock_output = '{"scores": [{"id": 1, "score": 8, "reason": "exact answer"}, {"id": 2, "score": 7, "reason": "supporting detail"}, {"id": 3, "score": 2, "reason": "irrelevant"}, {"id": 4, "score": 1, "reason": "off topic"}]}'

        with patch("services.prompt_pipeline_service.LLMService.get_fast_model") as mock_get_model:
            mock_model = MagicMock()
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_output
            # ChatPromptTemplate | fast_model | StrOutputParser()
            with patch("services.prompt_pipeline_service.ChatPromptTemplate.from_messages") as mock_prompt:
                mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain
                mock_get_model.return_value = mock_model

                top_3, scores, survived = PromptPipelineService.rerank_candidates(
                    "What is the pump specification?", docs, score_floor=4.0, api_key="dummy_key"
                )

                assert survived is True
                assert len(top_3) == 2  # Only doc 1 and doc 2 survive floor 4.0
                assert top_3[0].metadata["pipeline_relevance_score"] == 8
                assert top_3[1].metadata["pipeline_relevance_score"] == 7

    def test_p2_all_below_floor_fails_gracefully(self):
        docs = [Document(page_content="Doc 1", metadata={"page": 1})]
        mock_output = '{"scores": [{"id": 1, "score": 2, "reason": "unrelated"}]}'

        with patch("services.prompt_pipeline_service.LLMService.get_fast_model") as mock_get_model:
            mock_model = MagicMock()
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_output
            with patch("services.prompt_pipeline_service.ChatPromptTemplate.from_messages") as mock_prompt:
                mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain
                mock_get_model.return_value = mock_model

                top_3, scores, survived = PromptPipelineService.rerank_candidates(
                    "Random question?", docs, score_floor=4.0, api_key="dummy_key"
                )
                assert survived is False
                assert len(top_3) == 0


class TestPrompt3Generation:
    def test_p3_empty_docs_returns_refusal(self):
        ans = PromptPipelineService.generate_answer("Any question?", [])
        assert ans == PromptPipelineService.REFUSAL_STRING

    def test_p3_fallback_generates_citation(self):
        docs = [Document(page_content="Transformer oil temperature must stay below 75C.", metadata={"page": 3})]
        ans = PromptPipelineService.generate_answer("What is maximum transformer oil temperature?", docs, api_key="")
        assert "[1]" in ans
        assert "75C" in ans


class TestPrompt4Validation:
    def test_p4_refusal_on_empty_context_passes(self):
        res = PromptPipelineService.validate_answer("What is the warranty?", [], PromptPipelineService.REFUSAL_STRING)
        assert res["verdict"] == "PASS"
        assert res["grounded"] is True

    def test_p4_ungrounded_validation_failure(self):
        docs = [Document(page_content="The API rate limit is 100 requests per minute.", metadata={"page": 1})]
        mock_output = '{"grounded": false, "cited": false, "relevant": true, "complete": true, "verdict": "FAIL", "violations": [{"criterion": "grounded", "span": "it resets at midnight UTC", "issue": "Reset time not stated in context"}], "fix_instructions": "Remove claim about reset time."}'

        with patch("services.prompt_pipeline_service.LLMService.get_fast_model") as mock_get_model:
            mock_model = MagicMock()
            mock_chain = MagicMock()
            mock_chain.invoke.return_value = mock_output
            with patch("services.prompt_pipeline_service.ChatPromptTemplate.from_messages") as mock_prompt:
                mock_prompt.return_value.__or__.return_value.__or__.return_value = mock_chain
                mock_get_model.return_value = mock_model

                res = PromptPipelineService.validate_answer(
                    "What is the API rate limit?",
                    docs,
                    "The rate limit is 100 requests per minute [1], and it resets at midnight UTC.",
                    api_key="dummy_key"
                )
                assert res["verdict"] == "FAIL"
                assert res["grounded"] is False
                assert len(res["violations"]) == 1
                assert "midnight UTC" in res["violations"][0]["span"]


class TestPromptPipelineLoopControl:
    def test_early_stop_on_repeat_criterion_failure(self):
        docs = [Document(page_content="Water turbidity is 4.2 NTU.", metadata={"page": 1})]

        # Mock rerank to pass
        with patch.object(PromptPipelineService, "rerank_candidates", return_value=(docs, [{"id": 1, "score": 9}], True)):
            with patch.object(PromptPipelineService, "generate_answer", return_value="Draft answer [1]"):
                with patch.object(PromptPipelineService, "regenerate_answer", return_value="Revised answer [1]"):
                    # Both attempt 1 and attempt 2 fail on 'grounded'
                    val_fail = {
                        "grounded": False,
                        "cited": True,
                        "relevant": True,
                        "complete": True,
                        "verdict": "FAIL",
                        "violations": [{"criterion": "grounded", "span": "unsupported", "issue": "not in text"}],
                        "fix_instructions": "Remove unsupported claim"
                    }
                    with patch.object(PromptPipelineService, "validate_answer", return_value=val_fail):
                        result = PromptPipelineService.run_pipeline("Question?", docs, max_retries=2)
                        telemetry = result["telemetry"]
                        # Should stop early at attempt 2 due to repeat failure on 'grounded'
                        assert telemetry["attempts"] == 2
                        assert telemetry.get("early_stop") is True
                        assert "grounded" in telemetry.get("early_stop_criteria", [])
                        assert result["answer"] == PromptPipelineService.REFUSAL_STRING

    def test_score_floor_refusal_skips_generation(self):
        docs = [Document(page_content="Irrelevant text", metadata={"page": 1})]
        with patch.object(PromptPipelineService, "rerank_candidates", return_value=([], [{"id": 1, "score": 1.5}], False)):
            result = PromptPipelineService.run_pipeline("Specific question?", docs)
            assert result["answer"] == PromptPipelineService.REFUSAL_STRING
            assert result["telemetry"]["attempts"] == 0
            assert result["telemetry"]["finish_reason"] == "score_floor_refusal"
