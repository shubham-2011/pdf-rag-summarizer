import os
import sys
import pickle
sys.path.insert(0, r"d:\Program\Projects\pdf-rag-summarizer\backend")
import config

for store in ["eval_technical_manual_long", "eval_water_quality_report", "eval_electrical_layout_drawing", "757636a1"]:
    p = os.path.join(config.VECTOR_STORE_DIR, store, "chunks.pkl")
    if os.path.exists(p):
        with open(p, "rb") as f:
            chunks = pickle.load(f)
        print(f"\n=== Store: {store} ({len(chunks)} chunks) ===")
        for c in chunks[:4]:
            print(f"[{c.metadata.get('chunk_id')}] (p.{c.metadata.get('page_label')}, sec={c.metadata.get('section_heading')}): {c.page_content[:100]}...")
