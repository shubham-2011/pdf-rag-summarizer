# tests/AGENTS.md

Instructions and conventions for adding, modifying, or evaluating tests in the Document Intelligence Platform.

## Commands

```bash
# Deterministic & regression tests (0 tokens, fast, run this first):
python tests/run_pipeline.py --fast

# Full CI pipeline including LLM judge evaluations:
python tests/run_pipeline.py

# Adapter wiring verification:
python tests/run_pipeline.py --wiring

# Self-test mock mutation suite:
python tests/selftest_mock.py
```

## Structure & Ownership

- `test_audit_rules.py` (A1): Ingestion boundaries (file size, page limits, magic bytes, OCR errors).
- `test_chunk_quality.py` (A2): Semantic chunking, no mid-word cuts, section header retention.
- `test_index_manifest_and_prefixes.py` (A3): Manifest schema integrity, Nomic asymmetric prefixes.
- `test_registry_state_machine.py` (A4): Lifecycle transitions, illegal skips, atomic deletion.
- `test_retrieval_and_reranking.py` (B1–B4): FAISS + BM25 hybrid balance, BGE reranker latency (<5s).
- `test_query_understanding_suite.py` (C1–C3): Intent classification, no false refusals, Identity Card.
- `test_synthesis_and_citations.py` (D1–D4): Grounding, unanswerable probe, page citations.
- `test_architecture_boundary_ci.py` (E1): Local retrieval vs Cloud synthesis isolation.
- `test_incident_regressions.py` (R1–R7): Historical incidents from Logs 09–21.
- `test_multi_format_chunking.py`: Multi-format ingestion audits (DOCX, PPTX, XLSX).

## Hard Testing Rules

1. **Deterministic tests must not require API keys or network.**
   Always run with local models (`nomic-ai/nomic-embed-text-v1.5`, `BAAI/bge-reranker-base`) or mock responses.
2. **Never delete an incident regression test.**
   Each test in `test_incident_regressions.py` corresponds to a bug that shipped.
3. **Parametrize page count tests.**
   Always test across 1-page, 2-page, 3-page, and 15-page fixtures to prevent silent hardcoding regressions.
4. **All CI release gates must pass before merge.**
   Faithfulness >= 4.0, Over-refusal <= 5%, Intent accuracy >= 90%, Citation accuracy >= 95%, Top-3 recall >= 85%.
