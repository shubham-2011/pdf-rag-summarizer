import sys
import os
import time

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.llm_service import LLMService

print("Testing LLMService.get_chat_model()...")
t0 = time.time()
llm = LLMService.get_chat_model()
print(f"Model: {llm}")
try:
    res = llm.invoke("What is 2+2? Answer in one word.")
    print(f"Response ({time.time()-t0:.2f}s): {res}")
except Exception as e:
    print(f"Error ({time.time()-t0:.2f}s): {e}")
