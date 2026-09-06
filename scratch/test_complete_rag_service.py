import sys
import os
import re
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("backend"))

from langchain_core.documents import Document
from services.vector_service import VectorService
from services.rag_service import RAGService

# Test Document: Electrical Single Line Diagram
drawing_chunk = Document(
    page_content="""PROJECT: 11kV POWER DISTRIBUTION & CABLE TRAY LAYOUT
SHEET: 1 of 1 | REV: RO 02-07-26 | PREPARED FOR: ACME INDUSTRIAL COMPLEX
LEGEND:
• T: Transformer (11kV/415V, 1500kVA Step-Down)
• HT: High Tension Panel
• LT: Low Tension Main Switchboard
• MCC: Motor Control Centre
• PEB: Pre-Engineered Building (Dimension: 90.13 x 55.77 m)
• ROOF: 250kW Rooftop Solar / PV Array
• BLOCKS: Admin Block, Parking Area, Canteen, Security Gate, DG Set Room, ETP Area
CABLE TRAY SPECIFICATION: 450mm Perforated GI Tray along Main Spine.""",
    metadata={"source_file": "Electrical_Single_Line_Layout.pdf", "page": 0, "page_label": 1, "is_header": True, "section_heading": "DOCUMENT_HEADER"}
)

VectorService.create_collection([drawing_chunk], collection_name="test_electrical_drawing")

print("--- Testing Global & Local RAG Queries on Drawing ---")
test_queries = [
    ("G1", "what is pdf works for?"),
    ("G1", "What is this document about?"),
    ("G2", "Summarize this PDF"),
    ("G4", "What kind of document is this?"),
    ("G5", "List the main sections"),
    ("L1", "What is the transformer rating?"),
    ("L2", "What is the dimension of the PEB?"),
    ("H1", "What does the document say about fire sprinkler zoning?")
]

for q_id, q in test_queries:
    res = RAGService.query(document_id="test_electrical_drawing", question=q)
    print(f"\n[{q_id}] Query: '{q}'")
    print(f"Answer:\n{res['answer']}")
