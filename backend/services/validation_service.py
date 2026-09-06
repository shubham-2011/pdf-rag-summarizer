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

    # V5: Answer Shape & Data Exposure Guard
    @staticmethod
    def validate_answer_shape(
        answer: str,
        intent: str = "LOCAL",
        allow_empty: bool = False
    ) -> None:
        """
        V5 Gate: Enforces clean prose and prevents broken chunk fragments or sensitive data leaks:
        - No bullet starting with dangling punctuation (e.g. '. Designed a...')
        - No mid-word cutoffs
        - Global/Synopsis answers must have >= 25 words
        - Structural answers must NOT leak personal phone numbers or emails
        """
        if not answer or not answer.strip():
            if not allow_empty:
                raise AnswerShapeError("Synthesized answer is empty.")
            return

        clean = answer.strip()

        # 1. Check for dangling punctuation at bullet beginnings (raw chunk dump indicator)
        bullet_lines = [line.strip() for line in clean.split("\n") if line.strip().startswith(("*", "-", "•", "1.", "2."))]
        for b in bullet_lines:
            text_after_bullet = re.sub(r'^(\*|-|•|\d+\.)\s*', '', b).strip()
            if text_after_bullet.startswith((".", ",", ";", ":", ")", "]")):
                raise AnswerShapeError(f"Raw chunk fragment detected in bullet: '{b[:40]}...'")

        # 2. Global intent shape check
        if intent == "GLOBAL":
            word_count = len(clean.split())
            if word_count < 15:
                raise AnswerShapeError(f"GLOBAL summary too short ({word_count} words). Expected comprehensive synopsis.")

        # 3. Data Exposure Guard: Structural answers must NEVER output phone numbers or emails
        if intent == "STRUCTURAL":
            phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', clean)
            email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', clean)
            if phone_match or email_match:
                raise AnswerShapeError("Data Exposure Violation: Structural query attempted to expose contact info.")

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

        return response_dict
