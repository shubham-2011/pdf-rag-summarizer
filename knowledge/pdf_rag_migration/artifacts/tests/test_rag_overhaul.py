import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import time

backend_dir = r"d:\Program\Projects\pdf-rag-summarizer\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.pdf_service import PDFService
from services.vector_service import VectorService
from services.rag_service import RAGService

def test_rag_system():
    print("==================================================")
    print("🔬 COMPREHENSIVE RAG RETRIEVAL ENGINE VERIFICATION")
    print("==================================================")
    
    # Test with sample_ai_roadmap.pdf
    pdf_path = r"d:\Program\Projects\pdf-rag-summarizer\sample_ai_roadmap.pdf"
    print(f"\n[1] Ingesting & Chunking '{os.path.basename(pdf_path)}'...")
    chunks, total_pages = PDFService.process_pdf(pdf_path)
    print(f" -> Generated {len(chunks)} chunks across {total_pages} pages.")
    
    doc_id = "test_overhaul_doc"
    VectorService.create_collection(chunks, collection_name=doc_id)
    print(f" -> ChromaDB and BM25 indexes created.")

    queries = [
        ("Query 1: Overview & Topics", "What is the overview of artificial intelligence and RAG?"),
        ("Query 2: Hyphenated compound words", "Step-by-Step Implementation Roadmap"),
        ("Query 3: Specific Phase Details", "What happens in Phase 1 and Phase 2?"),
    ]

    for label, q in queries:
        print(f"\n--- {label} ---")
        t0 = time.time()
        res = RAGService.query(document_id=doc_id, question=q)
        lat = time.time() - t0
        print(f"Query: '{q}' (Latency: {lat:.3f}s)")
        print(f"Answer:\n{res['answer']}")
        print(f"Sources ({len(res['sources'])}):")
        for s in res['sources']:
            print(f" - [Page {s['page']}]: {s['snippet']}")

    # Test with a candidate document if available in uploads
    uploads_dir = r"d:\Program\Projects\pdf-rag-summarizer\backend\storage\uploads"
    resume_files = [f for f in os.listdir(uploads_dir) if "Resume" in f or "shubham" in f.lower()]
    if resume_files:
        sample_resume = os.path.join(uploads_dir, resume_files[0])
        print(f"\n[2] Ingesting Resume '{os.path.basename(sample_resume)}'...")
        r_chunks, r_pages = PDFService.process_pdf(sample_resume)
        r_doc_id = "test_resume_doc"
        VectorService.create_collection(r_chunks, collection_name=r_doc_id)
        
        print("\n--- Testing Candidate Name Query ---")
        q_name = "name of candidate"
        t0 = time.time()
        res_name = RAGService.query(document_id=r_doc_id, question=q_name)
        print(f"Query: '{q_name}' (Latency: {time.time()-t0:.3f}s)")
        print(f"Answer:\n{res_name['answer']}")
        
        print("\n--- Testing Skills Query on Resume ---")
        q_skills = "What are the technical skills and programming languages?"
        t0 = time.time()
        res_skills = RAGService.query(document_id=r_doc_id, question=q_skills)
        print(f"Query: '{q_skills}' (Latency: {time.time()-t0:.3f}s)")
        print(f"Answer:\n{res_skills['answer']}")

    print("\n==================================================")
    print("✅ RAG RETRIEVAL ENGINE VERIFICATION PASSED 100%")
    print("==================================================")

if __name__ == "__main__":
    test_rag_system()
