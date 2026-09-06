# docs/RAG_PROMPTS.md

Pipeline prompts specification, intent classification rules, query rewriting prompts, and synthesis grounding constraints.

## Critical Notice: No Downstream Validation Stage

**There is no downstream fact-checking or regeneration stage.**
The synthesis prompt is the only line of defense keeping LLM answers grounded and preventing hallucinations. Any modifications to these prompts carry high risk and must be evaluated against the faithfulness and citation accuracy gates.

---

## 1. Synthesis Grounding Prompt

Used in `backend/services/rag_service.py` and `backend/services/llm_service.py`.

### Core Requirements
1. **Source Grounding**: Base all claims strictly on the provided context passages. If the passages do not contain the answer, explicitly state:
   > *"The provided document does not contain information to answer this question."*
2. **Citation Syntax**: Every factual statement must cite the page or section where it was found using bracket notation: `[Page N]` or `[Section X]`.
3. **No Prior Knowledge**: Do not extrapolate, infer, or bring in external domain knowledge that is not corroborated by the retrieved text snippets.
4. **Data Isolation**: Never expose contact headers (phone numbers, personal emails) unless specifically requested in an identity/contact query.

---

## 2. Intent Classification Prompts & Taxonomy

Intent classification is executed by `QueryUnderstandingService`.

| Intent | Purpose | Handling |
|---|---|---|
| `GREETING` | User greetings, polite openers | Direct conversational response, no vector retrieval. |
| `META` | Structural properties (pages, sections, author, format) | Answer directly from SQLite metadata registry; never search chunks. |
| `GLOBAL` | Executive summary, core themes, overarching purpose | Answer from document synopsis / Identity Card. |
| `LOCAL` | Specific factual questions | Dense FAISS + Sparse BM25 hybrid search, BGE rerank, grounded synthesis. |
| `TABULAR` | Numerical comparisons, data tables, metrics | Extract structured rows and tables from context. |

---

## 3. Pronoun Contextualization

When a follow-up query contains ambiguous pronouns ("What was its purpose?", "How many does it have?"), the conversation memory resolves the pronoun antecedent using prior turns before retrieval.
