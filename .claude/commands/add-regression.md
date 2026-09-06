# /add-regression

Workflow for adding a regression test when fixing a bug:
1. Identify the symptom and root cause.
2. Add a new test method to `tests/test_incident_regressions.py`.
3. Add a corresponding entry to `docs/INCIDENTS.md`.
4. If the bug produced an architectural boundary rule, update `AGENTS.md`.
5. Verify tests pass with `python tests/run_pipeline.py --fast`.
