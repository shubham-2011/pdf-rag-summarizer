import requests
import json
import os
import sys

BASE_URL = "https://3-18-112-83.sslip.io/api"

print(f"=== TESTING LIVE BACKEND AT {BASE_URL} ===")

# 1. Health Endpoint
print("\n[1] Testing GET /health...")
resp = requests.get(f"{BASE_URL}/health", timeout=30)
print(f"Status: {resp.status_code}, Body: {resp.text}")
assert resp.status_code == 200, f"Health check failed: {resp.text}"

# 2. Upload Document
print("\n[2] Testing POST /pdf/upload...")
# Let's find a test file from audit/fixtures or tests/
fixture_pdf = "audit/fixtures/canary_test.pdf"
if not os.path.exists(fixture_pdf):
    # generate a small test pdf or find an existing pdf
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".pdf"):
                fixture_pdf = os.path.join(root, f)
                break
        if fixture_pdf != "audit/fixtures/canary_test.pdf":
            break

print(f"Uploading file: {fixture_pdf}")
with open(fixture_pdf, "rb") as f:
    files = {"file": (os.path.basename(fixture_pdf), f, "application/pdf")}
    upload_resp = requests.post(f"{BASE_URL}/pdf/upload", files=files, timeout=60)

print(f"Upload Status: {upload_resp.status_code}")
print(f"Upload Response: {upload_resp.text[:300]}...")
assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"

upload_data = upload_resp.json()
doc_id = upload_data.get("document_id")
print(f"Uploaded Doc ID: {doc_id}")
print(f"Unit count: {upload_data.get('unit_count')} {upload_data.get('unit_name')}")
print(f"Document Purpose: {upload_data.get('one_line_purpose')}")

# 3. Dossier Endpoint
print(f"\n[3] Testing GET /pdf/dossier/{doc_id}...")
dossier_resp = requests.get(f"{BASE_URL}/pdf/dossier/{doc_id}", timeout=10)
print(f"Dossier Status: {dossier_resp.status_code}")
if dossier_resp.status_code == 200:
    print(f"Dossier Title: {dossier_resp.json().get('title')}")
    print(f"Dossier Summary Preview: {str(dossier_resp.json().get('executive_summary'))[:100]}...")

# 4. Summarize Endpoint
print(f"\n[4] Testing POST /pdf/summarize...")
sum_resp = requests.post(f"{BASE_URL}/pdf/summarize", json={"document_id": doc_id}, timeout=60)
print(f"Summarize Status: {sum_resp.status_code}")
if sum_resp.status_code == 200:
    sum_data = sum_resp.json()
    print(f"Roadmap Summary Keys: {list(sum_data.keys())}")
    print(f"Executive Summary preview: {str(sum_data.get('summary', ''))[:150]}...")

# 5. Chat Query Endpoints - Test all query types
print(f"\n[5] Testing POST /chat/query...")

queries = [
    ("Greeting Query", "Hello! Who are you?"),
    ("Meta Query", "How many pages does this document contain?"),
    ("Global Purpose Query", "What is the primary purpose and objective of this document?"),
    ("Content Query", "What are the main topics and key points discussed in this document?")
]

for label, question in queries:
    print(f"\n--- {label}: '{question}' ---")
    chat_payload = {
        "document_id": doc_id,
        "question": question
    }
    chat_resp = requests.post(f"{BASE_URL}/chat/query", json=chat_payload, timeout=60)
    print(f"Chat Query Status: {chat_resp.status_code}")
    if chat_resp.status_code == 200:
        chat_data = chat_resp.json()
        print(f"Served By: {chat_data.get('served_by')}")
        print(f"Latency: {chat_data.get('latency_ms')} ms")
        print(f"Sources: {chat_data.get('sources')}")
        print(f"Answer:\n{chat_data.get('answer')}\n")
    else:
        print(f"Error: {chat_resp.text}")

print("\n=== ALL APIS AND QUERY RESPONSES TESTED ON LIVE AWS BACKEND ===")
