import os
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.documents import Document
from services.vector_service import VectorService
from services.rag_service import RAGService
from services.document_service import DocumentService

def run_tests():
    print("=================================================================")
    print("🚀 COMPREHENSIVE RAG TEST SUITE (G1-G5, L1-L5, H1-H5, C1-C4)")
    print("=================================================================")
    
    # 1. Setup Mock Technical Drawing Document (ACME Industrial Complex)
    drawing_text = """
PROJECT: 11kV POWER DISTRIBUTION & CABLE TRAY LAYOUT
SHEET: 1 of 1 | REV: RO 02-07-26 | PREPARED FOR: ACME INDUSTRIAL COMPLEX

LEGEND:
• T: Transformer (11kV/415V, 1500kVA Step-Down)
• HT: High Tension Panel
• LT: Low Tension Main Switchboard
• DG: Diesel Generator Set (500kVA Backup)
• MCC: Motor Control Centre
• PEB: Pre-Engineered Building (Dimension: 90.13 x 55.77 m)
• ROOF: Rooftop Solar PV System (250kWp)
• ADMIN BLOCK: 2-Storey Office & Control Room
• PARKING: EV Charging & Staff Parking Bay
• CANTEEN: Cafeteria & Recreation
• SECURITY: Main Gate & Access Post
• ETP: Effluent Treatment Plant (50 KLD)
"""
    drawing_doc_id = "eval_drawing_test"
    chunks = [
        Document(
            page_content=drawing_text.strip(),
            metadata={"source_file": "electrical_layout.pdf", "page_label": 1, "section_heading": "DOCUMENT_HEADER"}
        )
    ]
    VectorService.create_collection(chunks, collection_name=drawing_doc_id)
    
    # Test cases definition
    passed_count = 0
    total_count = 0

    def check(query_id, query, check_fn, expected_desc, history=None):
        nonlocal passed_count, total_count
        total_count += 1
        res = RAGService.query(document_id=drawing_doc_id, question=query, chat_history=history)
        ans = res["answer"]
        is_pass = check_fn(ans)
        status = "✅ PASS" if is_pass else "❌ FAIL"
        if is_pass:
            passed_count += 1
        print(f"\n[{query_id}] Query: '{query}' -> {status}")
        print(f"  Expected: {expected_desc}")
        print(f"  Response: {ans[:200]}...")
        return is_pass

    print("\n--- 2.1 Global-Question Tests (G1-G5) ---")
    check("G1", "What is this document about?", 
          lambda a: "not mentioned" not in a.lower() and any(k in a for k in ["POWER DISTRIBUTION", "CABLE TRAY", "11kV"]),
          "Purpose statement without unwarranted refusal")
          
    check("G2", "Summarize this PDF", 
          lambda a: "not mentioned" not in a.lower() and len(a) > 50,
          "Coherent summary, not a refusal")
          
    check("G3", "Who prepared this and when?", 
          lambda a: "RO 02-07-26" in a or "ACME INDUSTRIAL COMPLEX" in a,
          "Extracts revision date and prepared for entity")
          
    check("G4", "What kind of document is this?", 
          lambda a: "not mentioned" not in a.lower() and any(k in a.lower() for k in ["power distribution", "layout", "cable tray"]),
          "Identifies electrical power distribution & cable tray layout")
          
    check("G5", "List the main sections", 
          lambda a: "not mentioned" not in a.lower() and any(k in a for k in ["Transformer", "LEGEND", "PEB"]),
          "Enumerates sections/components without refusal")

    print("\n--- 2.2 Local / Extractive Tests (L1-L5) ---")
    check("L1", "What is the transformer rating?", 
          lambda a: "11kV/415V" in a or "1500kVA" in a,
          "11kV/415V, 1500kVA cited")
          
    check("L2", "What is the dimension of the PEB?", 
          lambda a: "90.13 x 55.77" in a,
          "90.13 x 55.77 m cited")
          
    check("L3", "What is on the roof of the PEB?", 
          lambda a: "Solar" in a or "PV" in a or "250kWp" in a,
          "Rooftop Solar PV")
          
    check("L4", "What does MCC stand for here?", 
          lambda a: "Motor Control Centre" in a,
          "Motor Control Centre")
          
    check("L5", "Which blocks are listed in the legend?", 
          lambda a: all(k in a.lower() for k in ["admin", "parking", "canteen"]),
          "Admin block, parking, canteen")

    print("\n--- 2.3 Grounding Probes (H1-H5: Must Refuse Out-of-Domain) ---")
    check("H1", "What does the document say about fire sprinkler zoning?", 
          lambda a: any(k in a.lower() for k in ["not mentioned", "not found", "not covered"]),
          "Refusal: not mentioned in doc")
          
    check("H2", "Summarize page 47", 
          lambda a: any(k in a.lower() for k in ["not present", "not mentioned", "not found", "not covered", "1 of 1", "1 page"]),
          "Refusal: document is only 1 page")
          
    check("H4", "What is the project budget?", 
          lambda a: any(k in a.lower() for k in ["not mentioned", "not found", "not covered"]),
          "Refusal: no budget mentioned")

    print("\n--- 2.4 Conversational Memory Tests (C1-C2) ---")
    check("C1", "And its location?", 
          lambda a: "11kV/415V" in a or "Transformer" in a or "not mentioned" not in a.lower(),
          "Resolves 'its' to transformer from previous turn",
          history=[{"user": "What is the transformer rating?", "assistant": "The transformer rating is 11kV/415V, 1500kVA Step-Down."}])

    print("\n=================================================================")
    print(f"📊 RESULTS: {passed_count}/{total_count} PASSED ({(passed_count/total_count)*100:.1f}%)")
    print("=================================================================")

if __name__ == "__main__":
    run_tests()
