import os
import sys
import shutil
import subprocess
import tempfile
import uuid
import logging
import threading
from typing import NamedTuple, Optional
from pathlib import Path

import config

logger = logging.getLogger(__name__)

_conversion_semaphore: Optional[threading.BoundedSemaphore] = None
_cached_renderer_id: Optional[str] = None


def get_conversion_semaphore() -> threading.BoundedSemaphore:
    global _conversion_semaphore
    if _conversion_semaphore is None:
        limit = max(1, getattr(config, "CONVERSION_SEMAPHORE_LIMIT", 2))
        _conversion_semaphore = threading.BoundedSemaphore(limit)
    return _conversion_semaphore


class IngestAdapterError(Exception):
    """Base exception for all ingest adapter failures."""
    pass


class UnsupportedFormatError(IngestAdapterError):
    """Raised when an uploaded file format is not supported or disabled."""
    pass


class LibreOfficeNotFoundError(IngestAdapterError):
    """Raised when LibreOffice binary cannot be located on the system."""
    pass


class ConversionTimeoutError(IngestAdapterError):
    """Raised when LibreOffice conversion exceeds the timeout limit."""
    pass


class ConversionExecutionError(IngestAdapterError):
    """Raised when LibreOffice conversion process exits with non-zero status or fails to produce a valid PDF."""
    pass


class ConversionResult(NamedTuple):
    pdf_path: Optional[str]
    original_path: str
    format: str
    was_converted: bool
    unit_source: str


