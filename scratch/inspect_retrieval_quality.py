import os
import sys
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath("backend"))
import config
from services.vector_service import VectorService
from services.rag_service import RAGService

# Test on real document
doc_id = "eval_water_quality_report"
query = "which model achieved the highest predictive accuracy for WQI"

print(f"===============================================================")
print(f"[RETRIEVAL QUALITY AUDIT]")
print(f"Document ID: {doc_id}")
print(f"User Query : '{query}'")
print(f"===============================================================\n")

# 1. Inspect Candidate Retrieval
vs = VectorService.get_collection(doc_id)
bm25 = VectorService.get_bm25_retriever(doc_id)

dense_candidates = vs.as_retriever(search_kwargs={"k": 5}).invoke(query) if vs else []
bm25_candidates = bm25.invoke(query)[:5] if bm25 else []

print(f"--- 1. Dense Semantic Hits (Nomic 768d + FAISS) ---")
for i, d in enumerate(dense_candidates):
    print(f"  Rank #{i+1} | Page {d.metadata.get('page_label')} | Chunk {d.metadata.get('chunk_id')} | Section: {d.metadata.get('section_heading')}")
    print(f"    Snippet: {d.page_content[:120].strip()}...\n")

print(f"--- 2. Sparse Lexical Hits (BM25 Keyword Matching) ---")
for i, d in enumerate(bm25_candidates):
    print(f"  Rank #{i+1} | Page {d.metadata.get('page_label')} | Chunk {d.metadata.get('chunk_id')} | Section: {d.metadata.get('section_heading')}")
    print(f"    Snippet: {d.page_content[:120].strip()}...\n")

# 3. Cross-Encoder Reranking
print(f"--- 3. Cross-Encoder Reranking (BAAI/bge-reranker-base) ---")
pool = dense_candidates + bm25_candidates
reranked = VectorService.rerank_documents(query, pool, top_k=3)

for i, d in enumerate(reranked):
    score = d.metadata.get("rerank_score", "N/A")
    print(f"  [TOP RANK #{i+1}] | Rerank Score: {score} | Page: {d.metadata.get('page_label')} | Chunk: {d.metadata.get('chunk_id')}")
    print(f"     Section: {d.metadata.get('section_heading')}")
    print(f"     Content:\n     \"{d.page_content.strip()}\"\n")

# 4. Synthesized Grounded Response with Citation Verification
print(f"--- 4. Grounded Answer Synthesis & Citation Verification ---")
ans = RAGService.query(document_id=doc_id, question=query)
print(f"Served by: {ans.get('served_by')}")
print(f"Citations: {ans.get('sources')}")
print(f"\nFinal Grounded Answer:\n{ans.get('answer')}")
print(f"\n===============================================================")
