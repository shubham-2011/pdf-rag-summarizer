import requests
import json

url = "http://localhost:8000/api/chat/query"
payload = {
    "document_id": "757636a1",
    "question": "What is the candidate's name, education, and technical skills?",
    "model_name": "gemini-3.6-flash",
    "enable_web_search": False,
    "chat_history": []
}

resp = requests.post(url, json=payload)
print("Status:", resp.status_code)
data = resp.json()
print("Answer:\n", data.get("answer"))
print("\nServed by:", data.get("served_by"))
print("\nSources count:", len(data.get("sources", [])))
for s in data.get("sources", []):
    print(" - Source page:", s.get("page"), "| Section:", s.get("section"))
