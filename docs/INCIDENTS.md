# INCIDENTS.md

Every hard rule in `AGENTS.md` traces to one of these. Read the relevant entry before arguing a rule is unnecessary — each looked unnecessary right up until it shipped.

Format: symptom → root cause → fix → the rule it produced → the test that guards it.

---

## Log 09 — Blank white screen

**Symptom.** Client loaded blank white. Server logs showed HTTP 404 for `/pdf-rag-summarizer/assets/index-*.js`. No console error worth noticing.

**Root cause.** Vite `base` was `/pdf-rag-summarizer/` for GitHub Pages. It broke when FastAPI mounted the SPA at root.

**Fix.** `base: './'` — universal relative path.

**Rule 6.** Vite `base` stays `'./'`.
**Guarded by** `test_r1_vite_base_is_relative`, `test_r1_built_assets_use_relative_paths`.

---

## Logs 11 & 16 — Tunnel 503s and network errors

**Symptom.** Bad Gateway / 503 on public tunnel URLs. Looked like backend failure.

**Root cause.** Localtunnel drops sockets when background tasks restart, and its anti-abuse HTML interstitial intercepted CORS preflight requests.

**Fix.** `bypass-tunnel-reminder: true` header in the Axios client; documented migration to Render / Hugging Face.

**Guarded by** `test_r2_tunnel_bypass_header_present`.

---

## Log 14 — Access drops when the laptop sleeps

**Root cause.** Serving from a developer machine with no supervision.

**Fix.** PM2 locally, containerized cloud deploy via Dockerfile and `render.yaml`.

**Guarded by** `test_r3_health_endpoint_and_restart_policy`.

---

## Log 17 — Chunking destroyed content

**Symptom.** Retrieval quality poor. Chunks contained fragments like `SEO-optim` / `ized Angular`. Tables unreadable.

**Root cause.** Fixed 500-character splitting with no delimiter hierarchy. Cut mid-word, separated headings from bodies, split tables across chunks.

**Fix.** Hierarchical chunking in `pdf_service.py` with prioritized delimiters, size raised to 1000, `section_heading` metadata added.

**Rule 7.** `CHUNK_SIZE` stays ≥ 1000 with hierarchical delimiters.
**Guarded by** `test_r4_chunking_config_not_reverted`, `test_a2_no_mid_word_splits`.

**Note on the test.** Checking for a trailing hyphen alone does not catch this — a fixed-size splitter cuts without one most of the time. The test compares consecutive chunk boundaries: text ending on a word character followed by text starting lowercase.

---

## Log 18 — Pronoun follow-ups failed

**Symptom.** "What technologies were used in it?" returned nothing useful.

**Root cause.** Follow-ups went to vector search verbatim. "it" carries no semantic signal.

**Fix.** `contextualize_question()` with conversation memory in `rag_service.py`.

**Guarded by** `test_c4_resolves_pronoun`, `test_c4_three_turn_chain`.

**Watch for.** The opposite failure — a rewrite that invents a constraint absent from the question silently narrows retrieval, and nothing downstream can tell the question was changed.

---

## Log 21 — Defect 3, page count discrepancy

**The most instructive failure. Read this one.**

**Symptom.** "How many pages does this document have?" always returned "This document contains exactly 15 pages" — for 1-page drawings and 2-page resumes alike.

**Root cause — three independent causes:**
1. `upload_pdf` never called `MetadataService.register_document()`.
2. `index_manifest.json` recorded `chunk_count` but not `unit_count`.
3. `query_understanding_service.py` had a hardcoded `15` fallback.

**Fix.** All three. Fixing one and shipping is how this class of bug returns.

**Rules 3 and 4.** No hardcoded document facts; every upload registers.
**Guarded by** `test_r6_no_hardcoded_page_count`, `test_r6_upload_registers_document_in_source`, `test_r6_manifest_has_unit_count`, `test_r6_page_count_accurate`.

**Why the 15-page fixture is kept.** It is the one value where a reintroduced hardcode still returns the correct answer. Alone it passes silently; alongside 1-, 2-, and 199-page fixtures the regression fails loudly.

---

## Migration — HTTP 500 on `/api/chat/query`

**Symptom.** "What is this pdf for?" returned HTTP 500.

**Root cause.** `snippet` was mandatory in `schemas.py` while `rag_service` emitted `text`.

**Fix.** Both fields optional, both populated. Added missing deps: `python-multipart`, `rank_bm25`, `pymupdf`.

**Rule 9.** New response fields default to `Optional`.
**Guarded by** `test_r7_source_citation_fields_optional`, `test_r7_identity_question_returns_200`.

---

## Open — Format unit semantics

**Status: active defect.** Not yet in `knowledge/`.

**Symptom.** A `.docx` reported as "26 Pages • 33 Vector Chunks (Audit Passed)", answered "This document contains exactly 26 pages."

**Three defects in one card:**

1. **DOCX has no page count.** Pagination is computed by the renderer, not stored. `docProps/app.xml` `<Pages>` is a stale cache — measured at `1` on a freshly generated 22,000-character document.
2. **The arithmetic fails.** 33 chunks ÷ 26 pages = 1.27 per page. At `CHUNK_SIZE=1000` that implies ~1,270 characters per claimed page against a normal 2,000–3,500. Either the count is inflated ~2.5× or half the content was dropped.
3. **"Audit Passed" measures the wrong thing.** `validation_service` checks size, encryption, page limit, minimum characters — that the file was *ingestible*, not that ingestion was *correct*.

**Probable extraction cause.** `document.paragraphs` excludes tables, headers, footers, and text boxes. On the fixture, paragraph-only extraction lost 27 of 32 planted tokens, all in tables. For a report that is mostly metric tables, that is most of the substance.

**Note the lineage.** "This document contains exactly N pages" is the same template string as Defect 3. The hardcoded `15` went away, but the phrasing that asserts false precision survived — a fix that removed the symptom and left the shape.

**Rules 1, 2, 5.** Details in `docs/FORMAT_UNITS.md`.
**Guarded by** `audit/audit_formats.py` — not yet in CI. Gate it.

---

## Patterns worth carrying

**Bugs have more than one cause.** Defect 3 had three. Fix all of them or it comes back through the one you left.

**A fix that removes the symptom can leave the shape.** The `15` went away; the sentence template that asserts fake precision did not, and it caused the next bug.

**"Audit passed" is a claim about what was checked.** Name what a check does not cover.

**Silent degradation is the dangerous kind.** Wrong embedding prefixes, dropped table content, and inflated page counts all produce plausible output and no error. Every one of them needed a test built specifically to see it.
