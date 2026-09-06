import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("--- 1. Health Check ---")
    try:
        res = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"Status: {res.status_code}, Response: {res.json()}")
        return res.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_pdf_upload_and_retrieval():
    print("\n--- 2. Upload and Index PDF ---")
    pdf_path = r"d:\Program\Projects\pdf-rag-summarizer\sample_ai_roadmap.pdf"
    with open(pdf_path, "rb") as f:
        files = {"file": ("sample_ai_roadmap.pdf", f, "application/pdf")}
        res = requests.post(f"{BASE_URL}/api/pdf/upload", files=files, timeout=30)
    print(f"Upload Status: {res.status_code}")
    print(f"Upload Response: {json.dumps(res.json(), indent=2)}")
    doc_id = res.json().get("document_id")

    print("\n--- 3. Test Retrieval: Exact Concept / Query 1 ---")
    t0 = time.time()
    query_payload = {
        "document_id": doc_id,
        "question": "What are the core topics and phases in this roadmap?",
        "enable_web_search": False,
        "chat_history": []
    }
    res_query = requests.post(f"{BASE_URL}/api/chat/query", json=query_payload, timeout=30)
    print(f"Query 1 Status: {res_query.status_code} (Latency: {time.time()-t0:.3f}s)")
    print(f"Query 1 Answer:\n{res_query.json().get('answer')}")
    print(f"Query 1 Sources ({len(res_query.json().get('sources', []))}):")
    for s in res_query.json().get("sources", []):
        print(f" - [Page {s.get('page')} | {s.get('file')}]: {s.get('snippet')}")

    print("\n--- 4. Test Retrieval: Multi-Turn Contextualization with Pronoun ---")
    t0 = time.time()
    history = [
        {"user": "What is Phase 1 about?", "assistant": "Phase 1 covers Foundation & Python Essentials."}
    ]
    followup_payload = {
        "document_id": doc_id,
        "question": "What tools are needed in it?",
        "enable_web_search": False,
        "chat_history": history
    }
    res_followup = requests.post(f"{BASE_URL}/api/chat/query", json=followup_payload, timeout=30)
    print(f"Follow-up Query Status: {res_followup.status_code} (Latency: {time.time()-t0:.3f}s)")
    print(f"Follow-up Answer:\n{res_followup.json().get('answer')}")
    print(f"Follow-up Sources:")
    for s in res_followup.json().get("sources", []):
        print(f" - [Page {s.get('page')} | {s.get('file')}]: {s.get('snippet')}")

    print("\n--- 5. Test Summarization Endpoint ---")
    t0 = time.time()
    sum_payload = {
        "document_id": doc_id
    }
    res_sum = requests.post(f"{BASE_URL}/api/pdf/summarize", json=sum_payload, timeout=30)
    print(f"Summarize Status: {res_sum.status_code} (Latency: {time.time()-t0:.3f}s)")
    print(f"Summary Output:\n{res_sum.json().get('summary_and_roadmap')}")

if __name__ == "__main__":
    if test_health():
        test_pdf_upload_and_retrieval()
