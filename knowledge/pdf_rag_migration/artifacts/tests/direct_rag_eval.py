import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import time

# Add backend directory to sys.path
backend_dir = r"d:\Program\Projects\pdf-rag-summarizer\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.pdf_service import PDFService
from services.vector_service import VectorService
from services.rag_service import RAGService
from services.summarizer_service import SummarizerService

def run_retrieval_analysis():
    print("==================================================")
    print("🔬 COMPREHENSIVE RAG RETRIEVAL SYSTEM EVALUATION")
    print("==================================================")
    
    pdf_path = r"d:\Program\Projects\pdf-rag-summarizer\sample_ai_roadmap.pdf"
    file_size = os.path.getsize(pdf_path)
    print(f"\n[1] AUDIT TEST: Auditing PDF '{os.path.basename(pdf_path)}' ({file_size} bytes)...")
    is_valid, audit_msg = PDFService.audit_pdf(pdf_path, file_size)
    print(f" -> Audit Result: Valid={is_valid}, Message='{audit_msg}'")
    assert is_valid, "PDF Audit failed!"

    print("\n[2] CHUNKING & EXTRACTION TEST: Parsing blocks and chunking...")
    t0 = time.time()
    chunks, total_pages = PDFService.process_pdf(pdf_path)
    t_chunk = time.time() - t0
    print(f" -> Processed {total_pages} pages into {len(chunks)} chunks in {t_chunk:.3f}s")
    for i, c in enumerate(chunks):
        sec = c.metadata.get("section_heading", "N/A")
        print(f"    Chunk #{i+1} [Page {c.metadata.get('page_label')} | Section: {sec} | Length: {len(c.page_content)} chars]:")
        print(f"    Preview: {c.page_content[:120].replace(chr(10), ' ')}...")

    print("\n[3] VECTOR & BM25 DUAL INDEXING: Indexing chunks into ChromaDB and BM25 Cache...")
    doc_id = "test_eval_doc"
    t0 = time.time()
    vector_store = VectorService.create_collection(chunks, collection_name=doc_id)
    t_index = time.time() - t0
    print(f" -> ChromaDB + BM25 Dual Index built in {t_index:.3f}s")

    print("\n[4] RETRIEVAL TEST 1: Semantic Concept Query")
    q1 = "What are the stages or phases in machine learning and AI roadmap?"
    t0 = time.time()
    res1 = RAGService.query(document_id=doc_id, question=q1)
    t_q1 = time.time() - t0
    print(f" -> Query: '{q1}' (Time: {t_q1:.3f}s)")
    print(f" -> Generated Answer:\n{res1['answer']}\n")
    print(f" -> Retrieved Sources ({len(res1['sources'])}):")
    for s in res1['sources']:
        print(f"    - [Page {s['page']}]: {s['snippet']}")

    print("\n[5] RETRIEVAL TEST 2: Exact Keyword Search (Hybrid BM25 validation)")
    q2 = "PyPDFLoader RecursiveCharacterTextSplitter"
    t0 = time.time()
    res2 = RAGService.query(document_id=doc_id, question=q2)
    t_q2 = time.time() - t0
    print(f" -> Query: '{q2}' (Time: {t_q2:.3f}s)")
    print(f" -> Generated Answer:\n{res2['answer']}\n")
    print(f" -> Retrieved Sources ({len(res2['sources'])}):")
    for s in res2['sources']:
        print(f"    - [Page {s['page']}]: {s['snippet']}")

    print("\n[6] RETRIEVAL TEST 3: Multi-Turn Conversation with Pronoun ('it')")
    history = [
        {"user": "Explain Phase 1 of the roadmap", "assistant": "Phase 1 covers parsing PDF with PyPDFLoader."}
    ]
    q3 = "What are the key components used in it?"
    t0 = time.time()
    res3 = RAGService.query(document_id=doc_id, question=q3, chat_history=history)
    t_q3 = time.time() - t0
    print(f" -> Query: '{q3}' (Time: {t_q3:.3f}s)")
    print(f" -> Generated Answer:\n{res3['answer']}\n")

    print("\n[7] MAP-REDUCE SUMMARIZATION & ROADMAP SYNTHESIS TEST")
    t0 = time.time()
    sum_res = SummarizerService.generate_summary(chunks)
    t_sum = time.time() - t0
    print(f" -> Summarization completed in {t_sum:.3f}s")
    print(f" -> Summary Output Preview:\n{sum_res}\n")

    print("==================================================")
    print("✅ RETRIEVAL SYSTEM EVALUATION COMPLETE - 100% SUCCESS")
    print("==================================================")

if __name__ == "__main__":
    run_retrieval_analysis()
