# FORMAT_UNITS.md

**Read this before writing any code that reports a document's size, or answers "how many pages".** The answer is format-dependent, and reporting "pages" universally is the root of an active defect.

## Unit semantics

| Format | Real unit | Never report | Why |
|---|---|---|---|
| PDF | **pages** | — | The only format with a genuine, stable page count |
| DOCX | **paragraphs**, words, sections | pages | No pagination without a renderer |
| PPTX | **slides** | pages | Slides are sparse; notes are a separate block |
| XLSX | **sheets**, rows | pages | Headers must stay attached to their rows |

Store `unit_name` alongside `unit_count` in the registry and manifest, set by the format handler at ingestion. The answer template reads both. This kills the defect class rather than patching one format and waiting for the next to surface it.

## Why DOCX has no page count

Pagination is computed at layout time and depends on fonts, margins, printer metrics, and the Word version. It is not stored in the file. python-docx cannot compute it.

`docProps/app.xml` `<Pages>` is a **stale cache** written only when Word itself last saved. Measured on a freshly generated 22,000-character, 60-paragraph document:

```
Pages        1        ← for a document that renders to roughly 15 pages
Words        0
Paragraphs   0
Characters   0
```

Any number sourced from there is not a fact about the file.

### The honest answer

> This .docx has 60 paragraphs and 4 tables. Word documents have no fixed page count — pagination depends on the renderer, so I can't give a page number.

That passes the audit. `"This document contains exactly 26 pages"` does not: wrong unit, fabricated number, and false precision from the word "exactly".

If a page count is genuinely required, convert to PDF first and count that — and label it as the converted count, not the document's.

## DOCX containers

Content lives in several places. `document.paragraphs` is one of them.

| Container | In `.paragraphs`? | Handling |
|---|---|---|
| Body paragraphs | yes | normal chunks |
| **Table cells** | **no** | `doc.tables`, `block_type="table"`, keep rows together |
| **Headers / footers** | **no** | per section, `block_type="header_footer"`, exclude from body |
| **Text boxes, shapes** | **no** | walk the XML; commonly holds callouts and captions |
| **Footnotes / endnotes** | **no** | separate part; keep the reference link |
| List items | yes | keep grouped, do not split mid-list |

On the generated fixture, paragraph-only extraction lost **27 of 32 planted tokens, all in tables**. To size the impact accurately: this represents **all table content, ~4% of characters on a prose-heavy fixture, approaching 100% of tabular facts**. Tables are where quantitative facts, financial figures, and model benchmarks live — losing them destroys retrieval recall on tabular facts while leaving prose largely intact.

## Renderer Divergence & Layout Drift

The same `.docx` document routinely renders to different page counts depending on the engine: e.g. **15 pages in Microsoft Word** vs **14 or 16 pages in LibreOffice**, caused by differing font substitution, hyphenation dictionaries, and table cell padding algorithms.

To eliminate phantom layout drift:
1. **Record `unit_source`**: Persist `unit_source` (e.g. `libreoffice-7.6.4`, `word-16.0`, or `native-ast`) in both the SQLite `documents` registry and the vector store `index_manifest.json`.
2. **Canonical Renderer for CI**: In CI containers, headless LibreOffice is configured as the canonical renderer (`CANONICAL_RENDERER=libreoffice`).
3. **Tripwire against Model/Dimension & Renderer Drift**: If an index built with Word metrics is loaded under a different renderer, `unit_source` serves as a provenance tripwire.

## Conversion Security & Sandboxing

Headless office converters execute untrusted user uploads. The conversion pipeline enforces:
- **Macro Hard-Disabling**: Macro execution is restricted and disabled.
- **Strict Sandboxing Arguments**: `soffice` is invoked with `--headless --norestore --nolockcheck --nodefault --invisible`.
- **Isolated User Profiles**: Each conversion generates a unique temporary user profile (`-env:UserInstallation=file://{temp_dir}`), cleaned up immediately on exit to prevent profile-lock deadlocks.
- **Bounded Concurrency & Process-Tree Cleanup**: Ingestion is throttled via `CONVERSION_SEMAPHORE_LIMIT` (default: 2), and timeout expiration invokes process-tree termination (`taskkill /F /T /PID` on Windows, `killpg` on POSIX) to prevent zombie processes.


**PDF** — multi-column pages interleave into nonsense with no error. Figure captions detach from their figures. Scanned PDFs yield no text and deserve an OCR-specific message, not "insufficient text".

**DOCX** — the container problem above. Also: headers repeated into every body chunk inflate them with noise; tracked changes can surface as content.

**PPTX** — slides are short, so naive chunking emits stubs too small to retrieve on. Speaker notes must be captured but tagged `speaker_notes`; merging them into slide text corrupts citations. Decide whether `page_label` means slide number, and be consistent.

**XLSX** — flattening sheets separates column headers from data, making every row chunk uninterpretable. Emit `header: value` pairs per row. Formula cells have no cached value until Excel opens the file — openpyxl returns `=SUM(...)`. Sheets after the first are commonly dropped entirely.

## Diagnosing a suspect count

Characters per claimed unit is the fastest check.

```
chars_per_unit = extracted_chars / claimed_units
```

| Format | Plausible range |
|---|---|
| PDF | 700–6,000 per page |
| PPTX | 80–1,500 per slide |

Below the floor means either extraction is dropping content **or** the unit count is inflated. From outside those are indistinguishable — which is why the audit plants canary tokens. Missing canaries mean lost content; intact canaries with low density mean an inflated count.

Worked example from the live UI: 33 chunks over 26 claimed pages, `CHUNK_SIZE=1000`, implies ~1,270 characters per page against a normal 2,000–3,500. Roughly half the expected content, or a count inflated ~2.5×.

## Auditing

```bash
cd audit
python make_fixtures.py     # documents with ground truth known by construction
python audit_formats.py     # run through the app, compare
```

Fixtures plant canary tokens in every container, so any token that goes in and does not come out is a loss with a known cause — no judgement call needed.

Verified in both directions: a correct implementation produces **0 findings**, a naive one produces **6 critical**. Gate CI on zero critical.

Wire it by editing `extract()` and `report_metadata()` at the top of `audit_formats.py`. Include `answer_text` — the unit word in the user-facing sentence is half of what is being audited.

## Adding a format

1. Decide the real unit. If the format has no page concept, say so in the answer rather than estimating.
2. Enumerate its containers and extract all of them, tagging auxiliary ones with `block_type`.
3. Add a fixture builder in `make_fixtures.py` with canaries in every container.
4. Add the unit to `VALID_UNITS` and a plausible `CHARS_PER_UNIT` range in `audit_formats.py`.
5. Run the audit. Zero critical findings before merge.
