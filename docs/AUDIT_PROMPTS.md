# docs/AUDIT_PROMPTS.md

Auditing extraction quality, container coverage, and building ground-truth evaluation datasets.

## Canary Token Audit Strategy

To guarantee that extraction does not silently drop document structures (such as tables, headers, footers, or text boxes), the extraction auditor uses **synthetic fixtures with planted canary tokens**.

### Rules for Audit Fixtures
1. **Canary Placement**:
   - Plant unique alphanumeric canaries (e.g. `CANARY_DOCX_TABLE_ROW_01`, `CANARY_DOCX_HEADER_SEC1`, `CANARY_PPTX_NOTES_SLIDE2`) into each container type.
2. **Deterministic Verification**:
   - Any canary present in the input file that does not appear in the extracted chunks indicates an extraction defect.
3. **Zero Critical Findings**:
   - Continuous integration fails if any critical container loses its canary tokens.
4. **Unit Semantics Audit**:
   - Asserts that DOCX never claims to have "pages".
   - Asserts that PPTX uses "slides".
   - Asserts that XLSX uses "sheets" and "rows".
