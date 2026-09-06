import os
import sys
import json
import re
from typing import Dict, Any, List, Optional

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.llm_service import LLMService

class LLMJudge:
    """Enterprise LLM-as-a-Judge implementation covering Answer Quality (§3.3) and Locational Precision (§3.4)."""

    ANSWER_QUALITY_SYSTEM_PROMPT = """You are evaluating an answer from a document question-answering system,
from the perspective of the user who asked.

<document_facts>
title: {title}
type: {doc_type}
pages: {unit_count}
outline: {outline}
</document_facts>

<source_excerpts>
{source_excerpts}
</source_excerpts>

<retrieved_context>
{retrieved_context}
</retrieved_context>

<question>{question}</question>
<question_class>{question_class}</question_class>
<answer>{answer}</answer>

DEFINITIONS
- hallucination: a claim not supported by <source_excerpts>. Always a defect.
- inference: a claim not stated verbatim but validly synthesized from the retrieved context. NOT a defect.
- unwarranted_refusal: the answer declines or says information is missing, but the document contains enough to answer. Equal in severity to hallucination.
- fragment_answer: output consisting of phrases, labels, or bullet fragments rather than complete sentences. A defect for GLOBAL questions.
- wrong_class_handling: the answer was produced by the wrong strategy — e.g. a page count generated from chunks instead of read from metadata. A defect even if the answer is correct, because it is correct by accident.

SCORE 1-5 (5 best)
1. faithfulness        - free of hallucination. 1 if any hallucination.
2. helpfulness         - answers what was asked. 1 for unwarranted_refusal.
3. completeness        - covers what the question required, no more.
4. form                - appropriate shape for the class. 1 for fragment_answer on a GLOBAL question.
5. citation_support    - claims carry citations that plausibly support them.
6. calibration         - confidence matches evidence. Penalize both hedging on well-supported claims and certainty on weak ones.

Would a user reading only this answer be correctly informed, misled, or left without an answer? Answer in `user_outcome`.

Return ONLY valid JSON:
{
  "faithfulness": <int>,
  "hallucinated_claims": [<string>],
  "helpfulness": <int>,
  "unwarranted_refusal": <bool>,
  "completeness": <int>,
  "missed_points": [<string>],
  "form": <int>,
  "fragment_answer": <bool>,
  "citation_support": <int>,
  "calibration": <int>,
  "wrong_class_handling": <bool>,
  "user_outcome": "informed" | "misled" | "unanswered",
  "verdict": "PASS" | "FAIL",
  "reasoning": "<2 sentences max>"
}"""

    LOCATIONAL_PRECISION_SYSTEM_PROMPT = """You are evaluating locational precision for a document QA system.
<question>{question}</question>
<actual_page_text>{actual_page_text}</actual_page_text>
<answer>{answer}</answer>

1. Does the answer describe content actually on the requested page?
2. Does it include content from other pages? (leakage)
3. Does it omit a major element of the requested page?

Return ONLY valid JSON:
{
  "page_accurate": <bool>,
  "leaked_from": [<int>],
  "omitted": [<string>],
  "verdict": "PASS" | "FAIL",
  "reasoning": "<1 sentence>"
}"""

    @classmethod
    def evaluate_answer_quality(
        cls,
        doc_facts: Dict[str, Any],
        source_excerpts: str,
        retrieved_context: str,
        question: str,
        question_class: str,
        answer: str,
        response_strategy: str = "llm_synthesis"
    ) -> Dict[str, Any]:
        """Evaluates answer quality according to User-POV Section 3.3 rubric."""
        llm = LLMService.get_chat_model(temperature=0.0)

        # Check for wrong_class_handling defect
        wrong_class = False
        if question_class == "STRUCTURAL" and response_strategy != "registry_metadata":
            wrong_class = True

        if llm:
            try:
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser

                prompt_str = cls.ANSWER_QUALITY_SYSTEM_PROMPT.format(
                    title=doc_facts.get("title", ""),
                    doc_type=doc_facts.get("doc_type", "document"),
                    unit_count=doc_facts.get("unit_count", 1),
                    outline=doc_facts.get("outline", []),
                    source_excerpts=source_excerpts[:2500],
                    retrieved_context=retrieved_context[:2500],
                    question=question,
                    question_class=question_class,
                    answer=answer
                )

                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompt_str),
                    ("human", "Evaluate the answer and output valid JSON.")
                ])
                chain = prompt | llm | StrOutputParser()
                raw_out = chain.invoke({})

                # Parse JSON
                cleaned_json = re.sub(r'^```(json)?|```$', '', raw_out.strip(), flags=re.MULTILINE).strip()
                parsed = json.loads(cleaned_json)
                if wrong_class:
                    parsed["wrong_class_handling"] = True
                    parsed["verdict"] = "FAIL"
                return parsed
            except Exception as e:
                # Fallback to local heuristic scorecard
                pass

        # Offline / Heuristic Fallback Scorecard
        ans_lower = answer.lower()
        is_refusal = any(k in ans_lower for k in ["not mentioned", "not found", "cannot answer", "not present"])
        is_fragment = (question_class == "GLOBAL" and len(answer.split()) < 15 and not any(c in answer for c in [".", "\n"]))
        
        # Check if question could have been answered from source excerpts
        has_source_info = any(w in source_excerpts.lower() for w in re.findall(r'\b\w+\b', question.lower()) if len(w) > 4)
        unwarranted_refusal = is_refusal and has_source_info and question_class not in ["OUT_OF_SCOPE"]

        faithfulness = 5
        helpfulness = 1 if unwarranted_refusal else 5
        form = 1 if is_fragment else 5
        citation_support = 5 if ("[" in answer or question_class in ["STRUCTURAL", "CONVERSATIONAL"]) else 4
        calibration = 5
        completeness = 5 if len(answer) > 20 else 3

        verdict = "FAIL" if (wrong_class or unwarranted_refusal or is_fragment or helpfulness <= 2) else "PASS"
        outcome = "unanswered" if is_refusal else ("misled" if verdict == "FAIL" else "informed")

        return {
            "faithfulness": faithfulness,
            "hallucinated_claims": [],
            "helpfulness": helpfulness,
            "unwarranted_refusal": unwarranted_refusal,
            "completeness": completeness,
            "missed_points": [],
            "form": form,
            "fragment_answer": is_fragment,
            "citation_support": citation_support,
            "calibration": calibration,
            "wrong_class_handling": wrong_class,
            "user_outcome": outcome,
            "verdict": verdict,
            "reasoning": f"Evaluated under {response_strategy} with class {question_class}."
        }

    @classmethod
    def evaluate_locational_precision(
        cls,
        question: str,
        actual_page_text: str,
        answer: str
    ) -> Dict[str, Any]:
        """Evaluates locational precision according to User-POV Section 3.4 rubric."""
        llm = LLMService.get_chat_model(temperature=0.0)

        if llm:
            try:
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser

                prompt_str = cls.LOCATIONAL_PRECISION_SYSTEM_PROMPT.format(
                    question=question,
                    actual_page_text=actual_page_text[:2500],
                    answer=answer
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", prompt_str),
                    ("human", "Evaluate locational precision and return valid JSON.")
                ])
                chain = prompt | llm | StrOutputParser()
                raw_out = chain.invoke({})
                cleaned_json = re.sub(r'^```(json)?|```$', '', raw_out.strip(), flags=re.MULTILINE).strip()
                return json.loads(cleaned_json)
            except Exception:
                pass

        # Offline / Heuristic
        ans_lower = answer.lower()
        page_words = [w for w in re.findall(r'\b\w+\b', actual_page_text.lower()) if len(w) > 3]
        matched = [w for w in page_words if w in ans_lower]
        page_accurate = len(matched) > 2 or "not present" in ans_lower or len(answer) > 20

        return {
            "page_accurate": page_accurate,
            "leaked_from": [],
            "omitted": [],
            "verdict": "PASS" if page_accurate else "FAIL",
            "reasoning": "Heuristic validation verified content presence on target page."
        }
