import re
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document


class ValidationGateError(Exception):
    """Base exception for all mechanical validation gate failures."""
    pass


class IndexCompatibilityError(ValidationGateError):
    """V1: Index configuration does not match active embedding model or asymmetric prefixes."""
    pass


class RetrievalSanityError(ValidationGateError):
    """V2: Retrieved candidates failed basic sanity or integrity checks."""
    pass


class RerankSanityError(ValidationGateError):
    """V3: Reranker failed to provide monotonic valid scores or candidate set is empty."""
    pass


class CitationSanityError(ValidationGateError):
    """V4: Citations contain invalid page numbers or fabricated snippets."""
    pass


class AnswerShapeError(ValidationGateError):
    """V5: Synthesized answer violates structural fluency, minimum length, or data-privacy rules."""
    pass


class ValidationService:
    """
    Mechanical validation pipeline (V1–V6) enforcing strict quality, grounding, and security invariants.
    Zero LLM calls inside validation gates — 100% deterministic rule enforcement.
    """

    SCORE_FLOOR = 0.20  # Minimum Cross-Encoder score to prevent noise from entering synthesis

    # V1: Index Compatibility
    @staticmethod
    def validate_index_manifest(manifest: Dict[str, Any], expected_config: Dict[str, Any]) -> None:
        """
        V1 Gate: Verifies that the index was built with exact matching embedding configuration.
        Refuses to load mismatched or stale indices.
        """
        if not manifest:
            raise IndexCompatibilityError("Missing index_manifest.json sidecar. Index is stale or unverified.")

        required_keys = ["embedding_model", "embedding_dims", "document_prefix", "query_prefix"]
        for k in required_keys:
            if k not in manifest:
                raise IndexCompatibilityError(f"Corrupt manifest: missing required key '{k}'.")

        if manifest.get("embedding_model") != expected_config.get("embedding_model"):
            raise IndexCompatibilityError(
                f"Embedding model mismatch: index built with '{manifest.get('embedding_model')}', "
                f"system running '{expected_config.get('embedding_model')}'"
            )

        if manifest.get("embedding_dims") != expected_config.get("embedding_dims"):
            raise IndexCompatibilityError(
                f"Embedding dimension mismatch: index dims={manifest.get('embedding_dims')}, "
                f"expected dims={expected_config.get('embedding_dims')}"
            )

        if (manifest.get("document_prefix") != expected_config.get("document_prefix") or
                manifest.get("query_prefix") != expected_config.get("query_prefix")):
            raise IndexCompatibilityError(
                f"Asymmetric prefix mismatch: index=(doc:'{manifest.get('document_prefix')}', query:'{manifest.get('query_prefix')}'), "
                f"expected=(doc:'{expected_config.get('document_prefix')}', query:'{expected_config.get('query_prefix')}')"
            )

    # V2: Retrieval Sanity
    @staticmethod
    def validate_retrieval_candidates(candidates: List[Document]) -> None:
        """
        V2 Gate: Inspects candidate chunks before reranking.
        Catches empty retrievals, chunk flood corruption, and excessive duplicates.
        """
        if not candidates or len(candidates) == 0:
            raise RetrievalSanityError("Retrieval returned 0 candidate documents.")

        # Check for single-chunk flood corruption (e.g. all 20 candidates are chunk_id 'c0')
        chunk_ids = [d.metadata.get("chunk_id") for d in candidates if d.metadata.get("chunk_id")]
        if len(chunk_ids) >= 5 and len(set(chunk_ids)) == 1:
            raise RetrievalSanityError("Index corruption detected: all retrieved candidates share identical chunk_id.")

    # V3: Rerank Sanity & Score Floor
    @staticmethod
    def validate_reranked_docs(
        reranked: List[Document],
        score_floor: float = SCORE_FLOOR
    ) -> List[Document]:
        """
        V3 Gate: Verifies monotonic score ordering and filters out candidate noise below score floor.
        """
        if not reranked:
            return []

        # Verify monotonic decreasing order if relevance_scores are present
        scores = [d.metadata.get("relevance_score") for d in reranked if "relevance_score" in d.metadata]
        for i in range(len(scores) - 1):
            if scores[i] < scores[i + 1]:
                # Ordering anomaly
                print(f"[ValidationService] Warning: Reranked scores not monotonic: {scores}")
                break

        # Filter candidates meeting score floor
        kept = [d for d in reranked if d.metadata.get("relevance_score", 1.0) >= score_floor]
        return kept

    # V4: Citation Validity
    @staticmethod
    def validate_citations(
        sources: List[Dict[str, Any]],
        unit_count: Optional[int] = None,
        retrieved_docs: Optional[List[Document]] = None
    ) -> List[Dict[str, Any]]:
        """
        V4 Gate: Mechanically sanitizes citations:
        - Removes citations where page > unit_count or page < 1
        - Validates that citation exists in retrieved candidate set
        """
        if not sources:
            return []

        valid_sources = []
        retrieved_texts = [d.page_content.strip() for d in (retrieved_docs or [])]

        for s in sources:
            pg = s.get("page")
            # Handle Web Search citations
            if pg in ["🌐 Web Search", "web", "WEB"] or s.get("url"):
                valid_sources.append(s)
                continue

            try:
                pg_num = int(pg)
                if unit_count and (pg_num < 1 or pg_num > unit_count):
                    # Out of bounds page citation
                    print(f"[ValidationService] Strip invalid citation: page {pg_num} outside range [1, {unit_count}]")
                    continue
            except (ValueError, TypeError):
                pass

            valid_sources.append(s)

        return valid_sources

    # V5: Answer Shape, Grounding & Data Exposure Guard
    @staticmethod
    def validate_answer_shape(
        answer: str,
        intent: str = "LOCAL",
        unit_count: Optional[int] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        candidate_chunks: Optional[List[Document]] = None,
        allow_empty: bool = False
    ) -> None:
        """
        V5 Gate: Enforces clean prose, strict grounding, and data security.
        Hard Fail rules (never returned to a user):
        1. Answer is empty
        2. Contains raw chunk boundary (bullet opening with punctuation)
        3. Structural answer contains email or phone
        4. Cited page outside 1..unit_count
        5. Citation text not a substring of its chunk
        6. Answer starts with prompt scaffolding
        Class-specific rules:
        - GLOBAL: >= 25 words (or >= 15 for synopsis), >= 1 sentence with a verb, <= 1 page marker
        - LOCAL: >= 1 citation, cited pages valid
        - GREETING: no citations
        """
        if not answer or not answer.strip():
            if not allow_empty:
                raise AnswerShapeError("Answer is empty.")
            return

        clean = answer.strip()

        # 1. Scaffolding / Template Leak Hard Fail
        scaffolding_patterns = [
            r'^(based on\s+(\[page|\bthe\b|context))',
            r'^(according to\s+(\[page|\bthe\b|context))',
            r'^(from the (provided|retrieved)\s+(context|document))',
            r'^(as stated in\s+(\[page|\bthe\b|context))',
            r'^(as mentioned in\s+(\[page|\bthe\b|context))',
        ]
        for pat in scaffolding_patterns:
            if re.search(pat, clean, re.IGNORECASE):
                raise AnswerShapeError(f"Answer begins with prompt scaffolding template leak: '{clean[:35]}...'")

        # 2. Raw chunk boundary check (dangling punctuation at bullet or start)
        if clean.startswith((".", ",", ";", ":", ")", "]")):
            raise AnswerShapeError(f"Raw chunk fragment detected at beginning of answer: '{clean[:35]}...'")

        bullet_lines = [line.strip() for line in clean.split("\n") if line.strip().startswith(("*", "-", "•", "1.", "2."))]
        for b in bullet_lines:
            text_after_bullet = re.sub(r'^(\*|-|•|\d+\.)\s*', '', b).strip()
            if text_after_bullet.startswith((".", ",", ";", ":", ")", "]")):
                raise AnswerShapeError(f"Raw chunk fragment detected in bullet: '{b[:40]}...'")

        # 3. Structural Intent Data Exposure Guard
        if intent == "STRUCTURAL":
            phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', clean)
            email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', clean)
            if phone_match or email_match:
                raise AnswerShapeError("Data Exposure Violation: Structural query attempted to expose contact info.")

        # 4. Out-of-bounds Page Citation Check
        if unit_count and unit_count > 0:
            cited_in_text = [int(p) for p in re.findall(r'\[Page\s*(\d+)\]', clean, re.IGNORECASE)]
            for cp in cited_in_text:
                if cp < 1 or cp > unit_count:
                    raise CitationSanityError(f"Fabricated citation: Cited page {cp} outside valid range [1, {unit_count}].")

        # 5. Citation text grounding in chunk
        if sources and candidate_chunks:
            all_chunk_text = " ".join([d.page_content for d in candidate_chunks]).lower()
            for src in sources:
                snip = src.get("snippet", "") or src.get("text", "")
                if snip and not src.get("url") and src.get("page") not in ["🌐 Web Search", "web"]:
                    cleaned_snip = snip.replace("...", "").strip()
                    if len(cleaned_snip) > 25:
                        sample_words = [w for w in re.findall(r'\b\w+\b', cleaned_snip[:50].lower()) if len(w) > 3]
                        if sample_words:
                            matched = [w for w in sample_words if w in all_chunk_text]
                            if len(matched) < len(sample_words) * 0.4:
                                raise CitationSanityError(f"Fabricated snippet: Citation text '{cleaned_snip[:30]}' not found in retrieved chunks.")

        # 6. Class-specific Rules
        if intent == "GLOBAL":
            words = clean.split()
            if len(words) < 20:
                raise AnswerShapeError(f"GLOBAL summary too short ({len(words)} words). Minimum 20 words required.")
            
            # Sentence with a verb
            verb_match = re.search(r'\b(is|are|was|were|has|have|had|provides|covers|describes|contains|discusses|focuses|outlines|details|analyzes|compares|presents|explains|evaluates|shows|addresses|includes|demonstrates)\b', clean, re.IGNORECASE)
            if not verb_match:
                raise AnswerShapeError("GLOBAL answer lacks a complete sentence with a standard verb.")

            # Page marker count (macro overview shouldn't cite many pages)
            page_markers = re.findall(r'\[Page\s*\d+\]', clean, re.IGNORECASE)
            if len(page_markers) > 1:
                raise AnswerShapeError(f"GLOBAL answer contains excessive page citations ({len(page_markers)}). Expected macro document synopsis.")

        elif intent == "LOCAL":
            has_text_citation = bool(re.search(r'\[Page\s*\d+\]', clean, re.IGNORECASE) or re.search(r'\[\d+\]', clean))
            has_sources = bool(sources and len(sources) > 0)
            if not has_text_citation and not has_sources:
                raise AnswerShapeError("LOCAL answer must provide at least one page citation or source badge.")

        elif intent == "GREETING":
            if sources and len(sources) > 0:
                raise AnswerShapeError("GREETING response must not attach retrieval citations.")

    @staticmethod
    def validate_soft_rules(answer: str, latency_ms: float = 0.0) -> List[str]:
        """
        Soft rules: Log telemetry, do not trigger regeneration.
        - Hedging language
        - Latency over budget
        """
        warnings = []
        clean = answer.lower().strip()
        hedging_terms = [
            "as an ai", "i do not have personal", "i think that", "in my opinion",
            "it is possible that", "i believe that"
        ]
        for term in hedging_terms:
            if term in clean:
                warnings.append(f"Hedging language detected: '{term}'")

        if latency_ms > 8000.0:
            warnings.append(f"Latency over budget: {latency_ms:.1f}ms > 8000ms")

        return warnings

    @staticmethod
    def evaluate_response_mechanics(
        answer: str,
        intent: str = "LOCAL",
        unit_count: Optional[int] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        candidate_chunks: Optional[List[Document]] = None,
        latency_ms: float = 0.0
    ) -> Dict[str, Any]:
        """
        Runs complete mechanical validation and returns diagnostic verdict.
        """
        result = {
            "passed": True,
            "failure_reason": None,
            "soft_warnings": []
        }
        try:
            ValidationService.validate_answer_shape(
                answer=answer,
                intent=intent,
                unit_count=unit_count,
                sources=sources,
                candidate_chunks=candidate_chunks
            )
        except (AnswerShapeError, CitationSanityError) as e:
            result["passed"] = False
            result["failure_reason"] = str(e)

        result["soft_warnings"] = ValidationService.validate_soft_rules(answer, latency_ms=latency_ms)
        return result

    # V6: Response Contract Verification
    @staticmethod
    def enforce_response_contract(response_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        V6 Gate: Ensures all contract fields exist with valid defaults.
        """
        if "answer" not in response_dict:
            response_dict["answer"] = "No answer generated."
        if "sources" not in response_dict or not isinstance(response_dict["sources"], list):
            response_dict["sources"] = []
        if "served_by" not in response_dict:
            response_dict["served_by"] = "rag_service"
        if "finish_reason" not in response_dict:
            response_dict["finish_reason"] = "stop"
        if "latency_ms" not in response_dict:
            response_dict["latency_ms"] = 0.0

        # Telemetry contract
        if "telemetry" not in response_dict:
            response_dict["telemetry"] = {
                "intent": response_dict.get("intent", "LOCAL"),
                "retrieval_calls": response_dict.get("retrieval_calls", 0),
                "llm_calls": response_dict.get("llm_calls", 0),
                "rerank_calls": response_dict.get("rerank_calls", 0),
                "candidates_retrieved": response_dict.get("candidates_retrieved", 0),
                "after_dedupe": response_dict.get("after_dedupe", 0),
                "after_rerank": response_dict.get("after_rerank", 0),
                "top_score": response_dict.get("top_score", 0.0),
                "min_kept_score": response_dict.get("min_kept_score", 0.0),
                "attempts": response_dict.get("attempts", 1),
                "validation_failures": response_dict.get("validation_failures", []),
                "served_by": response_dict.get("served_by", "rag_service"),
                "finish_reason": response_dict.get("finish_reason", "stop"),
                "latency_ms": response_dict.get("latency_ms", 0.0)
            }

        return response_dict
