import sys
import os
sys.path.insert(0, r"d:\Program\Projects\pdf-rag-summarizer\backend")
import config
from google import genai

key = config.GEMINI_API_KEY
client = genai.Client(api_key=key)

print("Listing supported models:")
try:
    models = list(client.models.list())
    for m in models:
        print(f"Model: {m.name} | Display: {m.display_name}")
except Exception as e:
    print("List error:", e)

# Test 3.6-flash and 3.5-flash-lite
for test_m in ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]:
    try:
        resp = client.models.generate_content(model=test_m, contents="Say hello in 2 words")
        print(f"\nSUCCESS with {test_m}:", resp.text)
    except Exception as e:
        print(f"\nFAILED with {test_m}:", e)
