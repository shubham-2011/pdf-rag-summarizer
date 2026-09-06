import sys
import os
import re
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("backend"))

from langchain_core.documents import Document

# Simulate an electrical single-line diagram drawing (pure labels and tags)
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
    metadata={"source_file": "Electrical_Single_Line_Layout.pdf", "page": 0, "page_label": "Page 1", "is_header": True}
)

def classify_query(q: str) -> str:
    q_lower = q.lower().strip()
    is_about_whole_doc = any(phrase in q_lower for phrase in [
        "this document", "this pdf", "the document", "the pdf", "this file", "this paper", "this drawing", "this presentation", "this sheet"
    ])
    
    global_intents = [
        "what is this document about", "what is this pdf about", "what is this about",
        "what is pdf works for", "what is this pdf for", "what is this document for", "what does this document do",
        "what kind of document", "what type of document",
        "summarize this", "give me a summary", "executive summary", "overview of the document",
        "list the main sections", "structure of the document", "purpose of this document"
    ]
    
    if any(g in q_lower for g in global_intents):
        return "GLOBAL"
        
    if is_about_whole_doc and any(k in q_lower for k in ["purpose", "overview", "summary", "summarize", "sections", "scope", "describe"]):
        return "GLOBAL"
        
    return "LOCAL"

print("G1 'What is this document about?' ->", classify_query("What is this document about?"))
print("G1 'what is pdf works for?' ->", classify_query("what is pdf works for?"))
print("G2 'Summarize this PDF' ->", classify_query("Summarize this PDF"))
print("G4 'What kind of document is this?' ->", classify_query("What kind of document is this?"))
print("G5 'List the main sections' ->", classify_query("List the main sections"))
print("L1 'What is the transformer rating?' ->", classify_query("What is the transformer rating?"))
print("H1 'What does the document say about fire sprinkler zoning?' ->", classify_query("What does the document say about fire sprinkler zoning?"))

