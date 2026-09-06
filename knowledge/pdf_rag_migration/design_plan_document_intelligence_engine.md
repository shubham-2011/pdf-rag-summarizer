# Design Plan — Document Intelligence Engine

**Project**: `pdf-rag-summarizer` → multi-format document intelligence platform  
**Date**: September 6, 2026  
**Status**: Design proposal for review  
**Scope**: Architecture and decisions. Implementation detail deliberately excluded.  

---

## 1. Problem statement

The system retrieves well and answers badly.

Five successive retrieval upgrades — persistent storage, three embedding models, hybrid keyword search, cross-encoder reranking — produced no movement on the primary user-facing complaint: the assistant cannot say what a document is about. Every observed failure showed correct chunks reaching a synthesis step that then refused or returned a fragment.

Three secondary defects share a root: the system was designed around a single format with a single citation unit, and every abstraction downstream inherited that assumption.

This plan addresses the synthesis gap, generalizes the document model, and closes the verification gap that allowed all of it to ship green.

---

## 2. Design principles

These are the tie-breakers for every decision below.

| Principle | Meaning |
|---|---|
| **Fail loudly at boundaries** | A missing page number is a bug, not a value to default. Validation exists to surface producer errors, not to absorb them. |
| **One question class, one strategy** | Different questions need structurally different answering paths. Forcing all through one path guarantees a failing category. |
| **Correctness over liveness in testing** | HTTP 200 is not an answer. Health checks and quality checks are separate instruments and both are required. |
| **Abstract before you multiply** | Generalize the document model while there is one format, not four. |
| **Refusal and fabrication are symmetric failures** | An unwarranted "not found" is as defective as a hallucination, and must be measured with equal weight. |

The last principle is the correction most specific to this system. Current design treats refusal as the safe default, which is why the primary feature fails safe into uselessness.

---

## 3. Root cause

**The synthesizer is extractive. The failing questions are not extractive.**

Extraction selects spans that already exist in retrieved text. It cannot produce a statement absent from every chunk.

Questions divide into two classes with incompatible requirements:

| | Local | Global |
|---|---|---|
| Example | "What is the transformer rating?" | "What is this document about?" |
| Answer location | One chunk | No chunk — emerges from the whole |
| Correct strategy | Retrieve top-k, extract, cite | Traverse all content, reduce, synthesize |
| Retrieval quality matters? | Decisively | Barely |

Global questions currently take the local path. The extractive synthesizer does the only two things available to it: return nothing, or return the highest-scoring existing sentence. Both observed failures are these two behaviors. **The component is correct; the routing is not.**

This also explains the five null-result upgrades. Improving retrieval improves the local path. The complaint was always about the global path.

The capability to answer global questions already exists — the map-reduce chain serving the summarize endpoint is verified working. It is simply unreachable from chat.

---

## 4. Target architecture

```
                        ┌─────────────────────────┐
                        │      Ingestion          │
                        │  format parsers → IR    │
                        └───────────┬─────────────┘
                                    │  Blocks + Locators
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
      ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
      │  Chunk index │     │ Doc synopsis │     │ Tabular store│
      │ FAISS + BM25 │     │  (cached)    │     │  dataframes  │
      └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                        ┌─────────┴───────────┐
                        │    Query Router     │
                        └─────────┬───────────┘
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        LOCAL path          GLOBAL path         TABULAR path
     retrieve → rerank    read synopsis      generate query →
      → extract → cite    → synthesize       execute → report
              └───────────────────┼───────────────────┘
                                  ▼
                        ┌─────────────────────┐
                        │  Citation assembly  │
                        └─────────────────────┘
```

Four changes from today: a normalized intermediate representation at ingest, a cached document synopsis, a query router, and a separate path for tabular data.

---

## 5. Component design

### 5.1 Query router

Classifies each incoming question and dispatches to one of three paths.

**Classes**: LOCAL (specific fact), GLOBAL (document-level characterization or summary), TABULAR (aggregation over structured data).

**Approach**: LLM classification. Rules were considered and rejected — keyword heuristics fail on the exact phrasings observed in production, where an ungrammatical global question carried no reliable lexical signal.

**Failure mode**: misclassification. LOCAL misread as GLOBAL wastes tokens but still answers. GLOBAL misread as LOCAL reproduces today's bug. **Bias the classifier toward GLOBAL** — the asymmetry favors it, since the global path degrades gracefully on specific questions while the local path fails hard on broad ones.

**Design note**: this is where the reported bug is fixed. It is the highest-value component in the plan and among the cheapest.

