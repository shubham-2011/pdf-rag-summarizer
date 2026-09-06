import sys
import os
import re
sys.path.insert(0, os.path.abspath("backend"))

from langchain_core.documents import Document

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing",
    "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in",
    "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll",
    "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves", "tell", "show", "give", "find"
}

def extract_smart_sentences_improved(docs, question: str):
    q_lower = question.lower().strip()
    q_tokens = [w for w in re.findall(r'\b\w+\b', q_lower) if w not in STOPWORDS and len(w) > 1]
    
    is_name_query = any(k in q_lower for k in ["name", "who", "candidate", "author", "person", "whose", "applicant"])
    is_contact_query = any(k in q_lower for k in ["contact", "phone", "mobile", "email", "address", "call", "reach", "github", "linkedin"])
    is_table_query = any(k in q_lower for k in ["table", "column", "row", "financial", "grid"])
    is_action_query = any(k in q_lower for k in ["action", "item", "items", "owner", "owns", "roadmap", "task", "tasks", "deliverable"])
    is_number_query = any(k in q_lower for k in ["number", "numbers", "figure", "figures", "monetary", "date", "dates", "amount", "budget", "cost", "revenue"])
    is_general_summary_request = any(k in q_lower for k in ["summarize", "summary", "bullet", "points", "overview", "executive", "brief"])
    
    scored_sentences = []
    seen = set()
    
    # Pre-pass for candidate / author name identification on Page 1
    extracted_name = None
    if is_name_query:
        for doc in docs:
            pg = str(doc.metadata.get("page_label", doc.metadata.get("page", "1")))
            if pg in ["1", "0"] or doc.metadata.get("is_header"):
                lines = [l.strip() for l in doc.page_content.split('\n') if l.strip()]
                for l in lines[:4]:
                    l_clean = re.sub(r'^[•\-\*\d\.\s]+', '', l).strip()
                    l_lower = l_clean.lower()
                    words = [w for w in l_clean.split() if w.isalpha()]
                    if (
                        1 <= len(words) <= 4 and
                        all(w.isupper() or w.istitle() for w in words) and
                        not any(h in l_lower for h in ["resume", "curriculum", "page", "http", "objective", "profile", "summary", "skills", "experience", "education", "projects"]) and
                        "@" not in l_clean and
                        not re.search(r'\d', l_clean) and
                        ":" not in l_clean
                    ):
                        extracted_name = (pg, l_clean)
                        break
            if extracted_name:
                break

    if is_name_query and extracted_name:
        scored_sentences.append((extracted_name[0], f"**Candidate Name**: {extracted_name[1]}", 200.0))
        seen.add(extracted_name[1])

    for doc_idx, doc in enumerate(docs):
        pg = str(doc.metadata.get("page_label", doc.metadata.get("page", "1")))
        sec = doc.metadata.get("section_heading", "GENERAL").upper()
        content = doc.page_content
        
        # Split lines cleanly
        raw_units = [u.strip() for u in re.split(r'(?:\r?\n)+|(?<=[.!?])\s+(?=[A-Z0-9])', content) if len(u.strip()) > 3]
        
        for line_idx, unit in enumerate(raw_units):
            unit_clean = unit.strip()
            if not unit_clean or unit_clean in seen:
                continue
                
            u_lower = unit_clean.lower()
            score = 0.0
            
            # If asking specifically for a person's name, suppress work experience / technical task bullets
            if is_name_query:
                if any(v in u_lower for v in ["developed", "maintained", "optimized", "collaborated", "managed", "implemented", "designed", "created"]):
                    continue
                if re.search(r'\d{4}', unit_clean): # Date like 2024
                    continue
                if any(label in u_lower for label in ["name:", "candidate name:", "author:", "presented by:", "by:"]):
                    score += 50.0

            # Table query
            if is_table_query:
                if "|" in unit_clean or any(sym in unit_clean for sym in ["$", "%", "USD", "Total", "Revenue", "Growth"]):
                    score += 25.0

            # Action query
            if is_action_query:
                if any(a_term in u_lower for a_term in ["owner:", "due date:", "budget:", "action item", "action items"]):
                    score += 35.0

            # Numerical query
            if is_number_query:
                if re.search(r'\$[\d,]+|\d+(?:\.\d+)?%|\b20\d{2}\b', unit_clean):
                    score += 30.0

            # Token overlap
            for q_tok in q_tokens:
                if q_tok in u_lower:
                    score += 5.0
                    if re.search(r'\b' + re.escape(q_tok) + r'\b', u_lower):
                        score += 10.0
                        
            if score > 0:
                seen.add(unit_clean)
                scored_sentences.append((pg, unit_clean, score))
                
    scored_sentences.sort(key=lambda x: x[2], reverse=True)
    return scored_sentences

# Test with resume
resume_chunk_page1 = Document(
    page_content="""SHUBHAM KUMAR
Full Stack Software Developer
Email: shubham@example.com | Phone: +91-9876543210 | Bangalore, India
Languages: Java, Python, JavaScript, TypeScript""",
    metadata={"page": 0, "page_label": 1, "section_heading": "DOCUMENT_HEADER", "is_header": True}
)

resume_chunk_page2 = Document(
    page_content="""EXPERIENCE
Software Engineer at Acme Corp (Feb 2024 – Nov 2024)
• Developed and maintained web application features using Angular and Spring Boot.
• Optimized Oracle DB queries, improving application performance by 20%.""",
    metadata={"page": 1, "page_label": 2, "section_heading": "EXPERIENCE"}
)

res = extract_smart_sentences_improved([resume_chunk_page2, resume_chunk_page1], "what is candidate name")
print("Extracted Results:")
for pg, text, score in res:
    print(f"  [Score {score:.1f}] (Page {pg}): {text}")
