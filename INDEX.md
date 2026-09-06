# INDEX.md

Documentation map. Read this file first, then fetch only what the task needs — blanket-loading everything wastes context on a task that touches one service.

## Always loaded

| File | Contents |
|---|---|
| `AGENTS.md` | Boundary rule, commands, layout, 10 hard rules. ~90 lines, loads every session. |
| `CLAUDE.md` | One-line `@AGENTS.md` import. |

## Loaded when working in that directory

| File | Read before touching |
|---|---|
| `backend/services/AGENTS.md` | Any service. Ownership map + the trap in each. |
| `tests/AGENTS.md` | Adding or changing tests. |
| `frontend/AGENTS.md` | Vite config, API client, build output. |

## Fetch on demand

| File | Read when |
|---|---|
| `docs/FORMAT_UNITS.md` | Touching ingestion, page counts, or any non-PDF format. **Read before answering "how many pages"** — the answer is format-dependent and currently wrong for DOCX. |
| `docs/UNIFIED_CROSS_FORMAT_FIDELITY_ROADMAP.md` | Complete architecture for cross-format fidelity, dual-branch ingestion, and renderer drift elimination. |
| `docs/INCIDENTS.md` | Before a large refactor, or when a hard rule looks wrong. Every rule's origin bug. |
| `docs/TESTING.md` | Test architecture, stages, gates, metric definitions. |
| `docs/RAG_PROMPTS.md` | Changing synthesis, intent classification, or query rewriting prompts. |
| `docs/SUMMARY_PROMPTS.md` | Prompts for Summary & Roadmap path (summarizer_service.py) with plain language rules. |
| `docs/AUDIT_PROMPTS.md` | Auditing extraction quality or building eval data. |


## Task routing

| Task | Read |
|---|---|
| "Why does page count say N?" | `docs/FORMAT_UNITS.md` first — for DOCX the honest answer is that no page count exists |
| "Retrieval is returning bad results" | `backend/services/AGENTS.md`, then `/diagnose` |
| "Add support for a new format" | `docs/FORMAT_UNITS.md`, `backend/services/AGENTS.md` |
| "Fix a bug" | `docs/INCIDENTS.md` to check it is not a known one, then `/add-regression` |
| "Change a prompt" | `docs/RAG_PROMPTS.md` — note there is no validation stage downstream |
| "Is this change safe to ship?" | `/verify`, then `tests/AGENTS.md` for what the gates mean |

## Facts an agent gets wrong without reading

1. **DOCX has no page count.** Any number reported as "pages" for a `.docx` is fabricated. `docs/FORMAT_UNITS.md`
2. **There is no validation or regeneration stage.** The synthesis prompt is the only grounding defense. `docs/RAG_PROMPTS.md`
3. **Embedding prefixes are asymmetric and mandatory.** Omitting them costs recall with no error. `backend/services/AGENTS.md`
4. **The index manifest is a tripwire, not config.** Never edit it to match changed settings. `AGENTS.md` rule 7
5. **`document.paragraphs` is not the whole DOCX.** Tables, headers, footers, and text boxes live elsewhere. `docs/FORMAT_UNITS.md`