### 5.2 Document synopsis

A document-level summary computed once at ingest and cached alongside the index.

**Rationale**: global questions are answered from this, not from retrieval. Computing it once at upload converts a repeated expensive map-reduce into a one-time cost, and makes the global path faster than the local one.

**Contents**: document type, purpose, structure outline, principal claims, provenance (author, date, revision).

**Citation strategy**: synopsis claims trace back to the locators of the blocks that produced them, preserving the grounding guarantee. Without this the global path becomes uncitable, which would be a regression against the product's core promise.

**Invalidation**: recomputed on re-ingest. Version-tagged so a stale synopsis is detectable.

### 5.3 Locator abstraction

Replaces the page-integer assumption throughout metadata, transport, and UI.

**Motivation**: three of four target formats have no page numbers. Word pagination is computed at render time and never stored. Spreadsheets have sheets and cell ranges. Slides have slide indices.

**Model**: a locator carries a kind, an ordinal, a human-readable label, and an optional structural anchor. The UI renders the label without interpreting it. One citation component serves every format.

**Optional page hint**: converting Office documents to PDF at ingest yields real page numbers by matching block text against rendered pages. This preserves the "exact page citation" promise for formats that don't natively support it, and supplies a single document viewer for all formats.

**Sequencing**: this abstraction must land before any second format parser. Retrofitting it across four parsers, a stored index schema, and the frontend costs several times more than doing it once now.

### 5.4 Format parsers

Each parser's only job is producing normalized blocks. Chunking, embedding, retrieval, and citation stay format-agnostic.

| Format | Citation unit | Principal design concern |
|---|---|---|
| PDF | Page | Existing; multi-column reading order already solved |
| PPTX | Slide | Speaker notes carry the argument; slides carry fragments. Notes must be indexed and labeled distinctly. Slides are already chunk-sized — do not split further. |
| DOCX | Heading section | No page numbers exist. Reading order requires walking the document body, since paragraphs and tables are separate collections. |
| XLSX | Sheet + range | Not a retrieval problem — see below. |

### 5.5 Tabular path

**Spreadsheets must not be embedded as prose.** Structurally similar rows produce near-identical vectors; retrieval returns arbitrary rows; reranking cannot help because no row is semantically *about* anything. The model then aggregates over whichever rows happened to surface and reports a confidently wrong total.

**Design**: split the treatment.
- For *retrieval*, index only semantic content — sheet names, column headers, dtypes, a generated description per sheet, and genuinely textual columns. This keeps spreadsheets discoverable in cross-document search.
- For *answering*, generate and execute a query against the actual data.

**Security**: query execution runs generated code. It must be sandboxed — isolated process, no network, hard timeout, unprivileged user, never in the API process. This is the highest-risk component in the plan and should be gated behind explicit review.

### 5.6 Citation contract

A strict schema at the service-to-transport boundary.

**Required**: identifier, locator, source text, origin. **Derived**: display snippet, computed from source text rather than transmitted, eliminating divergence.

**Design stance**: no permissive defaults. A missing locator indicates a metadata bug in the parser and must fail at the boundary. Defaulting it to page 1 converts a visible crash into an invisible wrong citation shown to a user — a strictly worse outcome, and the direct cause of an earlier defect.

**Presentation**: only sources the answer actually cited are surfaced. Retrieved-but-unused chunks are working state, not evidence, and displaying them inflates apparent support while burying the answer.

---

## 6. Key decisions

| # | Decision | Alternatives rejected | Rationale |
|---|---|---|---|
| D1 | Route by question class | Better retrieval; larger k; more context | Five retrieval upgrades produced no movement. The gap is structural. |
| D2 | Cache a synopsis at ingest | Map-reduce per query | One-time cost; makes global answers fast and cheap |
| D3 | Generic locators over page integers | Page numbers everywhere; per-format special cases | Three of four formats have no pages |
| D4 | Normalized IR between parsing and indexing | Each parser writes to the index directly | Retrieval stays untouched as formats multiply |
| D5 | Query execution for tabular data | Embed rows | Row embeddings are not semantically separable |
| D6 | Strict citation schema | Permissive optional fields | Absorbing producer errors hides bugs and misleads users |
| D7 | Keep hand-tuned parsers | Adopt a general extraction library | Would discard the completed chunking and layout work |
| D8 | Allow inference, forbid outside knowledge | Strict extraction; unconstrained generation | Extraction cannot answer global questions; unconstrained generation fabricates |

