import sys
import os
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("backend"))

from services.rag_service import RAGService
from langchain_core.documents import Document

sample_doc1 = Document(
    page_content="""1. Shubham Kumar Mobile: +91-7322007327 Email: shubhammishra000@gmail.com GitHub: https://github.com/shubham200020 LinkedIn: https://linkedin.com/in/shubham-kumar-48b57023b
CAREER OBJECTIVE
Enthusiastic Software Engineer with strong foundation in full stack development.
TECHNICAL SKILLS
Languages: Java, Python, JavaScript, TypeScript
Frontend: Angular, React, HTML5, CSS3
Backend: Spring Boot, ASP.NET Core, Hibernate, JPA
Databases: Oracle, PostgreSQL, MySQL""",
    metadata={"page": 0, "page_label": 1, "section_heading": "DOCUMENT_HEADER", "is_header": True}
)

sample_doc2 = Document(
    page_content="""EXPERIENCE
Software Engineer at TechCorp (Feb 2024 – Nov 2024)
• Developed and maintained web application features using Angular and Spring Boot.
• Optimized Oracle DB queries, improving application performance by 20%.
• Collaborated in Agile sprints and daily standups.""",
    metadata={"page": 1, "page_label": 2, "section_heading": "EXPERIENCE"}
)

sample_doc3 = Document(
    page_content="""EDUCATION
MSC Computer Science [2025] - XYZ University
Computer Science [2020–2023] - ABC College
Senior Secondary [2017–2020] - High School""",
    metadata={"page": 1, "page_label": 2, "section_heading": "EDUCATION"}
)

docs = [sample_doc2, sample_doc1, sample_doc3]

for q in ["what is candidate name", "what is phone number", "what is email", "what are technical skills", "what is company"]:
    res = RAGService.extract_smart_sentences(docs, q)
    print(f"\n--- Question: '{q}' ---")
    for pg, text, score in res[:3]:
        print(f"  (Page {pg}) [Score {score}]: {text}")
