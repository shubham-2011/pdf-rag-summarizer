import os
import sys
sys.path.insert(0, r"d:\Program\Projects\pdf-rag-summarizer\backend")
import config
from langchain_google_genai import ChatGoogleGenerativeAI

models_to_test = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-1.5-pro"]

key = config.GEMINI_API_KEY
print("Testing with key:", key[:10])

for m in models_to_test:
    print(f"\n--- Testing model: {m} ---")
    try:
        chat = ChatGoogleGenerativeAI(model=m, google_api_key=key, temperature=0.0)
        res = chat.invoke("Say 'model working' in exactly two words.")
        print(f"SUCCESS with {m}:", res.content)
    except Exception as e:
        print(f"FAILED with {m}:", e)
