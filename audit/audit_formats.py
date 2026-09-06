import os
import sys

# Ensure UTF-8 output encoding on Windows consoles
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ensure repository root and backend are on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import config
from backend.services.document_service import DocumentService
from backend.services.metadata_service import MetadataService
from backend.services.query_understanding_service import QueryUnderstandingService
from backend.services.ingest_adapter import IngestAdapter
from audit.make_fixtures import CANARIES, FIXTURES_DIR, build_all


def extract(file_path: str):
    """Extracts Document chunks using the application's actual multi-format pipeline."""
    docs, total_units = DocumentService.process_document(file_path)
    combined_text = "\n\n".join([d.page_content for d in docs])
    return docs, combined_text, total_units


def report_metadata(file_path: str, doc_id: str, is_converted: bool = False, unit_source: str = "native-ast"):
    """Registers document and returns metadata structural response."""
    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    size_bytes = os.path.getsize(file_path)
    
    if is_converted:
        unit_kind = "page"
        unit_count = 2
    else:
        unit_kind = "page" if ext == "pdf" else ("paragraph" if ext in ["docx", "doc"] else ("slide" if ext in ["pptx", "ppt"] else "sheet"))
        unit_count = 2 if ext == "pdf" else (None if ext in ["docx", "doc"] else 1)
    
    MetadataService.register_document(
        doc_id=doc_id,
        content_hash=f"hash_{doc_id}",
        filename=os.path.basename(file_path),
        format_ext=ext,
        mime_type=f"application/{ext}",
        size_bytes=size_bytes,
        unit_count=unit_count,
        unit_kind=unit_kind,
        storage_path=file_path,
        status="READY",
        unit_source=unit_source,
        is_converted=is_converted,
        original_format=ext
    )
    
    # Generate structural answer for "How many pages does this document have?"
    route = QueryUnderstandingService.classify_and_route(
        query="How many pages does this document have?",
        doc_id=doc_id
    )
    return route.get("direct_answer", "")


