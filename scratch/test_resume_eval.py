import requests

questions = [
    "What is the candidate's name, education, and technical skills?",
    "What projects and work experience are listed in the resume?",
    "Tell me about the Tipco Engineering internship.",
    "What is the Product Management System project and what technologies were used?",
    "Does the document mention any work experience at Microsoft or Google?"
]

url = "http://localhost:8000/api/chat/query"

for q in questions:
    print(f"\n==================================================")
    print(f"QUERY: {q}")
    payload = {
        "document_id": "757636a1",
        "question": q,
        "model_name": "gemini-3.5-flash-lite",
        "enable_web_search": False,
        "chat_history": []
    }
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        print(f"ANSWER:\n{data.get('answer')}")
        print(f"SERVED BY: {data.get('served_by')}")
        print(f"LATENCY: {data.get('latency_ms')}ms")
    else:
        print(f"ERROR ({resp.status_code}): {resp.text}")
