import sys
import os
sys.path.insert(0, r"d:\Program\Projects\pdf-rag-summarizer\backend")
from services.vector_service import VectorService

vs = VectorService.get_collection("757636a1")
print("VectorStore:", vs)
if vs:
    docs = vs.similarity_search("What skills are listed?", k=10)
    print(f"Found {len(docs)} docs:")
    for i, d in enumerate(docs):
        print(f"\n--- Chunk {i+1} (Page {d.metadata.get('page_label', d.metadata.get('page'))}) ---")
        print("Metadata:", d.metadata)
        print("Content:\n", d.page_content)