def _kill_process_tree(proc: subprocess.Popen):
    """Safely kills a process and all its descendants."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception as ex:
        logger.warning(f"Failed to kill process tree for PID {proc.pid}: {ex}")
    try:
        proc.kill()
    except Exception:
        pass


class IngestAdapter:
    """
    Additive conversion adapter placed in front of the document ingestion pipeline.
    Converts supported non-PDF formats (DOCX, PPTX, DOC, PPT) into PDF via headless LibreOffice or MS Word COM.
    Preserves existing downstream pipeline (PyMuPDF layout extraction, chunking, metadata registry) untouched.
    """

    MAGIC_PDF = b"%PDF"
    MAGIC_ZIP = b"PK\x03\x04"
    MAGIC_OLE = b"\xD0\xCF\x11\xE0"

    SUPPORTED_EXTENSIONS = {
        "pdf": "pdf",
        "docx": "docx",
        "doc": "doc",
        "pptx": "pptx",
        "ppt": "ppt",
        "xlsx": "xlsx",
        "xls": "xls"
    }

    @classmethod
    def get_renderer_id(cls) -> str:
        """
        Introspects and returns renderer identity string
        (e.g. 'libreoffice-7.6.4' or 'word-16.0' or 'native-ast').
        """
        global _cached_renderer_id
        if _cached_renderer_id is not None:
            return _cached_renderer_id

        # Windows MS Word COM check
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CurVer") as key:
                    cur_ver, _ = winreg.QueryValue(key, "")
                    ver_num = cur_ver.split(".")[-1] if "." in cur_ver else cur_ver
                    _cached_renderer_id = f"word-{ver_num}.0"
                    return _cached_renderer_id
            except Exception:
                pass

        # LibreOffice version check
        soffice_bin = cls.find_libreoffice_binary()
        if soffice_bin:
            try:
                res = subprocess.run(
                    [soffice_bin, "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5
                )
                out = (res.stdout or res.stderr).strip()
                parts = out.split()
                for p in parts:
                    if p and p[0].isdigit() and "." in p:
                        subparts = p.split(".")[:3]
                        _cached_renderer_id = f"libreoffice-{'.'.join(subparts)}"
                        return _cached_renderer_id
                _cached_renderer_id = "libreoffice"
                return _cached_renderer_id
            except Exception:
                _cached_renderer_id = "libreoffice"
                return _cached_renderer_id

        _cached_renderer_id = "native-ast"
        return _cached_renderer_id

    @classmethod
    def find_libreoffice_binary(cls) -> Optional[str]:
        """Locates the soffice / libreoffice executable on the host system."""
        custom_path = getattr(config, "LIBREOFFICE_PATH", "") or os.getenv("LIBREOFFICE_PATH", "")
        if custom_path and os.path.isfile(custom_path):
            return custom_path

        # Standard PATH lookup
        for cmd in ["soffice", "libreoffice", "soffice.exe", "libreoffice.exe"]:
            resolved = shutil.which(cmd)
            if resolved:
                return resolved

        # Common Windows installation paths
        win_candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\LibreOffice\program\soffice.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"LibreOffice\program\soffice.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"LibreOffice\program\soffice.exe")
        ]
        for candidate in win_candidates:
            if candidate and os.path.isfile(candidate):
                return candidate

        # Common Linux / macOS paths
        nix_candidates = [
            "/usr/bin/soffice",
            "/usr/bin/libreoffice",
            "/usr/local/bin/soffice",
            "/usr/local/bin/libreoffice",
            "/opt/libreoffice/program/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        ]
        for candidate in nix_candidates:
            if os.path.isfile(candidate):
                return candidate

        return None

    @classmethod
    def detect_format(cls, file_path: str) -> str:
        """
        Determines file format using magic bytes first, falling back to file extension.
        Returns lowercase format extension (e.g. 'pdf', 'docx', 'pptx', 'doc', 'ppt').
        """
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
                
            if header.startswith(cls.MAGIC_PDF):
                return "pdf"
            elif header.startswith(cls.MAGIC_ZIP):
                if ext in ["docx", "pptx", "xlsx"]:
                    return ext
                return "docx"  # default zip-based office format
            elif header.startswith(cls.MAGIC_OLE):
                if ext in ["doc", "ppt", "xls"]:
                    return ext
                return "doc"
        except Exception as e:
            logger.warning(f"Could not read magic bytes from {file_path}: {e}")

        return ext if ext else "unknown"

    @classmethod
    def to_pdf(
        cls,
        input_path: str,
        out_dir: Optional[str] = None,
        allow_fallback: bool = False
    ) -> ConversionResult:
        """
        Converts the input file to PDF if necessary and permitted by feature flags.
        
        Returns:
            ConversionResult(pdf_path, original_path, format, was_converted, unit_source)
            
        Raises:
            UnsupportedFormatError: If the format is not allowed or multi-format is disabled.
            LibreOfficeNotFoundError: If conversion is required, soffice is missing, and allow_fallback=False.
            ConversionTimeoutError: If LibreOffice hangs beyond the configured timeout.
            ConversionExecutionError: If conversion fails or outputs an empty PDF.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found at: {input_path}")

        detected_format = cls.detect_format(input_path)
        multiformat_enabled = getattr(config, "MULTIFORMAT_ENABLED", False)
        allowed_formats = getattr(config, "MULTIFORMAT_FORMATS", ["docx", "pptx", "doc", "ppt"])

        # Native PDF pass-through (zero overhead, completely unmodified)
        if detected_format == "pdf":
            return ConversionResult(input_path, input_path, "pdf", False, "native-pdf")

        # If multi-format flag is disabled, reject non-PDFs cleanly
        if not multiformat_enabled:
            raise UnsupportedFormatError(
                f"Multi-format document support is disabled (MULTIFORMAT_ENABLED=false). "
                f"Only PDF files are currently supported."
            )

        # Check if format is in allowed formats list
        if detected_format not in allowed_formats:
            raise UnsupportedFormatError(
                f"Document format '{detected_format.upper()}' is not enabled for conversion. "
                f"Allowed formats: {', '.join([f.upper() for f in allowed_formats])}"
            )

        # If converter is explicitly disabled via RAG_DISABLE_CONVERTER
        if getattr(config, "RAG_DISABLE_CONVERTER", False):
            logger.info("RAG_DISABLE_CONVERTER is enabled; bypassing external conversion.")
            if allow_fallback:
                return ConversionResult(None, input_path, detected_format, False, "native-ast")
            raise ConversionExecutionError("External converter disabled by RAG_DISABLE_CONVERTER.")

        destination_dir = out_dir or os.path.dirname(input_path)
        os.makedirs(destination_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(input_path))[0]
        converted_pdf_path = os.path.join(destination_dir, f"{stem}.pdf")

        # Windows MS Word COM high-fidelity conversion (if available)
        if detected_format in ["docx", "doc"] and sys.platform == "win32":
            try:
                import win32com.client  # type: ignore
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                try:
                    abs_in = os.path.abspath(input_path)
                    abs_out = os.path.abspath(converted_pdf_path)
                    doc = word.Documents.Open(abs_in)
                    # wdFormatPDF = 17
                    doc.SaveAs(abs_out, FileFormat=17)
                    doc.Close()
                    if os.path.exists(abs_out) and os.path.getsize(abs_out) > 0:
                        logger.info(f"MS Word COM high-fidelity converted {input_path} -> {converted_pdf_path}")
                        return ConversionResult(converted_pdf_path, input_path, detected_format, True, cls.get_renderer_id())
                finally:
                    word.Quit()
            except Exception as e:
                logger.info(f"Native MS Word COM automation not available: {e}. Checking LibreOffice.")

        # Non-PDF format needs headless LibreOffice conversion
        soffice_bin = cls.find_libreoffice_binary()
        if not soffice_bin:
            if allow_fallback:
                logger.info(f"LibreOffice not found; falling back to native AST for {detected_format}.")
                return ConversionResult(None, input_path, detected_format, False, "native-ast")
            raise LibreOfficeNotFoundError(
                f"Cannot convert '{detected_format.upper()}' document: LibreOffice (soffice) "
                f"executable was not found on the host system. Please install LibreOffice or set LIBREOFFICE_PATH."
            )

        timeout_sec = getattr(config, "CONVERSION_TIMEOUT_SECONDS", 120)

        # Concurrency control via bounded semaphore
        sem = get_conversion_semaphore()
        acquired = sem.acquire(timeout=timeout_sec)
        if not acquired:
            raise ConversionTimeoutError(f"LibreOffice conversion queued longer than {timeout_sec}s waiting for semaphore.")

        profile_dir = tempfile.mkdtemp(prefix=f"lo_profile_{uuid.uuid4().hex[:8]}_")
        profile_uri = Path(profile_dir).as_uri()

        # Security hardening arguments: disable restoration, lock-checking, default UI, macros
        cmd = [
            soffice_bin,
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--invisible",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to", "pdf",
            "--outdir", destination_dir,
            input_path
        ]

        logger.info(f"Executing LibreOffice conversion: {' '.join(cmd)}")

        try:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags
            )
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_sec)
            except subprocess.TimeoutExpired as te:
                _kill_process_tree(proc)
                raise ConversionTimeoutError(
                    f"LibreOffice conversion timed out after {timeout_sec} seconds."
                ) from te

            if proc.returncode != 0:
                err_msg = stderr_bytes.decode("utf-8", errors="ignore").strip() or stdout_bytes.decode("utf-8", errors="ignore").strip()
                raise ConversionExecutionError(
                    f"LibreOffice conversion failed with exit code {proc.returncode}: {err_msg}"
                )

            # Determine expected converted PDF file path
            stem = os.path.splitext(os.path.basename(input_path))[0]
            converted_pdf_path = os.path.join(destination_dir, f"{stem}.pdf")

            if not os.path.exists(converted_pdf_path) or os.path.getsize(converted_pdf_path) == 0:
                raise ConversionExecutionError(
                    f"LibreOffice conversion reported success, but output PDF '{converted_pdf_path}' "
                    f"is missing or zero bytes."
                )

            renderer_id = cls.get_renderer_id()
            logger.info(f"Successfully converted {input_path} -> {converted_pdf_path} ({os.path.getsize(converted_pdf_path)} bytes) via {renderer_id}")
            return ConversionResult(converted_pdf_path, input_path, detected_format, True, renderer_id)

        finally:
            sem.release()
            # Clean up temporary profile directory
            try:
                if os.path.exists(profile_dir):
                    shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Could not remove temp profile dir {profile_dir}: {e}")

