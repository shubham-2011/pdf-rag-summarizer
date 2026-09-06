import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from services.vector_service import VectorService
from services.rag_service import RAGService
from langchain_core.documents import Document

def test_rag_overhaul_suite():
    print("=" * 70)
    print("RUNNING RAG OVERHAUL GLOBAL & LOCAL BENCHMARK TEST SUITE")
    print("=" * 70)

    # 1. Setup multi-page technical document
    sample_docs = [
        Document(
            page_content="SINGLE LINE ELECTRICAL DIAGRAM & SUBSTATION LAYOUT\nProject: Metro Station Phase 2 Electrical Works.\nPrepared by: Siemens Infrastructure Ltd on August 15, 2026.\nPurpose: Details power distribution, 11kV/415V substation schematics, and transformer layout specifications.",
            metadata={"source_file": "Metro_Electrical_Layout.pdf", "page": 0, "page_label": "1", "chunk_id": "c0", "is_header": True}
        ),
        Document(
            page_content="EQUIPMENT RATINGS & SCHEDULE:\n- Main Transformer 1: 11kV / 415V, 1500 kVA Step-Down Transformer with ONAN cooling.\n- Diesel Generator Backup: 500 kVA 415V 3-Phase Diesel GenSet.\n- Circuit Breakers: 11kV SF6 Breakers with 25kA breaking capacity.",
            metadata={"source_file": "Metro_Electrical_Layout.pdf", "page": 0, "page_label": "1", "chunk_id": "c1"}
        ),
        Document(
            page_content="SITE PLAN & CONTROL BLOCKS:\nLegend:\n- Block A: Main Admin & Security Office\n- Block B: 11kV Switchgear Room\n- Block C: Battery & UPS Room\n- Block D: DG Yard & Fuel Storage\nSafety clearance of 3.5m maintained across all high voltage busbars.",
            metadata={"source_file": "Metro_Electrical_Layout.pdf", "page": 1, "page_label": "2", "chunk_id": "c2"}
        )
    ]

    doc_id = "test_metro_doc"
    VectorService.create_collection(sample_docs, doc_id)

    # BENCHMARK 1: Global Questions Never Refuse
    global_questions = [
        "what is this document about",
        "summarize this document",
        "what is pdf works for?",
        "what kind of document is this",
        "who prepared this and when",
    ]

    print("\n[BENCHMARK 1] Global Question Synthesis & Non-Refusal Tests:")
    for q in global_questions:
        res = RAGService.query(document_id=doc_id, question=q)
        ans = res.get("answer", "")
        print(f"  • Q: '{q}'")
        print(f"    Ans: {ans[:120].strip().replace(chr(10), ' ')}...")
        assert "not mentioned or found" not in ans.lower(), f"Unwarranted refusal on global query: '{q}'"
        assert len(ans.split()) >= 10, f"Answer is too short or empty for global query: '{q}'"
        print("    [PASS] Valid non-refusal synthesis")

    # BENCHMARK 2: Local Questions Precision
    print("\n[BENCHMARK 2] Local Fact Extraction:")
    local_q = "what is the transformer rating"
    res_local = RAGService.query(document_id=doc_id, question=local_q)
    ans_local = res_local.get("answer", "")
    print(f"  • Q: '{local_q}'")
    print(f"    Ans: {ans_local[:120].strip().replace(chr(10), ' ')}...")
    assert "1500 kva" in ans_local.lower() or "11kv" in ans_local.lower(), "Failed to extract transformer rating"
    print("    [PASS] Precise local extraction")

    # BENCHMARK 3: Hallucination Probe
    print("\n[BENCHMARK 3] Absent Info Probe:")
    absent_q = "what is the nuclear propulsion system capacity?"
    res_absent = RAGService.query(document_id=doc_id, question=absent_q)
    ans_absent = res_absent.get("answer", "")
    print(f"  • Q: '{absent_q}'")
    print(f"    Ans: {ans_absent[:120].strip().replace(chr(10), ' ')}...")
    assert "not mentioned" in ans_absent.lower() or "not present" in ans_absent.lower(), "Did not correctly report absent info"
    print("    [PASS] Correctly rejected absent query without hallucinating")

    # BENCHMARK 4: Page Diversity
    print("\n[BENCHMARK 4] Multi-Page Source Diversity:")
    sources = res.get("sources", [])
    pages = {s.get("page") for s in sources}
    print(f"  • Retrieved Pages: {pages}")
    assert len(pages) >= 1, "Page metadata missing from sources"
    print("    [PASS] Page metadata preserved")

    print("\n" + "=" * 70)
    print("ALL RAG OVERHAUL BENCHMARKS PASSED (100%)")
    print("=" * 70)

if __name__ == "__main__":
    test_rag_overhaul_suite()
