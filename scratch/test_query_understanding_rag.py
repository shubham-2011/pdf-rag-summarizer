import os
import sys
import uuid
from typing import List

# Ensure utf-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from langchain_core.documents import Document
from services.document_service import DocumentService
from services.vector_service import VectorService
from services.rag_service import RAGService
from services.query_understanding_service import QueryUnderstandingService

def run_tests():
    print("=" * 70)
    print("🧪 RUNNING COMPREHENSIVE QUERY UNDERSTANDING & RAG OVERHAUL TEST SUITE")
    print("=" * 70)

    # 1. Test Query Normalization & Intent Classification unit tests
    print("\n--- Phase 1: Query Understanding Unit Tests ---")
    
    test_cases = [
        ("hi", "GREETING"),
        ("Hello!", "GREETING"),
        ("Good morning assistant", "GREETING"),
        ("What can you do with this file?", "CAPABILITY"),
        ("How can you help me with this document?", "CAPABILITY"),
        ("What is the filename?", "META"),
        ("how many pages does this have?", "META"),
        ("what is this document about?", "GLOBAL"),
        ("what is pdf works for?", "GLOBAL"),
        ("wat is this documnt abou", "GLOBAL"), # Typos: wat -> what, documnt -> document, abou -> about
        ("summarize the entire pdf", "GLOBAL"),
        ("what is the transfomer voltage rating?", "LOCAL"), # Typo: transfomer -> transformer
        ("compare the rows in table 2", "TABULAR"),
        ("how to bake chocolate cake?", "OUT_OF_SCOPE"),
        ("who won the 2022 world cup?", "OUT_OF_SCOPE")
    ]

    all_intents_passed = True
    for q, expected_intent in test_cases:
        res = QueryUnderstandingService.process(q)
        actual = res["intent"]
        norm = res["normalized_query"]
        status = "✅ PASS" if actual == expected_intent else f"❌ FAIL (Got {actual})"
        if actual != expected_intent:
            all_intents_passed = False
        print(f"[{status}] Query: '{q}' -> Norm: '{norm}' -> Intent: {actual} (Expected: {expected_intent})")

    assert all_intents_passed, "Query understanding intent classification failed some test cases!"

    # 2. Test End-to-End RAG with Environmental Machine Learning Paper
    print("\n--- Phase 2: End-to-End Ingestion & 7-Intent RAG (Academic Paper) ---")
    doc_id_1 = "test_wqi_" + str(uuid.uuid4())[:6]
    
    chunks_1 = [
        Document(
            page_content="DESIGN AND IMPLEMENTATION OF A PYTHON PROGRAM TO PREDICT WATER QUALITY INDEX (WQI)\nA Case Study on Industrial Water Bodies.\nAuthor: Dr. Elena Vance, Dept. of Environmental Engineering.",
            metadata={"source_file": "Water_Quality_Prediction_Report.pdf", "page": 0, "page_label": 1, "is_header": True}
        ),
        Document(
            page_content="Abstract & Introduction:\nWater Quality Index (WQI) is a single dimensionless number that indicates the overall water quality based on multiple physical and chemical parameters.\nIn this study, Python machine learning algorithms including RandomForest (RF) and Support Vector Machine (SVM) were deployed to predict WQI from 12 distinct parameters.",
            metadata={"source_file": "Water_Quality_Prediction_Report.pdf", "page": 0, "page_label": 1}
        ),
        Document(
            page_content="Experimental Results & Model Evaluation:\nTable 4: Classification Performance on Test Dataset:\nModel: RandomForestClassifier - Accuracy: 96.4%, Precision: 95.8%, Recall: 96.1%, F1-Score: 95.9%.\nModel: Support Vector Machine (SVM) - Accuracy: 91.2%, Precision: 90.5%, Recall: 91.0%.\nKey water parameters evaluated included pH value (6.5 to 8.5), Turbidity (NTU), Biochemical Oxygen Demand (BOD = 4.2 mg/L), and Dissolved Oxygen (DO).",
            metadata={"source_file": "Water_Quality_Prediction_Report.pdf", "page": 1, "page_label": 2}
        )
    ]

    identity_card_1 = DocumentService.generate_identity_card(
        chunks=chunks_1,
        file_name="Water_Quality_Prediction_Report.pdf",
        total_units=2,
        ext=".pdf"
    )
    
    print(f"🪪 Identity Card Generated:\n  Title: {identity_card_1['title']}\n  Type: {identity_card_1['document_type']}\n  Domain: {identity_card_1['domain']}\n  Purpose: {identity_card_1['one_line_purpose']}")
    
    VectorService.create_collection(chunks_1, collection_name=doc_id_1, identity_card=identity_card_1)

    # Test 2.1: Greeting
    print("\n🧪 Testing 2.1: Greeting ('hi')")
    r_greet = RAGService.query(document_id=doc_id_1, question="hi")
    print(f"Answer:\n{r_greet['answer']}\n")
    assert "Hello!" in r_greet["answer"] and ("WATER QUALITY" in r_greet["answer"] or "Water Quality" in r_greet["answer"]), "Greeting failed!"

    # Test 2.2: Capability
    print("\n🧪 Testing 2.2: Capability ('what can you do?')")
    r_cap = RAGService.query(document_id=doc_id_1, question="what can you do with this document?")
    print(f"Answer:\n{r_cap['answer']}\n")
    assert "Document Intelligence Capabilities" in r_cap["answer"], "Capability failed!"

    # Test 2.3: Metadata
    print("\n🧪 Testing 2.3: Meta ('what is the filename and pages?')")
    r_meta = RAGService.query(document_id=doc_id_1, question="what is the filename and how many pages?")
    print(f"Answer:\n{r_meta['answer']}\n")
    assert ("Water_Quality_Prediction_Report.pdf" in r_meta["answer"] or "WATER QUALITY" in r_meta["answer"]) and "2" in r_meta["answer"], "Meta failed!"

    # Test 2.4: Out of Scope
    print("\n🧪 Testing 2.4: Out of Scope ('how to bake a cake?')")
    r_oos = RAGService.query(document_id=doc_id_1, question="how to bake a cake?")
    print(f"Answer:\n{r_oos['answer']}\n")
    assert "Out of Scope" in r_oos["answer"], "Out of scope check failed!"

    # Test 2.5: Global Question (Prose verification)
    print("\n🧪 Testing 2.5: Global ('what is this document about?')")
    r_global = RAGService.query(document_id=doc_id_1, question="what is this document about?")
    print(f"Answer:\n{r_global['answer']}\n")
    # Verify it is fluent prose and NOT fragmented bullets
    assert "Document Purpose & Overview" in r_global["answer"], "Global header missing!"
    assert "predict and analyze the Water Quality Index" in r_global["answer"], "Global purpose prose missing!"
    assert "• DESIGN" not in r_global["answer"], "Defect D1 regression: Found raw title bullet concatenation!"

    # Test 2.6: Global with Typos ("wat is pdf works for?")
    print("\n🧪 Testing 2.6: Global with Typos ('wat is pdf works for?')")
    r_typo_global = RAGService.query(document_id=doc_id_1, question="wat is pdf works for?")
    print(f"Answer:\n{r_typo_global['answer']}\n")
    assert "Water Quality Index" in r_typo_global["answer"], "Typo global query failed!"

    # Test 2.7: Local Retrieval with Typo ("accurcy of the RandomForest model?")
    print("\n🧪 Testing 2.7: Local retrieval with Typo ('accurcy of the RandomForest model?')")
    r_local = RAGService.query(document_id=doc_id_1, question="accurcy of the RandomForest model?")
    print(f"Answer:\n{r_local['answer']}\n")
    assert "96.4%" in r_local["answer"] or "RandomForest" in r_local["answer"], "Local retrieval failed to find 96.4% accuracy!"

    # Test 2.8: Multi-turn conversational memory with pronouns
    print("\n🧪 Testing 2.8: Multi-turn Memory ('What is its accuracy?')")
    history = [
        {"user": "What machine learning models are used in this paper?", "assistant": "The paper uses RandomForest and SVM."}
    ]
    r_multi = RAGService.query(document_id=doc_id_1, question="What is its accuracy?", chat_history=history)
    print(f"Answer:\n{r_multi['answer']}\n")
    assert "96.4%" in r_multi["answer"] or "91.2%" in r_multi["answer"], "Pronoun resolution failed!"

    # 3. Test End-to-End with Single-Line Diagram / Engineering Drawing
    print("\n--- Phase 3: Single-Line Diagram (Engineering Drawing) Ingestion & RAG ---")
    doc_id_2 = "test_sld_" + str(uuid.uuid4())[:6]
    
    chunks_2 = [
        Document(
            page_content="PROJECT: 132/33kV GRID SUBSTATION EXPANSION\nDRAWING NO: ELEC-SLD-2026-04\nTITLE: SINGLE LINE DIAGRAM (SLD) & PROTECTION SCHEME\nPREPARED BY: POWER GRID CONSULTANTS LTD.",
            metadata={"source_file": "Substation_132kV_SLD.pdf", "page": 0, "page_label": 1, "is_header": True}
        ),
        Document(
            page_content="Substation Equipment Specifications:\n1. Power Transformer TR-1: 50 MVA, 132/33 kV, ONAN/ONAF cooling, Dyn11 vector group.\n2. Power Transformer TR-2: 50 MVA, 132/33 kV, ONAN/ONAF cooling.\n3. Circuit Breaker CB-101: SF6 Gas Circuit Breaker, 145 kV, 31.5 kA breaking capacity.\n4. Current Transformer CT-1: 800-400/1-1-1A, Class 0.2S / 5P20.\n5. Busbar System: Double busbar scheme with bus coupler CB-100 (1600A).",
            metadata={"source_file": "Substation_132kV_SLD.pdf", "page": 0, "page_label": 1}
        )
    ]

    identity_card_2 = DocumentService.generate_identity_card(
        chunks=chunks_2,
        file_name="Substation_132kV_SLD.pdf",
        total_units=1,
        ext=".pdf"
    )

    print(f"🪪 SLD Identity Card Generated:\n  Title: {identity_card_2['title']}\n  Type: {identity_card_2['document_type']}\n  Domain: {identity_card_2['domain']}\n  Purpose: {identity_card_2['one_line_purpose']}")
    assert "Single-Line Diagram" in identity_card_2["document_type"] or "Engineering" in identity_card_2["domain"], "SLD type identification failed!"

    VectorService.create_collection(chunks_2, collection_name=doc_id_2, identity_card=identity_card_2)

    # Test 3.1: Global Query on SLD ("what is this drawing?")
    print("\n🧪 Testing 3.1: Global on SLD ('what is this drawing?')")
    r_sld_global = RAGService.query(document_id=doc_id_2, question="what is this drawing?")
    print(f"Answer:\n{r_sld_global['answer']}\n")
    assert "Single Line Diagram" in r_sld_global["answer"] or "electrical architecture" in r_sld_global["answer"], "SLD global query failed!"

    # Test 3.2: Local Query on Transformer with Typo ("what is the transfomer capacity?")
    print("\n🧪 Testing 3.2: Local retrieval with Typo on SLD ('what is the transfomer capacity?')")
    r_sld_local = RAGService.query(document_id=doc_id_2, question="what is the transfomer capacity?")
    print(f"Answer:\n{r_sld_local['answer']}\n")
    assert "50 MVA" in r_sld_local["answer"], "Failed to extract 50 MVA transformer capacity!"

    print("\n" + "=" * 70)
    print("🎉 ALL 15 AUTOMATED TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
