# Unified Cross-Format Fidelity & Discrepancy Elimination Architecture

## 1. Executive Summary

In document ingestion systems supporting PDF, Word (`.docx`, `.doc`), PowerPoint (`.pptx`), and Excel (`.xlsx`), significant discrepancies can emerge across rendering engines, parsers, and environments:
- **Layout Divergence**: The identical `.docx` file renders to 15 pages in Microsoft Word, 14–16 pages in LibreOffice, and 26 artificial pages in naive rasterizers.
- **Tabular Data Token Loss**: Paragraph-only parsers silently drop tables, textboxes, headers, and footers. On test fixtures, this resulted in losing 27 of 32 canary tokens: representing **all table content, ~4% of characters on a prose-heavy fixture, and approaching 100% of tabular facts**.
- **Citation Mismatch**: Citations citing `Page X` clash with native documents that have no page boundaries.
- **Security & Concurrency**: Uncontrolled office converter processes introduce RCE risks via malicious macros and resource exhaustion / lock deadlocks.

This architecture establishes a **tiered, dual-branch ingestion system with honest provenance attribution**:
1. **Option B (High-Fidelity Rendered PDF)**: When a canonical headless converter (LibreOffice or MS Word COM) is available, documents are converted with strict sandboxing into vector PDFs, providing exact visual page grounding.
2. **Option A (Deep Semantic AST Extraction)**: When external converters are unavailable or bypassed via `RAG_DISABLE_CONVERTER=1`, documents are parsed natively across all containers (`paragraphs`, `tables`, `header_footer`, `text_box`). Citations and structural metadata honestly acknowledge the absence of renderer pagination.
3. **Legacy `.doc` Policy**: Binary OLE `.doc` cannot be parsed via `python-docx` and has no Option A; it fails loudly with HTTP 400 when no converter is available.

---

## 2. Ingestion Pipeline & Dual Branching

```
                             [Uploaded Document]
                                      │
                         Format Detection (Magic Bytes)
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            │                                                   │
        [Raw PDF]                                    [Non-PDF: DOCX / PPTX / XLSX / DOC]
            │                                                   │
     Pre-Embedding Audit                              Converter Available & Enabled?
            │                                         (RAG_DISABLE_CONVERTER == 0)
            │                                                   │
            │                                  ┌────────────────┴────────────────┐
            │                                  │ YES                             │ NO
            │                                  ▼                                 ▼
            │                        [Sandboxed Conversion]             Is Legacy .DOC?
            │                      (LibreOffice / MS Word COM)                   │
            │                                  │                        ┌────────┴────────┐
            │                                  ▼                        │ YES             │ NO
            │                        [Rendered PDF Stream]              │                 ▼
            │                                  │                  Loud HTTP 400   [Deep AST Parsing]
            │                                  ▼                  (No Option A)   - Paragraphs
            └──────────────────────────► [PDFService]                             - Tables
                                     - PyMuPDF text & rects                       - Text Boxes
                                     - Layout & Citations                         - Headers / Footers
                                     - Page-grounded citations                         │
                                               │                                       ▼
                                               └───────────────────────────────► [Chunking & Indexing]
                                                                                  - Preserves block_type
                                                                                  - Records unit_source
```

---

## 3. Sandboxing & Process Security

Headless converter execution adheres to strict operational constraints:
- **Macro Execution Disabled**: Prevents malicious macros embedded in incoming Office documents from running.
- **Headless Invisibility**: Flags `--headless --norestore --nolockcheck --nodefault --invisible` ensure no UI prompts or lock dialogs block execution.
- **Isolated User Profiles**: Each conversion generates an isolated, ephemeral user profile via `-env:UserInstallation=file://{temp_dir}`, purged on exit.
- **Bounded Concurrency**: Ingestion conversion is governed by a thread-safe `BoundedSemaphore` (`CONVERSION_SEMAPHORE_LIMIT=2`).
- **Process-Tree Termination**: On timeout expiry, the entire process hierarchy is terminated (`taskkill /F /T /PID` on Windows, `os.killpg` on POSIX) to guarantee zero orphan zombie processes.

---

## 4. Metadata Provenance & Answer Templates

The platform records provenance directly in the SQLite `documents` registry and the vector store `index_manifest.json`:
- `unit_source`: Identifies the rendering engine (`libreoffice-7.6.4`, `word-16.0`, `native-ast`, `native-pdf`).
- `is_converted`: Boolean flag indicating whether the document was rendered from a non-PDF format.
- `original_format`: Preserves original file extension (`docx`, `pptx`, `xlsx`, `doc`, `pdf`).

### Three Honest Structural Answer Templates

When users inquire about document page counts (`"How many pages does this document have?"`), the query understanding service provides one of three deterministic answers:

1. **Native PDF**:
   > *"This document contains exactly {unit_count} pages."*
2. **Unconverted Native DOCX** (`is_converted=0`):
   > *"This .docx has {para_count} paragraphs and {table_count} tables. Word documents have no fixed page count — pagination depends on the renderer, so I can't give a page number."*
3. **High-Fidelity Converted DOCX** (`is_converted=1`):
   > *"This document was rendered to {unit_count} pages from the original Word layout (renderer: {unit_source})."*

---

## 5. Verification & Continuous Integration

Dual-branch validation is enforced via `audit/audit_formats.py` and `tests/run_pipeline.py --fast`:
1. **Branch 1 (Converter Path)**: Verifies conversion, canary retention, and rendered attribution when a renderer is present.
2. **Branch 2 (Forced AST Path)**: Verifies `RAG_DISABLE_CONVERTER=1`, proving zero token loss across all container types (`table`, `text_box`, `header_footer`) and verifying that legacy `.doc` fails loudly.
3. **Tripwire Gate**: Manifest validation guards against cross-renderer layout drift.
