# docs/TESTING.md

Test architecture, stages, release gates, and metric definitions.

## Test Stages

1. **Stage 1: Deterministic Gates (`--fast`)**:
   - Ingestion boundary checks (A1).
   - Chunk delimiter and integrity checks (A2).
   - Index manifest and asymmetric prefix checks (A3).
   - Registry state machine and deletion checks (A4).
   - Hybrid retrieval & BGE reranker checks (B1–B4).
   - Intent classification benchmarks (C1–C3).
   - Grounding and citation checks (D1–D4).
   - Architecture boundary offline checks (E1).
   - Regressions from historical incidents (R1–R7).
   - Multi-format ingestion audits.
   - *Cost*: 0 tokens, 100% offline, runs in ~25–30 seconds.

2. **Stage 2: Full Evaluation (with LLM Judges)**:
   - Faithfulness evaluation via LLM judge.
   - Over-refusal evaluation over tricky answerable questions.
   - Synthesis quality and global synopsis coverage.

## CI Release Gates Scorecard Definitions

| Metric | Target | Definition |
|---|---|---|
| `faithfulness_mean` | `>= 4.0` | Average score (1–5) measuring factual adherence to retrieved context without hallucination. |
| `over_refusal_rate` | `<= 0.05` | Proportion of valid, answerable document queries falsely rejected as out-of-scope. |
| `intent_accuracy` | `>= 0.90` | Accuracy across 100+ multi-class queries (`GREETING`, `META`, `GLOBAL`, `LOCAL`, `TABULAR`). |
| `global_to_local_confusion` | `== 0` | Zero queries asking for high-level summaries erroneously routed to isolated local chunks. |
| `page_citation_accuracy` | `>= 0.95` | Proportion of cited page numbers that actually contain the referenced factual evidence. |
| `gold_in_top_3` | `>= 0.85` | Retrieval recall: gold-standard chunk ranked in top-3 after hybrid search and BGE rerank. |
| `R1_R7_regressions` | `100%` | Zero regressions on all historical production defects from Logs 09–21. |
| `offline_ingestion` | `PASS` | Complete ingestion and indexing succeeds with zero network calls and without cloud API keys. |
