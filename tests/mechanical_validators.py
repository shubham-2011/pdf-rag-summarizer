import re
from typing import Dict, Any, List, Optional, Tuple

class MechanicalValidators:
    """Deterministic, Non-LLM mechanical validators for Structural queries and Citations."""

    @staticmethod
    def validate_structural_response(
        response: Dict[str, Any],
        expected_metadata: Dict[str, Any],
        subkind: str
    ) -> Dict[str, Any]:
        """
        Validates that:
        1. Query was handled by 'registry_metadata' strategy (zero LLM generation).
        2. No vector retrieval chunks/citations were attached.
        3. The numerical/factual values in the answer match the SQLite registry exactly.
        """
        answer = response.get("answer", "")
        strategy = response.get("strategy", "")
        sources = response.get("sources", [])
        question_class = response.get("question_class", "")

        is_metadata_strategy = (strategy == "registry_metadata")
        zero_citations = (len(sources) == 0)

        # Check subkind-specific value
        actual_val = None
        expected_val = None
        match_success = False
        failure_reasons = []

        if not is_metadata_strategy:
            failure_reasons.append(f"Routing failure: Answer came from '{strategy}' instead of 'registry_metadata'.")
        if not zero_citations:
            failure_reasons.append(f"Invalid citations attached: Expected 0 citations for structural query, found {len(sources)}.")

        if subkind in ["page_count", "slide_count", "sheet_count"]:
            expected_val = expected_metadata.get("unit_count", 1)
            num_match = re.search(r'\b(\d+)\s*(page|slide|sheet)s?\b', answer, re.IGNORECASE)
            if num_match:
                actual_val = int(num_match.group(1))
            else:
                # General integer match
                int_match = re.search(r'\b(\d+)\b', answer)
                actual_val = int(int_match.group(1)) if int_match else None
            
            match_success = (actual_val == expected_val)
            if not match_success:
                failure_reasons.append(f"Expected {expected_val} {subkind}, but got {actual_val} in answer: '{answer}'.")

        elif subkind == "section_count":
            expected_val = expected_metadata.get("section_count", 0)
            num_match = re.search(r'\b(\d+)\s*section', answer, re.IGNORECASE)
            actual_val = int(num_match.group(1)) if num_match else None
            match_success = (actual_val == expected_val)
            if not match_success:
                failure_reasons.append(f"Expected {expected_val} sections, but parsed {actual_val}.")

        elif subkind == "section_list":
            expected_sections = expected_metadata.get("sections", [])
            if not expected_sections:
                match_success = ("does not define" in answer or "outline" in answer)
            else:
                match_success = any(sec.lower() in answer.lower() for sec in expected_sections)
            if not match_success:
                failure_reasons.append(f"Answer did not list expected sections: {expected_sections}")

        elif subkind == "file_format":
            expected_fmt = expected_metadata.get("format", "pdf").lower()
            match_success = expected_fmt in answer.lower()
            if not match_success:
                failure_reasons.append(f"Expected format {expected_fmt} not found in answer.")

        elif subkind == "author_date":
            expected_author = expected_metadata.get("authors", "")
            if expected_author:
                match_success = expected_author.lower() in answer.lower()
            else:
                match_success = True
            if not match_success:
                failure_reasons.append(f"Expected author {expected_author} not found in answer.")

        else:
            match_success = len(answer) > 10

        verdict = "PASS" if (match_success and is_metadata_strategy and zero_citations) else "FAIL"

        return {
            "verdict": verdict,
            "subkind": subkind,
            "strategy": strategy,
            "expected_val": expected_val,
            "actual_val": actual_val,
            "match_success": match_success,
            "is_metadata_strategy": is_metadata_strategy,
            "zero_citations": zero_citations,
            "failure_reasons": failure_reasons
        }

    @staticmethod
    def verify_citations_mechanically(
        sources: List[Dict[str, Any]],
        doc_pages_text: Dict[int, str],
        total_pages: int
    ) -> Dict[str, Any]:
        """
        Mechanical citation verification:
        1. Does page P exist in the document? (else invalid_page)
        2. Does cited snippet / text exist on page P? (else invalid_span)
        3. Is the text at P:S non-empty? (else empty_citation)
        4. Multi-page uniformity regression check: Do all citations point to page 1 on a multi-page doc?
        """
        if not sources:
            return {
                "verdict": "PASS",
                "citations_count": 0,
                "valid_citations": 0,
                "citation_validity_rate": 1.0,
                "issues": []
            }

        issues = []
        valid_count = 0
        pages_cited = []

        for i, src in enumerate(sources):
            if src.get("origin") == "web":
                valid_count += 1
                continue

            page_raw = src.get("page", 1)
            try:
                page_num = int(page_raw)
            except Exception:
                page_num = 1

            pages_cited.append(page_num)

            # 1. Page bounds check
            if page_num < 1 or page_num > total_pages:
                issues.append(f"invalid_page: Citation [c{i}] references page {page_num}, but document has {total_pages} pages.")
                continue

            # 2. Non-empty text check
            text = src.get("text", "") or src.get("snippet", "")
            if not text.strip():
                issues.append(f"empty_citation: Citation [c{i}] contains empty text content.")
                continue

            # 3. Grounded in page text
            page_text = doc_pages_text.get(page_num, "")
            # Check if key words from snippet are on the designated page
            sample_words = [w for w in re.findall(r'\b\w+\b', text[:100].lower()) if len(w) > 3]
            if sample_words and page_text:
                matched_words = [w for w in sample_words if w in page_text.lower()]
                if len(matched_words) < len(sample_words) * 0.4:
                    issues.append(f"invalid_span: Citation [c{i}] text not found on page {page_num}.")
                    continue

            valid_count += 1

        # 4. Multi-page uniformity check (regression guard for "all-citations-point-to-page-1")
        if total_pages > 1 and len(pages_cited) >= 3:
            if all(p == 1 for p in pages_cited):
                issues.append("suspicious_uniformity: All citations uniformly pointed to page 1 on a multi-page document.")

        validity_rate = round(valid_count / len(sources), 4) if sources else 1.0
        verdict = "PASS" if validity_rate >= 0.98 and not any("suspicious_uniformity" in is_str for is_str in issues) else "FAIL"

        return {
            "verdict": verdict,
            "citations_count": len(sources),
            "valid_citations": valid_count,
            "citation_validity_rate": validity_rate,
            "issues": issues
        }
