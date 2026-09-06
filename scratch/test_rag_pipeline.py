import sys
import os
import re
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("backend"))

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

def smart_answer(docs, question):
    q_lower = question.lower().strip()
    
    # Check 1: Contact info intent (phone, email, github, linkedin)
    is_phone_query = any(k in q_lower for k in ["phone", "mobile", "number", "tel", "cell", "contact number", "call"])
    is_email_query = any(k in q_lower for k in ["email", "mail", "gmail", "inbox", "e-mail"])
    is_github_query = any(k in q_lower for k in ["github", "git", "repo", "repository"])
    is_linkedin_query = any(k in q_lower for k in ["linkedin", "profile", "social"])
    is_name_query = any(k in q_lower for k in ["name", "who is", "candidate", "author", "whose resume", "applicant"])
    
    for doc in docs:
        pg = str(doc.metadata.get("page_label", doc.metadata.get("page", "1")))
        text = doc.page_content
        
        if is_phone_query:
            p_match = re.search(r'(?:mobile|phone|tel|cell)?[:\s]*(\+?\d[\d\s\-\(\)]{8,16}\d)', text, re.I)
            if p_match:
                return f"### 📌 Extracted Answer\n\n• **(Page {pg})**: **Mobile / Phone Number**: {p_match.group(1).strip()}"
                
        if is_email_query:
            e_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
            if e_match:
                return f"### 📌 Extracted Answer\n\n• **(Page {pg})**: **Email Address**: {e_match.group(1).strip()}"

        if is_github_query:
            g_match = re.search(r'(https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+)', text, re.I)
            if g_match:
                return f"### 📌 Extracted Answer\n\n• **(Page {pg})**: **GitHub Profile**: {g_match.group(1).strip()}"

        if is_linkedin_query:
            l_match = re.search(r'(https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+)', text, re.I)
            if l_match:
                return f"### 📌 Extracted Answer\n\n• **(Page {pg})**: **LinkedIn Profile**: {l_match.group(1).strip()}"

        if is_name_query:
            # Check top lines of page 1
            if pg in ["1", "0"] or doc.metadata.get("is_header"):
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                for l in lines[:4]:
                    # Extract text before any contact keyword
                    name_part = re.split(r'\b(?:mobile|email|phone|github|linkedin|tel|cell)\b', l, flags=re.I)[0].strip()
                    n_match = re.match(r'^(?:\d+\.\s*)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}|\b[A-Z]{2,}(?:\s+[A-Z]{2,}){1,3}\b)', name_part)
                    if n_match:
                        name_str = n_match.group(1).strip()
                        if not any(h in name_str.lower() for h in ["resume", "curriculum", "page", "objective", "skills", "experience", "education"]):
                            return f"### 📌 Extracted Answer\n\n• **(Page {pg})**: **Candidate Name**: {name_str}"

    return "No match found."

docs = [sample_doc1, sample_doc2, sample_doc3]
print("Q1: 'what is phone number' ->", smart_answer(docs, "what is phone number"))
print("Q2: 'what is candidate name' ->", smart_answer(docs, "what is candidate name"))
print("Q3: 'what is email' ->", smart_answer(docs, "what is email"))
print("Q4: 'what is github' ->", smart_answer(docs, "what is github"))
