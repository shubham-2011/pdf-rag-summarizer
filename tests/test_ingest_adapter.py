import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

# --- Path Setup ---
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import config
from services.ingest_adapter import (
    IngestAdapter,
    UnsupportedFormatError,
    LibreOfficeNotFoundError,
    ConversionTimeoutError,
    ConversionExecutionError
)


class TestIngestAdapter:
    """Comprehensive test suite for IngestAdapter conversion pipeline."""

    def test_detect_format_magic_pdf(self, tmp_path):
        """Magic bytes %PDF are detected as format 'pdf'."""
        pdf_file = tmp_path / "sample.pdf"
        pdf_file.write_bytes(b"%PDF-1.7\nSample content")
        assert IngestAdapter.detect_format(str(pdf_file)) == "pdf"

    def test_detect_format_magic_zip_docx(self, tmp_path):
        """Magic bytes PK... with .docx extension are detected as 'docx'."""
        docx_file = tmp_path / "sample.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")
        assert IngestAdapter.detect_format(str(docx_file)) == "docx"

    def test_detect_format_magic_zip_pptx(self, tmp_path):
        """Magic bytes PK... with .pptx extension are detected as 'pptx'."""
        pptx_file = tmp_path / "slides.pptx"
        pptx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")
        assert IngestAdapter.detect_format(str(pptx_file)) == "pptx"

    def test_detect_format_magic_ole_doc(self, tmp_path):
        """Magic bytes OLE compound binary are detected as 'doc'."""
        doc_file = tmp_path / "legacy.doc"
        doc_file.write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1")
        assert IngestAdapter.detect_format(str(doc_file)) == "doc"

    def test_pdf_pass_through_unmodified(self, tmp_path):
        """PDF files pass through with zero conversion overhead."""
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj")
        
        res = IngestAdapter.to_pdf(str(pdf_file))
        assert res.pdf_path == str(pdf_file)
        assert res.original_path == str(pdf_file)
        assert res.format == "pdf"
        assert res.was_converted is False
        assert res.unit_source == "native-pdf"

    def test_flag_disabled_rejects_non_pdf(self, tmp_path, monkeypatch):
        """When MULTIFORMAT_ENABLED is false, non-PDFs raise UnsupportedFormatError."""
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", False)
        docx_file = tmp_path / "report.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")

        with pytest.raises(UnsupportedFormatError) as excinfo:
            IngestAdapter.to_pdf(str(docx_file))
        assert "MULTIFORMAT_ENABLED=false" in str(excinfo.value)

    def test_disallowed_format_rejected_when_flag_enabled(self, tmp_path, monkeypatch):
        """Formats not in MULTIFORMAT_FORMATS are rejected."""
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", True)
        monkeypatch.setattr(config, "MULTIFORMAT_FORMATS", ["docx", "pptx"])
        
        xls_file = tmp_path / "financials.xls"
        xls_file.write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1")

        with pytest.raises(UnsupportedFormatError) as excinfo:
            IngestAdapter.to_pdf(str(xls_file))
        assert "not enabled for conversion" in str(excinfo.value)

    def test_missing_libreoffice_raises_typed_error(self, tmp_path, monkeypatch):
        """When LibreOffice executable is not found and allow_fallback=False, LibreOfficeNotFoundError is raised."""
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", True)
        monkeypatch.setattr(config, "MULTIFORMAT_FORMATS", ["docx"])
        monkeypatch.setattr(IngestAdapter, "find_libreoffice_binary", lambda: None)

        docx_file = tmp_path / "spec.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")

        with pytest.raises(LibreOfficeNotFoundError) as excinfo:
            IngestAdapter.to_pdf(str(docx_file), allow_fallback=False)
        assert "executable was not found" in str(excinfo.value)

    def test_missing_libreoffice_fallback_allowed(self, tmp_path, monkeypatch):
        """When LibreOffice executable is not found and allow_fallback=True, returns native-ast result."""
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", True)
        monkeypatch.setattr(config, "MULTIFORMAT_FORMATS", ["docx"])
        monkeypatch.setattr(IngestAdapter, "find_libreoffice_binary", lambda: None)

        docx_file = tmp_path / "spec.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")

        res = IngestAdapter.to_pdf(str(docx_file), allow_fallback=True)
        assert res.pdf_path is None
        assert res.original_path == str(docx_file)
        assert res.format == "docx"
        assert res.was_converted is False
        assert res.unit_source == "native-ast"

    def test_rag_disable_converter_flag(self, tmp_path, monkeypatch):
        """When RAG_DISABLE_CONVERTER is active and allow_fallback=True, returns native-ast immediately."""
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", True)
        monkeypatch.setattr(config, "MULTIFORMAT_FORMATS", ["docx"])
        monkeypatch.setattr(config, "RAG_DISABLE_CONVERTER", True)

        docx_file = tmp_path / "spec.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")

        res = IngestAdapter.to_pdf(str(docx_file), allow_fallback=True)
        assert res.pdf_path is None
        assert res.was_converted is False
        assert res.unit_source == "native-ast"

    def test_successful_conversion_mocked(self, tmp_path, monkeypatch):
        """Successful LibreOffice conversion produces effective PDF and cleans up temp profile."""
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", True)
        monkeypatch.setattr(config, "MULTIFORMAT_FORMATS", ["docx"])
        monkeypatch.setattr(config, "RAG_DISABLE_CONVERTER", False)
        monkeypatch.setattr(IngestAdapter, "find_libreoffice_binary", lambda: "soffice")
        monkeypatch.setattr(IngestAdapter, "get_renderer_id", lambda: "libreoffice-7.6.4")

        docx_file = tmp_path / "presentation.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")

        expected_pdf = tmp_path / "presentation.pdf"

        def mock_popen(cmd, *args, **kwargs):
            expected_pdf.write_bytes(b"%PDF-1.7\nConverted from docx")
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.pid = 12345
            mock_proc.communicate.return_value = (b"Converted presentation.docx -> presentation.pdf", b"")
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            res = IngestAdapter.to_pdf(str(docx_file))
            assert res.pdf_path == str(expected_pdf)
            assert res.original_path == str(docx_file)
            assert res.format == "docx"
            assert res.was_converted is True
            assert res.unit_source == "libreoffice-7.6.4"
            assert os.path.exists(res.pdf_path)

    def test_conversion_timeout_raises_typed_error(self, tmp_path, monkeypatch):
        """Conversion exceeding timeout limit raises ConversionTimeoutError."""
        import subprocess
        monkeypatch.setattr(config, "MULTIFORMAT_ENABLED", True)
        monkeypatch.setattr(config, "MULTIFORMAT_FORMATS", ["docx"])
        monkeypatch.setattr(config, "RAG_DISABLE_CONVERTER", False)
        monkeypatch.setattr(config, "CONVERSION_TIMEOUT_SECONDS", 1)
        monkeypatch.setattr(IngestAdapter, "find_libreoffice_binary", lambda: "soffice")

        docx_file = tmp_path / "huge.docx"
        docx_file.write_bytes(b"PK\x03\x04\x14\x00\x06\x00")

        def mock_popen(cmd, *args, **kwargs):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="soffice", timeout=1)
            return mock_proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            with pytest.raises(ConversionTimeoutError) as excinfo:
                IngestAdapter.to_pdf(str(docx_file))
            assert "timed out" in str(excinfo.value)