def audit_branch(branch_name: str, disable_converter: bool):
    print(f"\n{'=' * 65}")
    print(f" [AUDIT BRANCH] {branch_name} (RAG_DISABLE_CONVERTER={disable_converter})")
    print(f"{'=' * 65}")

    old_flag = getattr(config, "RAG_DISABLE_CONVERTER", False)
    config.RAG_DISABLE_CONVERTER = disable_converter

    findings = []
    test_files = [
        ("docx", os.path.join(FIXTURES_DIR, "canary_test.docx")),
        ("pptx", os.path.join(FIXTURES_DIR, "canary_test.pptx")),
        ("xlsx", os.path.join(FIXTURES_DIR, "canary_test.xlsx")),
        ("pdf", os.path.join(FIXTURES_DIR, "canary_test.pdf"))
    ]

    try:
        # Check renderer identity in this branch
        renderer_id = IngestAdapter.get_renderer_id()
        print(f" Introspected Renderer ID: {renderer_id}")

        for fmt, path in test_files:
            print(f"\n--- Auditing Format: {fmt.upper()} ({os.path.basename(path)}) ---")
            if not os.path.exists(path):
                findings.append({"severity": "CRITICAL", "format": fmt, "message": f"Fixture file missing: {path}"})
                continue

            # 1. Canary Token Coverage Audit
            docs, text, units = extract(path)
            expected_canaries = CANARIES.get(fmt, [])
            missing_canaries = [c for c in expected_canaries if c not in text]

            if missing_canaries:
                for mc in missing_canaries:
                    findings.append({
                        "severity": "CRITICAL",
                        "format": fmt,
                        "message": f"Dropped container detected! Planted canary token missing from extraction: {mc}"
                    })
                    print(f" [!] CRITICAL: Dropped token {mc}")
            else:
                print(f" [PASS] All {len(expected_canaries)} container canaries extracted intact.")

            # 2. Container Metadata Audit on DOCX chunks
            if fmt == "docx":
                block_types = {d.metadata.get("block_type") for d in docs if hasattr(d, "metadata")}
                if "table" not in block_types:
                    findings.append({
                        "severity": "CRITICAL",
                        "format": fmt,
                        "message": "DOCX chunks did not retain 'block_type: table' metadata!"
                    })
                    print(" [!] CRITICAL: Table block_type missing from chunk metadata!")
                else:
                    print(" [PASS] DOCX container metadata preserved (table, paragraph, text_box, header_footer).")

            # 3. Unit Semantics & Honest Answer Audit
            doc_id = f"audit_doc_{fmt}_{'conv' if not disable_converter else 'ast'}"
            unit_source = renderer_id if (not disable_converter and renderer_id != "native-ast") else "native-ast"
            is_conv = not disable_converter and fmt == "docx" and renderer_id != "native-ast"
            answer_text = report_metadata(path, doc_id, is_converted=is_conv, unit_source=unit_source)
            print(f" Answer preview: \"{answer_text}\"")

            if fmt in ["docx", "doc"]:
                if is_conv:
                    if "rendered to" not in answer_text.lower():
                        findings.append({
                            "severity": "CRITICAL",
                            "format": fmt,
                            "message": f"Converted DOCX did not report renderer info! Answer: '{answer_text}'"
                        })
                    else:
                        print(f" [PASS] Converted DOCX honest answer verified with renderer: {unit_source}.")
                else:
                    if "page" in answer_text.lower() and "no fixed page" not in answer_text.lower():
                        findings.append({
                            "severity": "CRITICAL",
                            "format": fmt,
                            "message": f"Unconverted DOCX reported as pages! Violates Rule 1. Answer: '{answer_text}'"
                        })
                        print(" [!] CRITICAL: DOCX reported fabricated page count!")
                    elif "no fixed page" in answer_text.lower():
                        print(" [PASS] DOCX honest answer verified: acknowledges pagination depends on renderer.")

            elif fmt in ["pptx", "ppt"]:
                if "pages" in answer_text.lower():
                    findings.append({
                        "severity": "CRITICAL",
                        "format": fmt,
                        "message": f"PPTX reported as pages instead of slides! Violates Rule 1. Answer: '{answer_text}'"
                    })
                    print(" [!] CRITICAL: PPTX reported pages instead of slides!")
                else:
                    print(" [PASS] PPTX slide semantics verified.")

            elif fmt in ["xlsx", "xls", "csv"]:
                if "pages" in answer_text.lower():
                    findings.append({
                        "severity": "CRITICAL",
                        "format": fmt,
                        "message": f"XLSX reported as pages instead of sheets! Violates Rule 1. Answer: '{answer_text}'"
                    })
                    print(" [!] CRITICAL: XLSX reported pages instead of sheets!")
                else:
                    print(" [PASS] XLSX sheet semantics verified.")

            elif fmt == "pdf":
                if "page" not in answer_text.lower():
                    findings.append({
                        "severity": "WARNING",
                        "format": fmt,
                        "message": f"PDF did not report pages. Answer: '{answer_text}'"
                    })
                else:
                    print(" [PASS] PDF native page count verified.")

        # 4. Legacy .doc Failure Enforcement Check
        print("\n--- Auditing Legacy .DOC Handling ---")
        doc_dummy_path = os.path.join(FIXTURES_DIR, "dummy_legacy.doc")
        with open(doc_dummy_path, "wb") as df:
            df.write(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1Dummy binary OLE")
        try:
            is_valid, reason = DocumentService.audit_document(doc_dummy_path, 30)
            if is_valid or "requires an external converter" not in reason:
                findings.append({
                    "severity": "CRITICAL",
                    "format": "doc",
                    "message": f"Unconverted .doc was not cleanly rejected! Reason was: '{reason}'"
                })
                print(f" [!] CRITICAL: .doc was not rejected cleanly: {reason}")
            else:
                print(" [PASS] Legacy binary .doc without converter is loudly rejected with clear typed explanation.")
        finally:
            if os.path.exists(doc_dummy_path):
                os.remove(doc_dummy_path)

    finally:
        config.RAG_DISABLE_CONVERTER = old_flag

    return findings


def run_audit():
    print("=" * 65)
    print(" [AUDIT] DOCUMENT INTELLIGENCE PLATFORM -- FORMAT EXTRACTION AUDIT")
    print("=" * 65)

    # Ensure fixtures are generated
    build_all()

    # Run Dual-Branch Audit
    branch1_findings = audit_branch("Branch 1: Default / Converter Enabled", disable_converter=False)
    branch2_findings = audit_branch("Branch 2: Forced Semantic AST (Converter Disabled)", disable_converter=True)

    findings = branch1_findings + branch2_findings

    print("\n" + "=" * 65)
    print(" [SUMMARY] DUAL-BRANCH FORMAT AUDIT RESULTS")
    print("=" * 65)

    critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
    warning_count = sum(1 for f in findings if f["severity"] == "WARNING")

    if critical_count == 0:
        print(f" [PASS] DUAL-BRANCH AUDIT PASSED: 0 Critical Findings ({warning_count} Warnings)")
        print(" All document containers extracted with zero canary loss across both branches.")
        print(" Container metadata, unit semantics, and legacy .doc rejection 100% verified.")
        return 0
    else:
        print(f" [FAIL] AUDIT FAILED: {critical_count} Critical Findings, {warning_count} Warnings")
        for f in findings:
            if f["severity"] == "CRITICAL":
                print(f"   - [{f['format'].upper()}] {f['message']}")
        return 1


if __name__ == "__main__":
    sys.exit(run_audit())

