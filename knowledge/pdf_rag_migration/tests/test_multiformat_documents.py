import sys
import os
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("backend"))

import docx
from pptx import Presentation
import pandas as pd
from services.document_service import DocumentService
from services.vector_service import VectorService
from services.rag_service import RAGService

test_dir = os.path.abspath("scratch/test_docs")
os.makedirs(test_dir, exist_ok=True)

# 1. Generate sample .docx
docx_path = os.path.join(test_dir, "sample_contract.docx")
doc = docx.Document()
doc.add_heading("Cloud Infrastructure Agreement", 0)
doc.add_paragraph("This agreement is between Alpha Inc and Beta LLC.")
doc.add_paragraph("Total Contract Value: $450,000 USD.")
doc.add_paragraph("Project Lead: Shubham Kumar (shubham@example.com).")
doc.save(docx_path)

# 2. Generate sample .pptx
pptx_path = os.path.join(test_dir, "quarterly_roadmap.pptx")
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Q3 Product Architecture Roadmap"
slide.placeholders[1].text = "1. Migration to Google Gemini 2.0 Flash\n2. ChromaDB RAG Vector Store\n3. Completion by December 2026"
prs.save(pptx_path)

# 3. Generate sample .xlsx
xlsx_path = os.path.join(test_dir, "financial_report.xlsx")
df = pd.DataFrame({
    "Quarter": ["Q1", "Q2", "Q3", "Q4"],
    "Revenue_USD": [120000, 150000, 180000, 220000],
    "Growth_Rate": ["12%", "15%", "18%", "22%"]
})
df.to_excel(xlsx_path, index=False)

# 4. Generate sample .csv
csv_path = os.path.join(test_dir, "employees.csv")
df_emp = pd.DataFrame({
    "Employee": ["Shubham Kumar", "Jane Doe", "Alex Smith"],
    "Role": ["Full Stack Engineer", "Product Manager", "DevOps Specialist"],
    "Phone": ["+91-7322007327", "+1-555-0199", "+44-20-7946"]
})
df_emp.to_csv(csv_path, index=False)

print("🧪 Testing Multi-Format Document Ingestion & RAG Queries:")

for name, path, q in [
    ("Word (.docx)", docx_path, "What is the total contract value?"),
    ("PowerPoint (.pptx)", pptx_path, "What is the target completion date for the roadmap?"),
    ("Excel (.xlsx)", xlsx_path, "What was the revenue for Q3?"),
    ("CSV (.csv)", csv_path, "What is the phone number of Shubham Kumar?")
]:
    is_valid, reason = DocumentService.audit_document(path, os.path.getsize(path))
    chunks, units = DocumentService.process_document(path)
    collection_id = "test_" + os.path.splitext(os.path.basename(path))[0]
    VectorService.create_collection(chunks, collection_name=collection_id)
    ans = RAGService.query(document_id=collection_id, question=q)
    print(f"\n📄 [{name}] Audit: {is_valid} ({reason}) | Chunks: {len(chunks)}")
    print(f"   Query: '{q}'")
    print(f"   Answer:\n{ans['answer']}")
