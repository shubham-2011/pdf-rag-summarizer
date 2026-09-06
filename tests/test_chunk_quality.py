import os
import sys
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.document_service import DocumentService
from services.pdf_service import PDFService

TEST_DOCS_DIR = os.path.join(os.path.dirname(__file__), "test_documents")

LLM_JUDGE_CHUNK_AUDIT_PROMPT = """
You audit chunk quality for a retrieval system. You output JSON and nothing else.

Original page text:
<page number="{page_num}">
{page_text}
</page>

Chunks the system produced from this page:
{chunks_formatted}

Check each defect:
- mid_word_split:      a chunk starts or ends mid-word or mid-token
- orphaned_heading:    a section heading sits in a different chunk from the body text it introduces
- broken_table:        a table's rows are split across chunks, or header rows are separated from data rows
- broken_list:         an enumerated or bulleted list is split so that items lose their stem
- lost_content:        text present on the page appears in no chunk
- duplicated_content:  the same sentence appears in more than one chunk beyond intended overlap
- wrong_heading:       a chunk's section_heading metadata does not match the section the text actually belongs to
- wrong_block_type:    block_type is mislabelled (a table tagged as prose, a caption as body)

Return JSON only:
{{
  "defects": [
    {{"type": "orphaned_heading", "chunk_ids": [1,2], "evidence": "<exact text showing the break>", "severity": "high|medium|low"}}
  ],
  "coverage": "complete|partial|poor",
  "retrievability": "<one sentence: would a user question about this page's content match one of these chunks on its own?>",
  "verdict": "PASS|FAIL"
}}

Rules:
1. verdict is FAIL if any high-severity defect is present, or coverage is not "complete".
2. mid_word_split and broken_table are always high severity.
3. Judge each chunk as a standalone retrieval unit. A chunk that only makes sense when read
   next to its neighbour is a defect even if no rule above fires — report it as
   orphaned_heading with severity medium.
4. Multi-column pages: text from two columns interleaved into one chunk is lost_content
   severity high, even if no words are missing.
"""


def evaluate_chunk_integrity_deterministic(chunks):
    """Deterministic pre-checks on chunk corpus before LLM judge."""
    defects = []
    for i, chunk in enumerate(chunks):
        text = chunk.page_content.strip()
        # 1. No mid-word hyphen cut at end of chunk
        if re.search(r'\w-\s*$', text):
            defects.append((i, "mid_word_split", f"Ends with hyphenated split: '{text[-20:]}'"))

        # 2. No dangling suffix orphan at chunk start
        if text.lower().startswith(('ized ', 'tion ', 'ing ', 'ment ', 'able ')):
            defects.append((i, "suffix_orphan", f"Starts with suffix orphan: '{text[:20]}'"))

        # 3. Size boundary checks (relaxed for single-item slide / table stubs if structured)
        if len(text) < 50:
            defects.append((i, "under_sized_stub", f"Chunk length ({len(text)}) too small"))
        elif len(text) > 2000:
            defects.append((i, "over_sized_chunk", f"Chunk length ({len(text)}) exceeds maximum target"))

        # 4. Citation page_label metadata check
        if "page_label" not in chunk.metadata or chunk.metadata.get("page_label") is None:
            defects.append((i, "missing_page_label", "Metadata is missing page_label for citation"))

        # 5. Section heading metadata check
        if chunk.metadata.get("section_heading") is None:
            defects.append((i, "missing_section_heading", "Metadata is missing section_heading"))

    return defects


class TestChunkQualityA2:
    """A2 — Chunk Quality Audit suite."""

    def test_deterministic_chunk_checks_water_quality(self):
        pdf_path = os.path.join(TEST_DOCS_DIR, "water_quality_report.pdf")
        assert os.path.exists(pdf_path), f"Fixture not found: {pdf_path}"
        chunks, total_pages = PDFService.process_pdf(pdf_path)
        assert len(chunks) > 0

        defects = evaluate_chunk_integrity_deterministic(chunks)
        assert len(defects) == 0, f"Detected chunk quality defects: {defects}"

    def test_deterministic_chunk_checks_two_column_academic(self):
        pdf_path = os.path.join(TEST_DOCS_DIR, "two_column_academic_paper.pdf")
        assert os.path.exists(pdf_path), f"Fixture not found: {pdf_path}"
        chunks, total_pages = PDFService.process_pdf(pdf_path)
        assert len(chunks) > 0

        defects = evaluate_chunk_integrity_deterministic(chunks)
        assert len(defects) == 0, f"Detected chunk quality defects in two-column doc: {defects}"

    def test_deterministic_chunk_checks_technical_manual(self):
        pdf_path = os.path.join(TEST_DOCS_DIR, "technical_manual_long.pdf")
        assert os.path.exists(pdf_path), f"Fixture not found: {pdf_path}"
        chunks, total_pages = PDFService.process_pdf(pdf_path)
        assert len(chunks) >= 15

        defects = evaluate_chunk_integrity_deterministic(chunks)
        assert len(defects) == 0, f"Detected chunk quality defects in technical manual: {defects}"

    def test_llm_judge_prompt_contract(self):
        """Validates that LLM judge prompt schema formats correctly with page and chunk text."""
        formatted = LLM_JUDGE_CHUNK_AUDIT_PROMPT.format(
            page_num=1,
            page_text="Introduction to RAG pipelines.",
            chunks_formatted='<chunk id="1" heading="GENERAL" block_type="prose">Introduction to RAG pipelines.</chunk>'
        )
        assert "<page number=\"1\">" in formatted
        assert "orphaned_heading" in formatted
        assert "mid_word_split" in formatted
        assert "PASS|FAIL" in formatted