D8 is the subtlest and warrants care. The current prompt conflates two distinct prohibitions — synthesizing across retrieved passages, and importing facts not present. Only the second is a defect. Separating them is what makes the global path possible without opening a fabrication risk.

---

## 7. Verification design

The suite currently validates only the working path. All existing benchmarks are local extractive queries; none are global. This is why five upgrades shipped green while the reported bug survived all five.

**Structural change**: quality tests, distinct from health checks, gating merges.

| Category | Purpose | Failure meaning |
|---|---|---|
| Global questions | The reported bug | Refusal or fragment = regression |
| Local extraction | Existing capability | Guards against regression from prompt loosening |
| Refusal probes | Absent information | Fabrication = over-correction on D8 |
| False-premise probes | Incorrect assertions in the question | Agreement = insufficient grounding |
| Citation integrity | Locator correctness | Uniform locators on a multi-unit document = metadata bug |
| Contract | Producer/transport agreement | Drift caught before runtime |
| Persistence | Restart survival | Keyword index rebuilt from persisted content |
| Cross-format | Correct locator kind per format | Page label on a slide = abstraction leak |

**Grading**: refusal and fabrication weighted equally. An evaluator that scores a refusal as faithful and concise will grade the current failure as a pass — which is precisely what happened. The rubric must include an unwarranted-refusal signal or it cannot see this bug.

**Baseline requirement**: capture current answers on a fixed document set before any change. Without a baseline, improvement is indistinguishable from confirmation bias.

**New global tests must fail on today's build.** If they pass, this analysis is wrong and the plan needs revisiting before anything ships.

---

## 8. Phasing

| Phase | Objective | Gate to proceed |
|---|---|---|
| **0. Instrument** | Localize the failing stage empirically; establish baseline; add failing quality tests | Stage-level evidence confirms or refutes §3 |
| **1. Route** | Query router; wire global path to the existing summarize chain | Global questions answered; local unchanged |
| **2. Ground** | Separate inference from outside knowledge in synthesis; add relevance floor | Global works *and* refusal probes still pass |
| **3. Contract** | Strict citation schema; producer assertions; boundary tests | Locator defects surface at ingest, not in the UI |
| **4. Generalize** | Locator and IR abstraction; PDF parser refactored to emit them | Existing PDF answers byte-identical |
| **5. Extend** | PPTX, then DOCX, then XLSX | Correct locator kind per format |
| **6. Enrich** | Shadow render for page hints; unified viewer | Office citations carry page references |

Phase 0 is non-negotiable. Every hypothesis in §3 is inferred from observed behavior and documentation, not from reading the code — it must be confirmed before implementation. If instrumentation shows retrieval returning irrelevant content, the ordering here is wrong and Phase 4 concerns move ahead of Phase 1.

Phases 0–2 address the reported bug. Everything after is capability expansion.

---

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Loosening extraction introduces fabrication | High — trades a visible failure for an invisible one | Refusal probes run before and after Phase 2; equal weighting in the rubric |
| Router misclassification | Medium | Bias toward GLOBAL; log every decision; review the confusion matrix weekly |
| Sandbox escape in the tabular path | Critical | Isolated process, no network, timeout, unprivileged; gate behind review |
| Locator refactor regresses PDF citations | High — breaks a working feature | Byte-identical output required on the golden set before merge |
| Synopsis becomes stale | Medium | Version tag; recompute on re-ingest |
| Office format edge cases | Medium | Per-format fixtures covering tables, grouped shapes, merged cells |
| Continued optimization of the wrong layer | High — the pattern that produced this plan | Any proposal touching embeddings or the vector store requires stage-level evidence first |

The last row is the process risk. It is the reason this document exists.

---

## 10. Success criteria

| Measure | Now | Target |
|---|---|---|
| Global questions answered without refusal | 0% | >95% |
| Fabrication rate on refusal probes | unmeasured | <2% |
| Citation locator accuracy | broken (uniform) | >98% |
| Formats supported | 1 | 4 |
| Defects reaching users undetected by tests | 3 known | 0 |

The last row is the one that matters. The other four are individual fixes; that one is whether the system can now catch its own regressions. Three defects have shipped through the same gap — the fixes address the instances, but only the verification design addresses the cause.

---

## 11. Explicitly out of scope

Graph-based retrieval, embedding model changes, vector store migration, agentic multi-hop retrieval, fine-tuning.

All are retrieval-layer work. The evidence indicates retrieval is not the constraint, and adding to it would repeat the pattern this plan is written to break. Revisit only if Phase 0 instrumentation contradicts §3.
