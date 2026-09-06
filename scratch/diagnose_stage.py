import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from services.vector_service import VectorService
from services.rag_service import RAGService
from langchain_core.documents import Document

QUERIES = [
    ("global", "what is this document about"),
    ("global", "summarize this document"),
    ("global", "what is pdf works for?"),
    ("local",  "what is the transformer rating"),
]

sample_docs = [
    Document(
        page_content="SINGLE LINE ELECTRICAL DIAGRAM & SUBSTATION LAYOUT\nProject: Metro Station Phase 2 Electrical Works.\nPurpose: Details power distribution, 11kV/415V substation schematics, and transformer layout specifications.",
        metadata={"source_file": "electrical_layout.pdf", "page": 0, "page_label": "1", "chunk_id": "c0"}
    ),
    Document(
        page_content="EQUIPMENT RATINGS & SCHEDULE:\n- Main Transformer 1: 11kV / 415V, 1500 kVA Step-Down Transformer with ONAN cooling.\n- Diesel Generator Backup: 500 kVA 415V 3-Phase Diesel GenSet.\n- Circuit Breakers: 11kV SF6 Breakers with 25kA breaking capacity.",
        metadata={"source_file": "electrical_layout.pdf", "page": 0, "page_label": "1", "chunk_id": "c1"}
    ),
    Document(
        page_content="SITE PLAN & CONTROL BLOCKS:\nLegend:\n- Block A: Main Admin & Security Office\n- Block B: 11kV Switchgear Room\n- Block C: Battery & UPS Room\n- Block D: DG Yard & Fuel Storage\nSafety clearance of 3.5m maintained across all high voltage busbars.",
        metadata={"source_file": "electrical_layout.pdf", "page": 1, "page_label": "2", "chunk_id": "c2"}
    )
]

doc_id = "test_diag_doc"
print("[1] Ingesting test document into FAISS + BM25...")
VectorService.create_collection(sample_docs, doc_id)

print(f"\n{'='*70}\nRUNNING 4-STAGE RAG DIAGNOSTIC\n{'='*70}")

for cls, q in QUERIES:
    print(f"\n[{cls.upper()}] Query: '{q}'")
    print("-" * 50)

    # STAGE 1: Base Retrieval
    ensemble = VectorService.build_retriever(doc_id)
    if ensemble:
        base_ret = ensemble.base_retriever if hasattr(ensemble, 'base_retriever') else ensemble
        base_chunks = base_ret.invoke(q)
        print(f"STAGE 1 (Base Retrieval) : {len(base_chunks)} chunks retrieved")
        for i, d in enumerate(base_chunks[:2]):
            print(f"   [{i}] (Page {d.metadata.get('page_label')}): {d.page_content[:80].replace(chr(10), ' ')}...")
    else:
        print("STAGE 1: Retriever failed to build!")

    # STAGE 2: Reranker
    if ensemble:
        reranked_chunks = ensemble.invoke(q)
        print(f"STAGE 2 (Reranked)       : {len(reranked_chunks)} chunks")
        for i, d in enumerate(reranked_chunks[:2]):
            print(f"   [{i}] (Page {d.metadata.get('page_label')}): {d.page_content[:80].replace(chr(10), ' ')}...")

    # STAGE 3: Context Tokens / Size
    if ensemble:
        ctx_chars = sum(len(d.page_content) for d in reranked_chunks)
        print(f"STAGE 3 (Context Size)   : {ctx_chars} chars (~ {ctx_chars // 4} tokens)")

    # STAGE 4: Synthesis Output
    res = RAGService.query(document_id=doc_id, question=q)
    ans_snippet = res.get("answer", "").strip().replace("\n", " ")[:150]
    print(f"STAGE 4 (Synthesis Ans)  : {ans_snippet}...")
