import os
import sys
import pytest
import fitz

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import config
from services.pdf_service import PDFService


def _create_minimal_pdf(tmp_path, filename: str, pages: int = 1, text: str = "This is valid test content with sufficient characters.") -> str:
    pdf_path = str(tmp_path / filename)
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        if i == 0 and text:
            page.insert_text((50, 50), text)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


class TestAuditRulesA1:
    """A1 — Pre-embedding audit rules tests."""

    def test_file_size_boundary_49_9mb_accepted(self, tmp_path):
        pdf_path = _create_minimal_pdf(tmp_path, "boundary_49_9.pdf")
        size_49_9_mb = int(49.9 * 1024 * 1024)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=size_49_9_mb)
        assert passed is True, f"Expected 49.9 MB to pass, got: {msg}"

    def test_file_size_boundary_50_0mb_accepted_inclusive(self, tmp_path):
        pdf_path = _create_minimal_pdf(tmp_path, "boundary_50_0.pdf")
        size_50_0_mb = 50 * 1024 * 1024  # Exact config.MAX_FILE_SIZE_BYTES
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=size_50_0_mb)
        assert passed is True, f"Expected 50.0 MB (inclusive) to pass, got: {msg}"

    def test_file_size_boundary_50_1mb_rejected(self, tmp_path):
        pdf_path = _create_minimal_pdf(tmp_path, "boundary_50_1.pdf")
        size_50_1_mb = int(50.1 * 1024 * 1024)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=size_50_1_mb)
        assert passed is False
        assert "exceeds maximum allowed limit" in msg

    def test_page_count_boundary_199_pages_accepted(self, tmp_path):
        pdf_path = _create_minimal_pdf(tmp_path, "pages_199.pdf", pages=199)
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is True, f"Expected 199 pages to pass, got: {msg}"

    def test_page_count_boundary_200_pages_accepted(self, tmp_path):
        pdf_path = _create_minimal_pdf(tmp_path, "pages_200.pdf", pages=200)
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is True, f"Expected 200 pages to pass, got: {msg}"

    def test_page_count_boundary_201_pages_rejected(self, tmp_path):
        pdf_path = _create_minimal_pdf(tmp_path, "pages_201.pdf", pages=201)
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is False
        assert "exceeds maximum limit of 200 pages" in msg

    def test_character_count_boundary_19_chars_rejected(self, tmp_path):
        text_19 = "1234567890123456789"  # exactly 19 chars (< 20 threshold)
        pdf_path = _create_minimal_pdf(tmp_path, "chars_19.pdf", pages=1, text=text_19)
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is False
        assert "OCR is not supported yet" in msg or "no extractable text" in msg

    def test_character_count_boundary_20_chars_accepted(self, tmp_path):
        text_20 = "12345678901234567890"  # exactly 20 chars (threshold is >= 20)
        pdf_path = _create_minimal_pdf(tmp_path, "chars_20.pdf", pages=1, text=text_20)
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is True, f"Expected 20 chars to pass, got: {msg}"

    def test_character_count_boundary_21_chars_accepted(self, tmp_path):
        text_21 = "123456789012345678901"  # 21 chars
        pdf_path = _create_minimal_pdf(tmp_path, "chars_21.pdf", pages=1, text=text_21)
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is True, f"Expected 21 chars to pass, got: {msg}"

    def test_encrypted_pdf_rejected(self, tmp_path):
        pdf_path = str(tmp_path / "encrypted.pdf")
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), "Secret secure document with sufficient length.")
        # Encrypt with owner and user password
        perm = fitz.PDF_PERM_ACCESSIBILITY
        encrypt_meth = fitz.PDF_ENCRYPT_AES_256
        doc.save(pdf_path, encryption=encrypt_meth, owner_pw="owner123", user_pw="user123", permissions=perm)
        doc.close()

        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is False
        assert "password-protected or encrypted" in msg

    def test_scanned_image_only_pdf_explicit_ocr_message(self, tmp_path):
        # A PDF with 0 extractable text characters (scanned page)
        pdf_path = _create_minimal_pdf(tmp_path, "scanned_doc.pdf", pages=1, text="")
        file_size = os.path.getsize(pdf_path)
        passed, msg = PDFService.audit_pdf(pdf_path, file_size=file_size)
        assert passed is False
        assert "OCR is not supported yet" in msg

    def test_zero_byte_file_rejected_distinct_error(self, tmp_path):
        empty_path = str(tmp_path / "empty.pdf")
        with open(empty_path, "wb") as f:
            f.write(b"")
        passed, msg = PDFService.audit_pdf(empty_path, file_size=0)
        assert passed is False
        assert "0 bytes" in msg

    def test_txt_renamed_to_pdf_rejected_distinct_error(self, tmp_path):
        fake_pdf = str(tmp_path / "fake_renamed.pdf")
        with open(fake_pdf, "w", encoding="utf-8") as f:
            f.write("This is a plain text file that someone renamed to .pdf")
        file_size = os.path.getsize(fake_pdf)
        passed, msg = PDFService.audit_pdf(fake_pdf, file_size=file_size)
        assert passed is False
        assert "Missing %PDF file header" in msg or "Corrupted or invalid" in msg

    def test_corrupt_header_rejected_distinct_error(self, tmp_path):
        corrupt_path = str(tmp_path / "corrupt_header.pdf")
        with open(corrupt_path, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04GARBAGE_HEADER")
        file_size = os.path.getsize(corrupt_path)
        passed, msg = PDFService.audit_pdf(corrupt_path, file_size=file_size)
        assert passed is False
        assert "Corrupted or invalid PDF structure" in msg
