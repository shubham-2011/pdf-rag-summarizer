# /diagnose

Diagnoses retrieval defects, manifest inconsistencies, and format container drops.

1. Verify index manifest integrity (`index_manifest.json`).
2. Run format audit: `python audit/audit_formats.py`.
3. Check retrieval recall and BGE reranker score distribution.
