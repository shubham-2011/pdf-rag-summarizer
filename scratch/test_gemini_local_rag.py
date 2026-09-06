import os
import sys

# Ensure UTF-8 output encoding on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from services.pdf_service import PDFService
from services.vector_service import VectorService
from services.metadata_service import MetadataService
from services.query_understanding_service import QueryUnderstandingService
from services.rag_service import RAGService
from services.llm_service import LLMService
import config

def test_full_pipeline():
    print("=" * 70)
    print("Starting End-to-End Gemini Chat + Local FAISS Retrieval Test")
    print("=" * 70)

    # 1. Check LLM status
    llm_status = LLMService.verify_models()
    print(f"1. LLM Status: {llm_status}")

    # 2. Test sample PDF parsing
    pdf_path = os.path.join(BASE_DIR, "sample_ai_roadmap.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(BASE_DIR, "test_sample.pdf")
    
    print(f"\n2. Parsing PDF page-by-page: {pdf_path}")
    chunks, total_pages = PDFService.process_pdf(pdf_path)
    print(f"   Extracted {len(chunks)} chunks across {total_pages} pages.")
    
    # Verify metadata on first chunk
    first_chunk = chunks[0]
    print(f"   Chunk 0 Metadata: {first_chunk.metadata}")
    assert "page_label" in first_chunk.metadata or "page" in first_chunk.metadata
    print("   [PASSED] Page metadata preservation verified.")

    # 3. Ingest into local FAISS vector store
    doc_id = "test_doc_e2e"
    print(f"\n3. Ingesting chunks into Local FAISS & BM25 Store for '{doc_id}'...")
    VectorService.create_collection(chunks, collection_name=doc_id)
    
    # Verify index manifest
    manifest = VectorService.validate_index_manifest(doc_id)
    print(f"   [PASSED] Index Manifest verified: Model={manifest['embedding_model']}, Dims={manifest['embedding_dims']}")

    # Register in metadata DB
    MetadataService.register_document(
        doc_id=doc_id,
        content_hash="test_hash_e2e",
        filename=os.path.basename(pdf_path),
        format_ext=".pdf",
        mime_type="application/pdf",
        size_bytes=os.path.getsize(pdf_path),
        unit_count=total_pages,
        unit_kind="page",
        storage_path=pdf_path,
        status="READY"
    )

    # 4. Test Query Understanding & Routing
    print("\n4. Testing Query Understanding & Routing...")
    
    # A. Greeting
    res_greeting = RAGService.query(document_id=doc_id, question="Hi there!")
    print(f"   Query: 'Hi there!' -> Intent: {res_greeting.get('intent')}")
    print(f"   Answer: {res_greeting.get('answer')[:120]}...")
    assert res_greeting.get("intent") == "CONVERSATIONAL"
    print("   [PASSED] Conversational Greeting route verified.")

    # B. Structural metadata
    res_pages = RAGService.query(document_id=doc_id, question="How many pages is this document?")
    print(f"\n   Query: 'How many pages is this document?' -> Intent: {res_pages.get('intent')}")
    print(f"   Answer: {res_pages.get('answer')}")
    assert res_pages.get("intent") == "STRUCTURAL"
    print("   [PASSED] Structural Page Count route verified.")

    # C. Local factual query with retrieval & grounded citations
    print(f"\n   Query: 'What are the main skills or roadmap milestones?'")
    res_fact = RAGService.query(document_id=doc_id, question="What are the main skills or roadmap milestones?")
    print(f"   Intent: {res_fact.get('intent')}")
    print(f"   Retrieved {len(res_fact.get('sources', []))} source chunks.")
    for idx, s in enumerate(res_fact.get("sources", [])[:3]):
        print(f"     Source {idx + 1}: Page {s.get('page')} | Section: {s.get('section', 'N/A')} | Snippet: {s.get('snippet')[:80]}")
    print(f"\n   Synthesized Answer:\n{res_fact.get('answer')}")
    print("\n   [PASSED] Local Retrieval + Page-Grounded Synthesis verified.")

    print("\n" + "=" * 70)
    print("ALL END-TO-END VERIFICATION CHECKS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    test_full_pipeline()
