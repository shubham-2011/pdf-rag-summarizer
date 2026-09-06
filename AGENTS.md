# AGENTS.md

Document Intelligence Platform — offline retrieval, cloud synthesis, page-grounded citations.

Ingests PDF/DOCX/PPTX/XLSX, extracts structured knowledge, generates roadmaps and executive summaries, answers questions over the corpus with citations.

Documentation map: `INDEX.md`. Read it before fetching other docs.

## The architectural boundary

The rule that shapes everything else. **Retrieval is local; synthesis is cloud. They never mix.**

```
LOCAL / OFFLINE                              CLOUD / LLM
PyMuPDF → chunking → Nomic embeddings   →    Query Understanding → Gemini
→ FAISS + BM25 → BGE reranker                → grounded answer + citations
no API keys, no network, CPU only            text-in, text-out only
```

Gemini-facing code **never imports FAISS, Chroma, BM25Retriever, or any vector store**. Ingestion code **never imports a cloud LLM client**. If a task seems to need both, you are about to break the boundary — stop and ask.

Enforced by `tests/test_e_regressions.py::test_e1_*`.

## Commands

```bash
uvicorn backend.main:app --reload           # dev server
cd frontend && npm run build                # must precede a mounted deploy

cd tests && python run_pipeline.py --fast   # deterministic tests, no tokens  ← default
cd tests && python run_pipeline.py          # full, including LLM judges
cd tests && python run_pipeline.py --wiring # which adapter methods are connected
cd tests && python selftest_mock.py         # prove the suite still catches bugs

cd audit && python make_fixtures.py         # generate known-truth documents
cd audit && python audit_formats.py         # cross-format extraction audit
```

Run `run_pipeline.py --fast` before calling any change done. It is free and fast.

## Layout

```
backend/
  main.py        FastAPI app, static mount
  config.py      model names, paths, chunking constants
  schemas.py     Pydantic models
  routers/       pdf_router.py, chat_router.py
  services/      see backend/services/AGENTS.md
frontend/        React 18 + Vite 5 — see frontend/AGENTS.md
tests/           see tests/AGENTS.md
audit/           cross-format extraction audit
docs/            reference docs, fetched on demand — see INDEX.md
knowledge/       original design docs and incident logs
```

## Hard rules

Each is a bug that shipped. Origins in `docs/INCIDENTS.md`.

1. **Never report "pages" for a non-PDF format.** DOCX has no page count — pagination is computed by the renderer and not stored. PPTX has slides, XLSX has sheets and rows. Read `unit_name` from the registry; never assume. [`docs/FORMAT_UNITS.md`]
2. **Never assert a document fact you cannot derive from the file.** `docProps/app.xml` `<Pages>` is a stale cache, commonly `1` or absent. An estimate stated without qualification is fabrication even when close.
3. **Never hardcode a page count, chunk count, or document length.** A hardcoded `15` fallback made every document report 15 pages. [Log 21]
4. **Every upload must call `MetadataService.register_document()`.** Unregistered documents have no identity, no unit count, no lifecycle state. [Log 21]
5. **DOCX extraction must cover every container.** `document.paragraphs` excludes tables, headers, footers, text boxes, and footnotes. On a test fixture, paragraph-only extraction lost 27 of 32 planted tokens, all in tables.
6. **Vite `base` stays `'./'`.** An absolute base 404s the JS bundle when FastAPI mounts the SPA at root — blank white screen, no error. [Log 09]
7. **`CHUNK_SIZE` stays ≥ 1000 with hierarchical delimiters.** Fixed 500-char splitting cut words mid-token and destroyed tables. [Log 17]
8. **Embedding prefixes are not optional.** `search_document: ` at index time, `search_query: ` at query time. Omitting or swapping them costs recall silently — nothing errors.
9. **New Pydantic response fields default to `Optional`.** A mandatory `snippet` while the service emitted `text` returned HTTP 500 on a normal question. [Migration log]
10. **Never delete or hand-edit `index_manifest.json`.** It exists to make model/dimension drift fail loudly. Rebuild the index instead.
11. **Do not answer META or GREETING queries through the retrieval path.** That is what `query_understanding_service.py` is for; bypassing it reintroduces the false-refusal bug.

## Conventions

- Python 3.11+, FastAPI, Pydantic v2. Async routes; services may be sync.
- Every chunk carries `page_label`, `section_heading`, `block_type`. Citations depend on `page_label` — never drop it.
- Intent taxonomy is exactly `GREETING`, `META`, `GLOBAL`, `LOCAL`, `TABULAR`. Adding one means updating the classifier, its dataset, and the confusion-matrix gate together.
- Lifecycle: `UPLOADED → PARSING → CHUNKING → INDEXED → READY`. No skipping. Not `READY` means not queryable.
- Local models: `nomic-ai/nomic-embed-text-v1.5` (768 dims), `BAAI/bge-reranker-base`. Changing either needs an index rebuild and a manifest bump.
- **There is no validation or regeneration stage.** The synthesis prompt is the only thing keeping answers grounded. Edits there have no safety net.

## Before you finish

- Ran `python run_pipeline.py --fast` and it is green.
- Touched ingestion or a format handler? Run the format audit too.
- Fixed a bug? Add a regression test — that is how these rules got written.
- Changed retrieval, chunking, or the classifier? Say so; those invalidate cached eval numbers.
