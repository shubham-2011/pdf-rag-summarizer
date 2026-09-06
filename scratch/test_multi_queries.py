import requests
import json

questions = [
    "What projects and work experience are listed?",
    "Tell me about the Tipco Engineering internship.",
    "What is the Product Management System project and what technologies were used?",
    "What is the candidate's contact information?",
    "Does the document mention any experience at Google?"
]

url = "http://localhost:8000/api/chat/query"

for q in questions:
    print(f"\n==================================================")
    print(f"QUESTION: {q}")
    payload = {
        "document_id": "757636a1",
        "question": q,
        "model_name": "gemini-3.6-flash",
        "enable_web_search": False,
        "chat_history": []
    }
    resp = requests.post(url, json=payload)
    if resp.status_code == 200:
        data = resp.json()
        print(f"ANSWER:\n{data.get('answer')}")
        print(f"SERVED BY: {data.get('served_by')}")
        print(f"SOURCES: {len(data.get('sources', []))} citations")
    else:
        print(f"ERROR ({resp.status_code}): {resp.text}")
