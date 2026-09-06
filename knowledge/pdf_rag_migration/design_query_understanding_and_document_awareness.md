# Design — Query Understanding & Document Awareness

**Context**: Routing has landed; synthesis and query interpretation have not.  
**Scope**: Design only.  

---

## 1. Current state from observed behavior

| Input | Output | Reading |
|---|---|---|
| "what is this document about" | Header: *Document Purpose & Structure*; body: title-page fragments joined by bullets | Router fired. Synthesizer did not. |
| "what is this document" | *"This specific information is not mentioned"* | Router missed. Falls back to local + extractive refusal. |

Two distinct defects, currently entangled.

### D1 — The global path still extracts

The output `DESIGN AND IMPLEMENT • PYTHON PROGRAM • TO PREDICT • WATER QUALITY INDEX • Selected Case Study` is the document's title block, split at separators and concatenated. No sentence was composed. No relationship between the fragments was expressed.

This is the extractive synthesizer running under a new heading. Routing chose the right path; the path calls the wrong synthesizer. **Phase 2 of the design plan — separating "may infer across passages" from "may not import outside knowledge" — has not been applied.**

Correct output for this document would read roughly: *"A project report describing the design and implementation of a Python program that predicts a Water Quality Index, using water potability data as the case study."* Same facts, composed into a claim.

### D2 — The router is a keyword rule

Adding the single word "about" flips the classification. That is lexical matching, not intent classification. It will fail on every paraphrase a user actually types: "what is this", "explain this file", "tl;dr", "iska matlab kya hai", "wat is this doc".

### D3 — No conversational intent exists

Every input is treated as a document query. "hi" will be embedded, retrieved against, and answered with *"not mentioned in the uploaded document."* There is no path for a greeting.

### D4 — Typos are not handled

Raw user text goes straight to retrieval. BM25 is exact-match: `transfarmer` scores zero against `transformer`. Dense embeddings are partially typo-tolerant, but with the ensemble at 50/50 a misspelling silently halves retrieval quality with no error.

### D5 — The system doesn't know what document it holds

The assistant has no persistent notion of "this is a water-quality prediction project report." Each query starts from nothing and rediscovers the document through retrieval. This is why answers read as fragments rather than as statements from something that has read the file.

---

## 2. Proposed component: Query Understanding Layer

A stage between the user and retrieval. Three responsibilities, in order.

```
user input
    │
    ▼
┌─────────────────────────────────────────┐
│  1. NORMALIZE   typos, casing, pronouns │
│  2. CLASSIFY    intent                  │
│  3. DISPATCH    to the matching path    │
└─────────────────────────────────────────┘
    │
    ├── GREETING / SMALLTALK ──→ conversational reply, no retrieval
    ├── META ─────────────────→ answer from document identity card
    ├── GLOBAL ───────────────→ synopsis → synthesize
    ├── LOCAL ────────────────→ retrieve → rerank → answer with citations
    ├── TABULAR ──────────────→ query engine
    └── OUT_OF_SCOPE ─────────→ decline, explain scope
```

### 2.1 Normalization

Runs before classification and before embedding. One LLM call that:

- corrects spelling and grammar
- resolves pronouns against chat history ("what about **it**" → "what about the transformer")
- expands the query with domain synonyms drawn from the document's identity card

Design points:

- **Preserve the original.** Display the user's text; use the normalized form only for retrieval. Silently rewriting what someone typed is disorienting when the rewrite is wrong.
- **Never invent specificity.** "wat is this" normalizes to "what is this document about", not "what is the water quality index methodology". Over-expansion here manufactures a question the user didn't ask.
- **Log both forms.** When an answer is wrong, the first thing to check is whether normalization distorted the question.

Domain-synonym expansion is what makes typos recoverable in BM25. `transfarmer` → `transformer` restores exact-match capability that would otherwise be lost without any error surfacing.

### 2.2 Intent taxonomy

| Intent | Examples | Path | Retrieval? |
|---|---|---|---|
| GREETING | "hi", "hello", "thanks", "bye" | Templated conversational reply | No |
| CAPABILITY | "what can you do", "how do I use this" | Static explanation of features | No |
| META | "what file is this", "how many pages", "when was it uploaded" | Document identity card | No |
| GLOBAL | "what is this document", "summarize", "main findings", "what's the conclusion" | Synopsis → synthesize | No (pre-computed) |
| LOCAL | "what is the transformer rating", "define WQI" | Retrieve → rerank → cite | Yes |
| TABULAR | "total sales in Q3", "average by region" | Query engine | No |
| OUT_OF_SCOPE | "write me a poem", "what's the weather" | Decline, restate scope | No |

Four of seven intents need no retrieval at all. Today all seven go through it.

**Classification design:**

- LLM-based, with the intent definitions and 2–3 examples each in the prompt. Not keyword rules — D2 is the direct consequence of rules.
- The prompt must include **the document's identity** so classification is context-aware. "What is the WQI?" is LOCAL in a water-quality report and OUT_OF_SCOPE in an electrical drawing.
- Return the label plus a confidence. Low confidence defaults to GLOBAL, since the global path degrades gracefully on specific questions while the local path fails hard on broad ones.
- Log every classification with the input. The confusion matrix over real traffic is the only way to tune this honestly.

