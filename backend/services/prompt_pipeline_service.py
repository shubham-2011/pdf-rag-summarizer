import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from services.llm_service import LLMService
import config


class PromptPipelineService:
    """
    RAG Pipeline Prompts Engine
    Implements the 5-stage Retrieve -> Rerank -> Generate -> Validate -> Regenerate pipeline:
    - Prompt 1: Query Processing (Temp 0.0, Small model, JSON output)
    - Prompt 2: Ranking / Reranking (Temp 0.0, Small model, JSON output)
    - Prompt 3: Generation (Temp 0.2, Large model, Text output with [id] citations)
    - Prompt 4: Validation (Temp 0.0, Small/Mid model, JSON output with fix instructions)
    - Prompt 5: Regeneration (Temp 0.2, Large model, Text revision)
    """

    REFUSAL_STRING = "I don't have enough information to answer that."

    # -------------------------------------------------------------------------
    # PROMPT 1: Query Processing
    # -------------------------------------------------------------------------
    P1_SYSTEM = (
        "You rewrite user questions into effective retrieval queries for a document search system.\n"
        "You output JSON and nothing else."
    )

    P1_USER = (
        "Conversation history:\n"
        "{history}\n\n"
        "User question: {question}\n\n"
        "Return JSON only, matching this schema:\n"
        "{{\n"
        '  "standalone_question": "<the question rewritten to be fully self-contained, resolving all pronouns and references using the history>",\n'
        '  "search_queries": ["<1-3 keyword-style queries, each covering a distinct aspect of the question>"],\n'
        '  "needs_retrieval": true,\n'
        '  "reasoning": "<one sentence, max 20 words>"\n'
        "}}\n\n"
        "Rules:\n"
        "1. The standalone question must be understandable with no access to the history.\n"
        "2. Do not invent entities, names, dates, or constraints that are not in the question or history.\n"
        "3. Split multi-part questions into separate search_queries. Single-topic questions get one query.\n"
        "4. Search queries are keywords and noun phrases, not full sentences.\n"
        "5. Set needs_retrieval to false for greetings, thanks, meta-questions about the assistant,\n"
        "   or questions already fully answered in the history. Then search_queries must be [].\n"
        "6. Output the JSON object only. No markdown fences, no commentary.\n\n"
        "Examples:\n"
        "History: user: \"What is the refund window?\"  assistant: \"30 days from delivery.\"\n"
        "Question: \"Does that apply to sale items?\"\n"
        'Output: {{"standalone_question":"Does the 30-day refund window apply to sale items?","search_queries":["refund policy sale items","clearance final sale returns"],"needs_retrieval":true,"reasoning":"Pronoun \'that\' resolved to the refund window."}}\n\n'
        "History: (empty)\n"
        "Question: \"thanks, that helped\"\n"
        'Output: {{"standalone_question":"thanks, that helped","search_queries":[],"needs_retrieval":false,"reasoning":"Conversational acknowledgement, no information request."}}'
    )

    # -------------------------------------------------------------------------
    # PROMPT 2: Ranking / Reranking
    # -------------------------------------------------------------------------
    P2_SYSTEM = (
        "You are a relevance judge. You score documents against a question on a 0-10 scale.\n"
        "You output JSON and nothing else."
    )

    P2_USER = (
        "Question: {question}\n\n"
        "Documents:\n"
        "{documents_block}\n\n"
        "Scoring scale:\n"
        "  0-2   unrelated to the question\n"
        "  3-5   same topic but does not answer the question\n"
        "  6-8   contains part of the answer or necessary supporting detail\n"
        "  9-10  directly and substantially answers the question\n\n"
        "Rules:\n"
        "1. Judge relevance to THIS question only. Ignore writing quality, length, formatting, and the order documents appear in.\n"
        "2. Score each document independently. Do not grade on a curve — all ten may be low, or several may be high.\n"
        "3. A document that is topically adjacent but answers a different question scores at most 5.\n"
        "4. Every document id must appear exactly once in the output.\n\n"
        "Return JSON only:\n"
        '{{"scores": [{{"id": 1, "score": 7, "reason": "<max 8 words>"}}]}}'
    )

    # -------------------------------------------------------------------------
    # PROMPT 3: Generation
    # -------------------------------------------------------------------------
    P3_SYSTEM = (
        "You answer questions using only the context provided in the user message.\n"
        "You never use prior knowledge. You cite every factual claim."
    )

    P3_USER = (
        "Context:\n"
        "{context_block}\n\n"
        "Question: {question}\n\n"
        "Rules:\n"
        "1. Use only information stated in the context above. Do not use outside or prior knowledge.\n"
        "2. Cite the document id after every factual claim, like [1] or [2][3]. Place citations at the\n"
        "   end of the sentence they support.\n"
        "3. If the context does not contain the answer, reply with exactly:\n"
        "   I don't have enough information to answer that.\n"
        "   Do not guess, do not partially answer, do not suggest what the answer might be.\n"
        "4. If the documents disagree, state that they disagree and give both positions with citations.\n"
        "5. Do not restate the question. Do not add a preamble or a closing offer of further help.\n"
        "6. Match the question's level of detail: a yes/no question gets a short answer plus the\n"
        "   supporting fact.\n\n"
        "Answer:"
    )

    # -------------------------------------------------------------------------
    # PROMPT 4: Validation
    # -------------------------------------------------------------------------
    P4_SYSTEM = (
        "You are a strict validator for a retrieval-augmented answering system.\n"
        "You judge an answer only against the supplied context. You output JSON and nothing else.\n"
        "A borderline answer fails."
    )

    P4_USER = (
        "Question: {question}\n\n"
        "Context:\n"
        "{context_block}\n\n"
        "Answer under review:\n"
        "{answer}\n\n"
        "Evaluate these four criteria:\n"
        "- grounded:  every factual claim in the answer is supported by the context. Any claim that is\n"
        "             not stated in or directly entailed by the context is a violation, even if it is\n"
        "             true in the real world.\n"
        "- cited:     every factual claim carries a citation, and every cited id exists in the context\n"
        "             and actually supports that claim.\n"
        "- relevant:  the answer addresses what was asked, not an adjacent question.\n"
        "- complete:  the answer covers the question using what the context supports; OR it correctly\n"
        "             refuses because the context is insufficient.\n\n"
        'Special case: if the answer is exactly "I don\'t have enough information to answer that.",\n'
        "it PASSES if the context truly cannot answer the question, and FAILS on `complete` if the\n"
        "context does contain the answer.\n\n"
        "Calibration examples:\n"
        "Example FAIL (ungrounded)\n"
        "Context: <doc id=\"1\">The API rate limit is 100 requests per minute.</doc>\n"
        'Answer: "The rate limit is 100 requests per minute [1], and it resets at midnight UTC."\n'
        'Output: {{"grounded":false,"cited":false,"relevant":true,"complete":true,"verdict":"FAIL","violations":[{{"criterion":"grounded","span":"it resets at midnight UTC","issue":"Reset time is not stated anywhere in the context."}},{{"criterion":"cited","span":"it resets at midnight UTC","issue":"Claim carries no citation."}}],"fix_instructions":"Remove the claim about the reset time entirely. Keep the rate limit sentence with its [1] citation."}}\n\n'
        "Example PASS\n"
        "Context: <doc id=\"1\">The API rate limit is 100 requests per minute.</doc>\n"
        'Answer: "The rate limit is 100 requests per minute [1]."\n'
        'Output: {{"grounded":true,"cited":true,"relevant":true,"complete":true,"verdict":"PASS","violations":[],"fix_instructions":""}}\n\n'
        "Return JSON only, matching this schema:\n"
        "{{\n"
        '  "grounded": true,\n'
        '  "cited": true,\n'
        '  "relevant": true,\n'
        '  "complete": true,\n'
        '  "verdict": "PASS",\n'
        '  "violations": [\n'
        '    {{"criterion": "grounded", "span": "<exact quoted text from the answer>", "issue": "<what is wrong, one sentence>"}}\n'
        "  ],\n"
        '  "fix_instructions": "<specific actionable instructions for the rewriter; empty string if PASS>"\n'
        "}}\n\n"
        "Rules:\n"
        '1. verdict is "PASS" only if all four booleans are true. Otherwise "FAIL".\n'
        '2. violations must be empty when the verdict is PASS.\n'
        "3. Each violation span must be text copied verbatim from the answer.\n"
        "4. Do not use outside knowledge to defend or attack a claim. The context is the only authority.\n"
        "5. Style, tone, and length are not criteria. Do not fail an answer for being terse."
    )

    # -------------------------------------------------------------------------
    # PROMPT 5: Regeneration
    # -------------------------------------------------------------------------
    P5_SYSTEM = (
        "You revise answers that failed validation. You work only from the supplied context.\n"
        "You fix the listed violations without introducing new ones."
    )

    P5_USER = (
        "Context:\n"
        "{context_block}\n\n"
        "Question: {question}\n\n"
        "Your previous answer (attempt {attempt} of {max_attempts}):\n"
        "{previous_answer}\n\n"
        "Validation failures:\n"
        "{violations}\n\n"
        "Required fixes:\n"
        "{fix_instructions}\n\n"
        "Rules:\n"
        "1. Fix every listed violation. Keep the parts of the previous answer that were not flagged.\n"
        "2. Delete any claim you cannot support with a citation to the context above. Deleting is\n"
        "   always preferable to hedging or rephrasing an unsupported claim.\n"
        "3. Do not add new claims that were not in the previous answer, unless a violation explicitly\n"
        "   says the answer was incomplete.\n"
        "4. If removing the unsupported claims leaves nothing substantive, reply with exactly:\n"
        "   I don't have enough information to answer that.\n"
        "5. Citation format is unchanged: [1], [2][3], at the end of the sentence.\n"
        "6. Output the corrected answer only. No explanation of what you changed.\n\n"
        "Corrected answer:"
    )

    # -------------------------------------------------------------------------
    # Helper: Context Document Block Formatter
    # -------------------------------------------------------------------------
    @staticmethod
    def format_documents_block(docs: List[Document], max_docs: int = 10) -> str:
        """Formats Document chunks into numbered XML-style tags <doc id="X">...</doc>."""
        blocks = []
        for i, doc in enumerate(docs[:max_docs], start=1):
            content = doc.page_content.strip()
            blocks.append(f'<doc id="{i}">{content}</doc>')
        return "\n".join(blocks)

    @staticmethod
    def format_history_block(chat_history: Optional[List[Dict[str, str]]]) -> str:
        """Formats conversation history dictionary list into a readable string."""
        if not chat_history:
            return "(empty)"
        lines = []
        for turn in chat_history:
            user_msg = turn.get("user") or turn.get("content") or ""
            bot_msg = turn.get("assistant") or turn.get("bot") or ""
            if user_msg:
                lines.append(f'user: "{user_msg}"')
            if bot_msg:
                lines.append(f'assistant: "{bot_msg}"')
        return "\n".join(lines) if lines else "(empty)"

    # -------------------------------------------------------------------------
    # Pipeline Step 1: Query Processing
    # -------------------------------------------------------------------------
    @classmethod
    def process_query(
        cls,
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes Prompt 1.
        Returns: {
            "standalone_question": str,
            "search_queries": List[str],
            "needs_retrieval": bool,
            "reasoning": str
        }
        """
        default_result = {
            "standalone_question": question,
            "search_queries": [question],
            "needs_retrieval": True,
            "reasoning": "Default single query fallback."
        }

        fast_model = LLMService.get_fast_model(api_key=api_key, temperature=0.0)
        if not fast_model:
            return default_result

        history_str = cls.format_history_block(chat_history)
        prompt = ChatPromptTemplate.from_messages([
            ("system", cls.P1_SYSTEM),
            ("human", cls.P1_USER)
        ])

        try:
            chain = prompt | fast_model | StrOutputParser()
            raw_output = chain.invoke({"history": history_str, "question": question})
            parsed = LLMService.extract_json(raw_output)
            if isinstance(parsed, dict) and "standalone_question" in parsed:
                sq = parsed.get("search_queries", [])
                if not isinstance(sq, list):
                    sq = [str(sq)] if sq else []
                parsed["search_queries"] = [str(q).strip() for q in sq if str(q).strip()]
                parsed["needs_retrieval"] = bool(parsed.get("needs_retrieval", True))
                parsed["standalone_question"] = str(parsed.get("standalone_question") or question).strip()
                return parsed
        except Exception as e:
            print(f"[PromptPipelineService] Prompt 1 invocation error: {e}")

        return default_result

    # -------------------------------------------------------------------------
    # Pipeline Step 2: Ranking / Reranking
    # -------------------------------------------------------------------------
    @classmethod
    def rerank_candidates(
        cls,
        question: str,
        candidates: List[Document],
        score_floor: float = 4.0,
        api_key: Optional[str] = None
    ) -> Tuple[List[Document], List[Dict[str, Any]], bool]:
        """
        Executes Prompt 2 over up to 10 candidate documents.
        Returns: (top_3_docs, all_scores, survived_floor)
        """
        if not candidates:
            return [], [], False

        candidate_slice = candidates[:10]
        for idx, doc in enumerate(candidate_slice, start=1):
            doc.metadata["pipeline_doc_id"] = idx

        fast_model = LLMService.get_fast_model(api_key=api_key, temperature=0.0)
        if not fast_model:
            # Fallback to candidate slice
            top_3 = candidate_slice[:3]
            return top_3, [], True

        docs_block = cls.format_documents_block(candidate_slice, max_docs=10)
        prompt = ChatPromptTemplate.from_messages([
            ("system", cls.P2_SYSTEM),
            ("human", cls.P2_USER)
        ])

        try:
            chain = prompt | fast_model | StrOutputParser()
            raw_output = chain.invoke({"question": question, "documents_block": docs_block})
            parsed = LLMService.extract_json(raw_output)

            scores_list = []
            if isinstance(parsed, dict) and "scores" in parsed:
                scores_list = parsed["scores"]
            elif isinstance(parsed, list):
                scores_list = parsed

            score_map = {}
            for item in scores_list:
                if isinstance(item, dict) and "id" in item:
                    try:
                        doc_id = int(item["id"])
                        score_val = float(item.get("score", 0.0))
                        reason = str(item.get("reason", ""))
                        score_map[doc_id] = (score_val, reason)
                    except (ValueError, TypeError):
                        continue

            for idx, doc in enumerate(candidate_slice, start=1):
                s_val, s_reason = score_map.get(idx, (0.0, "unscored"))
                doc.metadata["pipeline_relevance_score"] = s_val
                doc.metadata["pipeline_rerank_reason"] = s_reason

            sorted_docs = sorted(
                candidate_slice,
                key=lambda d: d.metadata.get("pipeline_relevance_score", 0.0),
                reverse=True
            )

            surviving_docs = [
                d for d in sorted_docs
                if d.metadata.get("pipeline_relevance_score", 0.0) >= score_floor
            ]

            if not surviving_docs:
                return [], scores_list, False

            top_3 = surviving_docs[:3]
            return top_3, scores_list, True

        except Exception as e:
            print(f"[PromptPipelineService] Prompt 2 reranking error: {e}")
            return candidate_slice[:3], [], True

    # -------------------------------------------------------------------------
    # Pipeline Step 3: Generation
    # -------------------------------------------------------------------------
    @classmethod
    def generate_answer(
        cls,
        question: str,
        top_docs: List[Document],
        api_key: Optional[str] = None
    ) -> str:
        """
        Executes Prompt 3 over top 3 context documents.
        """
        if not top_docs:
            return cls.REFUSAL_STRING

        synthesis_model = LLMService.get_synthesis_model(api_key=api_key, temperature=0.2)
        if not synthesis_model:
            first_doc = top_docs[0]
            snippet = first_doc.page_content.strip()[:200]
            return f"{snippet} [1]"

        context_block = cls.format_documents_block(top_docs, max_docs=3)
        prompt = ChatPromptTemplate.from_messages([
            ("system", cls.P3_SYSTEM),
            ("human", cls.P3_USER)
        ])

        try:
            chain = prompt | synthesis_model | StrOutputParser()
            answer = chain.invoke({"question": question, "context_block": context_block})
            return answer.strip() if answer else cls.REFUSAL_STRING
        except Exception as e:
            print(f"[PromptPipelineService] Prompt 3 generation error: {e}")
            return cls.REFUSAL_STRING

    # -------------------------------------------------------------------------
    # Pipeline Step 4: Validation
    # -------------------------------------------------------------------------
    @classmethod
    def validate_answer(
        cls,
        question: str,
        top_docs: List[Document],
        answer: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes Prompt 4.
        Returns: {
            "grounded": bool,
            "cited": bool,
            "relevant": bool,
            "complete": bool,
            "verdict": "PASS" | "FAIL",
            "violations": List[Dict[str, str]],
            "fix_instructions": str
        }
        """
        if answer.strip() == cls.REFUSAL_STRING:
            if not top_docs:
                return {
                    "grounded": True,
                    "cited": True,
                    "relevant": True,
                    "complete": True,
                    "verdict": "PASS",
                    "violations": [],
                    "fix_instructions": ""
                }

        fast_model = LLMService.get_fast_model(api_key=api_key, temperature=0.0)
        if not fast_model:
            has_citation = bool(re.search(r'\[\d+\]', answer) or re.search(r'\[Page\s*\d+\]', answer, re.IGNORECASE))
            is_refusal = answer.strip() == cls.REFUSAL_STRING
            passed = is_refusal or has_citation
            return {
                "grounded": passed,
                "cited": passed,
                "relevant": True,
                "complete": True,
                "verdict": "PASS" if passed else "FAIL",
                "violations": [] if passed else [{"criterion": "cited", "span": answer[:40], "issue": "Missing citations."}],
                "fix_instructions": "" if passed else "Add citations [1] to factual claims."
            }

        context_block = cls.format_documents_block(top_docs, max_docs=3)
        prompt = ChatPromptTemplate.from_messages([
            ("system", cls.P4_SYSTEM),
            ("human", cls.P4_USER)
        ])

        try:
            chain = prompt | fast_model | StrOutputParser()
            raw_output = chain.invoke({
                "question": question,
                "context_block": context_block,
                "answer": answer
            })
            parsed = LLMService.extract_json(raw_output)

            if isinstance(parsed, dict) and "verdict" in parsed:
                grounded = bool(parsed.get("grounded", False))
                cited = bool(parsed.get("cited", False))
                relevant = bool(parsed.get("relevant", False))
                complete = bool(parsed.get("complete", False))
                verdict = "PASS" if (grounded and cited and relevant and complete) else "FAIL"
                
                violations = parsed.get("violations", [])
                if not isinstance(violations, list):
                    violations = []
                fix_instructions = str(parsed.get("fix_instructions", "") or "").strip()

                return {
                    "grounded": grounded,
                    "cited": cited,
                    "relevant": relevant,
                    "complete": complete,
                    "verdict": verdict,
                    "violations": violations,
                    "fix_instructions": fix_instructions
                }
        except Exception as e:
            print(f"[PromptPipelineService] Prompt 4 validation error: {e}")

        return {
            "grounded": False,
            "cited": False,
            "relevant": True,
            "complete": False,
            "verdict": "FAIL",
            "violations": [{"criterion": "grounded", "span": answer[:40], "issue": "Validation error"}],
            "fix_instructions": "Ensure all claims are cited directly to provided documents."
        }

    # -------------------------------------------------------------------------
    # Pipeline Step 5: Regeneration
    # -------------------------------------------------------------------------
    @classmethod
    def regenerate_answer(
        cls,
        question: str,
        top_docs: List[Document],
        previous_answer: str,
        violations: List[Dict[str, str]],
        fix_instructions: str,
        attempt: int,
        max_attempts: int = 3,
        api_key: Optional[str] = None
    ) -> str:
        """
        Executes Prompt 5 to revise answer that failed validation.
        """
        synthesis_model = LLMService.get_synthesis_model(api_key=api_key, temperature=0.2)
        if not synthesis_model:
            return previous_answer

        context_block = cls.format_documents_block(top_docs, max_docs=3)
        violations_str = json.dumps(violations, indent=2) if violations else "No specific violations listed."

        prompt = ChatPromptTemplate.from_messages([
            ("system", cls.P5_SYSTEM),
            ("human", cls.P5_USER)
        ])

        try:
            chain = prompt | synthesis_model | StrOutputParser()
            corrected = chain.invoke({
                "question": question,
                "context_block": context_block,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "previous_answer": previous_answer,
                "violations": violations_str,
                "fix_instructions": fix_instructions
            })
            return corrected.strip() if corrected else cls.REFUSAL_STRING
        except Exception as e:
            print(f"[PromptPipelineService] Prompt 5 regeneration error: {e}")
            return previous_answer

    # -------------------------------------------------------------------------
    # Loop Control & Orchestration
    # -------------------------------------------------------------------------
    @classmethod
    def run_pipeline(
        cls,
        question: str,
        candidates: List[Document],
        chat_history: Optional[List[Dict[str, str]]] = None,
        api_key: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Runs the complete retrieve -> rerank -> generate -> validate -> regenerate pipeline.
        Enforces loop control:
        - Cap retries at 2 (max 3 total generations)
        - Stop early on repeat failures (same criterion in attempt N as attempt N-1)
        - Skip validation on refusal string when reranker scored no document above floor
        - Log violations by criterion
        """
        start_time = time.time()
        max_attempts = max_retries + 1  # 3 total attempts
        telemetry = {
            "attempts": 0,
            "llm_calls": 0,
            "rerank_calls": 0,
            "violations_by_criterion": {"grounded": 0, "cited": 0, "relevant": 0, "complete": 0},
            "validation_history": [],
            "final_verdict": "FAIL",
            "served_by": "prompt_pipeline"
        }

        # Step 2: Reranking top candidates (cut to top 3, floor >= 4.0)
        telemetry["rerank_calls"] += 1
        floor = getattr(config, "PIPELINE_RERANK_SCORE_FLOOR", 4.0)
        top_docs, rerank_scores, survived_floor = cls.rerank_candidates(
            question=question,
            candidates=candidates,
            score_floor=floor,
            api_key=api_key
        )

        # If no documents survived the score floor, skip generation and return refusal fallback
        if not survived_floor or not top_docs:
            elapsed_ms = (time.time() - start_time) * 1000.0
            return {
                "answer": cls.REFUSAL_STRING,
                "top_docs": [],
                "scores": rerank_scores,
                "verdict": "PASS",  # Skip validation on refusal string when reranker filtered all
                "telemetry": {
                    **telemetry,
                    "attempts": 0,
                    "latency_ms": elapsed_ms,
                    "finish_reason": "score_floor_refusal"
                }
            }

        # Generation & Validation Loop
        current_answer = ""
        last_failed_criteria = set()
        validation_result = {}

        for attempt in range(1, max_attempts + 1):
            telemetry["attempts"] = attempt

            # Generate or Regenerate
            if attempt == 1:
                telemetry["llm_calls"] += 1
                current_answer = cls.generate_answer(
                    question=question,
                    top_docs=top_docs,
                    api_key=api_key
                )
            else:
                telemetry["llm_calls"] += 1
                violations = validation_result.get("violations", [])
                fix_inst = validation_result.get("fix_instructions", "")
                current_answer = cls.regenerate_answer(
                    question=question,
                    top_docs=top_docs,
                    previous_answer=current_answer,
                    violations=violations,
                    fix_instructions=fix_inst,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    api_key=api_key
                )

            # Validate
            telemetry["llm_calls"] += 1
            validation_result = cls.validate_answer(
                question=question,
                top_docs=top_docs,
                answer=current_answer,
                api_key=api_key
            )

            verdict = validation_result.get("verdict", "FAIL")
            telemetry["validation_history"].append({
                "attempt": attempt,
                "verdict": verdict,
                "grounded": validation_result.get("grounded", False),
                "cited": validation_result.get("cited", False),
                "relevant": validation_result.get("relevant", False),
                "complete": validation_result.get("complete", False),
                "violations": validation_result.get("violations", [])
            })

            # Record violations by criterion
            current_failed_criteria = set()
            for crit in ["grounded", "cited", "relevant", "complete"]:
                if not validation_result.get(crit, False):
                    telemetry["violations_by_criterion"][crit] += 1
                    current_failed_criteria.add(crit)

            if verdict == "PASS":
                telemetry["final_verdict"] = "PASS"
                break

            # Check for early stop on repeat failures
            if attempt > 1 and current_failed_criteria and (current_failed_criteria & last_failed_criteria):
                print(f"[PromptPipelineService] Early stop: Repeat failure on {current_failed_criteria & last_failed_criteria}")
                telemetry["early_stop"] = True
                telemetry["early_stop_criteria"] = list(current_failed_criteria & last_failed_criteria)
                break

            last_failed_criteria = current_failed_criteria

        elapsed_ms = (time.time() - start_time) * 1000.0
        telemetry["latency_ms"] = elapsed_ms

        final_verdict = validation_result.get("verdict", "FAIL")
        if final_verdict == "PASS":
            return {
                "answer": current_answer,
                "top_docs": top_docs,
                "scores": rerank_scores,
                "verdict": "PASS",
                "validation": validation_result,
                "telemetry": telemetry
            }

        # If loop exhausted or broke early, check if last answer is at least grounded
        if validation_result.get("grounded", False) and current_answer.strip():
            return {
                "answer": current_answer,
                "top_docs": top_docs,
                "scores": rerank_scores,
                "verdict": "FAIL_GROUNDED_FALLBACK",
                "validation": validation_result,
                "telemetry": telemetry
            }

        # Otherwise return refusal fallback
        return {
            "answer": cls.REFUSAL_STRING,
            "top_docs": top_docs,
            "scores": rerank_scores,
            "verdict": "FAIL_REFUSAL_FALLBACK",
            "validation": validation_result,
            "telemetry": telemetry
        }
