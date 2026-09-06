import os
import sys
sys.path.insert(0, r"d:\Program\Projects\pdf-rag-summarizer\backend")
import config
from google import genai

key = config.GEMINI_API_KEY
client = genai.Client(api_key=key)

for m in ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-flash-latest"]:
    print(f"Testing {m}...")
    try:
        r = client.models.generate_content(model=m, contents="Reply with 'OK'")
        print(f"-> {m} SUCCESS: {r.text}")
    except Exception as e:
        print(f"-> {m} ERROR: {e}")