**Cheap pre-filter**: exact-match greetings under four tokens ("hi", "hey", "thanks") can skip the LLM call entirely. This is a latency optimization, not the classifier — don't let it grow into the rule engine that caused D2.

### 2.3 Document identity card

The missing piece behind D5, and the thing that makes the assistant feel like it has read the file.

Computed once at ingest, cached with the index, and injected into the system prompt of every downstream call.

| Field | Purpose |
|---|---|
| Title | Display, and grounding for the classifier |
| Document type | "academic project report", "electrical single-line drawing" |
| Domain | "water quality / machine learning" — drives synonym expansion |
| One-line purpose | Answers META and seeds GLOBAL |
| Structure outline | Section or slide list; enables "summarize section 3" |
| Key entities | Terms, acronyms, model names — feeds normalization |
| Provenance | Author, date, revision, page/slide/sheet count |

Effects across the system:

- **Classification** becomes document-aware rather than generic.
- **Normalization** can expand `WQI` → `Water Quality Index` because the entity list contains it.
- **META** questions are answered instantly with no retrieval.
- **GLOBAL** answers start from a real characterization instead of assembling one from fragments each time.
- **Refusals become informative**: instead of "not mentioned," the system can say what the document *does* cover.

The card is small — a few hundred tokens — and cheap to carry in every prompt. It is the highest leverage item in this design.

---

## 3. Fixing the global path (D1)

Routing alone doesn't produce a summary. The global path must call a synthesizing prompt, not an extracting one.

**Required distinction**, currently conflated:

| Permitted | Forbidden |
|---|---|
| Composing a sentence that appears nowhere in the source | Stating a fact not present in the source |
| Relating fragments to each other | Inferring beyond what the fragments support |
| Characterizing the document as a whole | Importing outside knowledge of the subject |

The current prompt forbids both columns, which is why the output is a fragment concatenation. Only the right column is a defect.

**Output shape** for GLOBAL should be specified explicitly: complete prose sentences, no bullet-fragment lists, minimum length, and the constraint that the document must be described *as a thing* rather than quoted from. The observed output would fail a "must contain a complete sentence" check — that check is worth encoding as a test.

**Source of content**: the pre-computed synopsis, not live retrieval. Retrieval on a global question returns fragments, which is exactly what produced the observed output.

---

## 4. Citation rendering on the global path

The `(1)` markers repeating after every fragment are the page-metadata defect resurfacing on the new path. Two design rules:

- Global answers cite **ranges or sections**, not per-fragment page numbers. "Summarized from pp. 1–14" is honest; "(1)" five times is noise.
- The strict citation contract applies to both paths. If the global path emits page 1 for everything, the same producer-side assertion should fail there too.

---

## 5. Interaction design for non-retrieval intents

**Greetings** should orient, not just acknowledge. A reply that names the loaded document and suggests two or three answerable questions converts an idle "hi" into a productive turn — and demonstrates D5's identity card is working.

**Out-of-scope** replies should state what the system *can* do with the current document rather than only what it won't do.

**Refusals** should distinguish three cases that currently collapse into one string:
- the document doesn't cover this
- the question is ambiguous
- retrieval found nothing above threshold

Each warrants a different next step for the user, and merging them is why "not mentioned" was so uninformative during debugging.

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Normalization distorts intent | High — trades a visible failure for an invisible one | Log original and rewritten; conservative expansion; never add specificity |
| Classifier misfires on multilingual or code-switched input | Include such examples in the prompt; test with them explicitly |
| Added latency from two extra LLM calls | Fast-path exact greetings; combine normalize+classify into one call; cache per session |
| Identity card wrong for unusual documents | Show it in the UI so users can see what the system thinks it has |
| Loosening synthesis introduces fabrication | Refusal and false-premise probes before and after |

The last one is the same trade recorded in the design plan. It applies with more force here, because the global path has no retrieved context constraining it — only the synopsis.

---

## 7. Sequence

| # | Change | Fixes |
|---|---|---|
| 1 | Synthesizing prompt on the global path | **D1** — the observed fragment output |
| 2 | Document identity card at ingest | D5, and unblocks 3–4 |
| 3 | LLM intent classifier replacing keyword rules | **D2** — "what is this document" refusing |
| 4 | Normalization stage | D4 typos, pronoun resolution |
| 5 | Greeting / capability / meta paths | D3 |
| 6 | Global-path citation ranges | the repeating `(1)` |

Item 1 first. It is the smallest change and fixes the defect visible in the current screenshot — routing already works, so only the prompt behind it needs replacing.

---

## 8. Tests this implies

- A GLOBAL answer must contain at least one complete sentence with a verb. The observed output fails this.
- "what is this document", "what is this doc", "wat is this documnt", "summarize", "tl;dr" must all classify as GLOBAL.
- "hi" must not trigger retrieval and must not produce a refusal.
- A misspelled technical term must retrieve the same chunks as the correct spelling.
- A GLOBAL answer must not consist solely of fragments joined by bullet characters.
- The identity card must be non-empty for every successfully ingested document.

The first and last are the ones that would have caught today's state.
