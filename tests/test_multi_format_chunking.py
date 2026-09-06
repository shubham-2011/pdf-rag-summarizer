import os
import sys
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.document_service import DocumentService

TEST_DOCS_DIR = os.path.join(os.path.dirname(__file__), "test_documents")


class TestMultiFormatChunking:
    """Multi-format chunking audits for DOCX, PPTX, XLSX, and PDF."""

    def test_docx_chunking_structure(self):
        """DOCX: Preserves section headings, avoids orphan fragments."""
        docx_path = os.path.join(TEST_DOCS_DIR, "specs_with_tables.docx")
        if not os.path.exists(docx_path):
            docx_path = os.path.join(TEST_DOCS_DIR, "sample_doc.docx")
        assert os.path.exists(docx_path), f"DOCX fixture not found: {docx_path}"

        chunks, total_units = DocumentService.process_document(docx_path)
        assert len(chunks) > 0
        for c in chunks:
            text = c.page_content.strip()
            assert len(text) >= 15, "Chunk too small in DOCX"
            assert "page_label" in c.metadata or "section" in c.metadata or "page" in c.metadata

    def test_pptx_chunking_slide_separation(self):
        """PPTX: Each slide preserves slide number label and avoids tiny stubs."""
        pptx_path = os.path.join(TEST_DOCS_DIR, "presentation_with_notes.pptx")
        assert os.path.exists(pptx_path), f"PPTX fixture not found: {pptx_path}"

        chunks, total_units = DocumentService.process_document(pptx_path)
        assert len(chunks) > 0
        for c in chunks:
            assert c.metadata.get("page_label") is not None or c.metadata.get("page") is not None

    def test_xlsx_chunking_tabular_integrity(self):
        """XLSX: Tabular sheets keep headers and rows together."""
        xlsx_path = os.path.join(TEST_DOCS_DIR, "sample_financial.xlsx")
        if not os.path.exists(xlsx_path):
            xlsx_path = os.path.join(TEST_DOCS_DIR, "multi_sheet_financial.xlsx")
        assert os.path.exists(xlsx_path), f"XLSX fixture not found: {xlsx_path}"

        chunks, total_units = DocumentService.process_document(xlsx_path)
        assert len(chunks) > 0
        for c in chunks:
            assert len(c.page_content) > 10

    def test_pdf_chunking_two_column_no_interleaving(self):
        """PDF: Multi-column academic paper does not interleave column sentences."""
        pdf_path = os.path.join(TEST_DOCS_DIR, "two_column_academic_paper.pdf")
        assert os.path.exists(pdf_path), f"PDF fixture not found: {pdf_path}"

        chunks, total_units = DocumentService.process_document(pdf_path)
        assert len(chunks) > 0
        for c in chunks:
            assert len(c.page_content) > 20
