import sys
import os
sys.path.insert(0, r"d:\Program\Projects\pdf-rag-summarizer\backend")
import config
from services.llm_service import LLMService
from services.rag_service import RAGService

print("GEMINI_KEY:", config.GEMINI_API_KEY[:10] if config.GEMINI_API_KEY else "None")
print("GEMINI_MODEL:", config.GEMINI_MODEL)

llm = LLMService.get_chat_model()
print("LLM instance:", llm)
try:
    res = llm.invoke("Hi, who are you? Say hello in 5 words.")
    print("LLM Response:", res)
except Exception as e:
    print("LLM invoke error:", type(e), e)

# Test RAG query on resume document
res_rag = RAGService.query(document_id="757636a1", question="What skills are listed in the document?")
print("RAG query answer:", res_rag.get("answer"))
print("Served by:", res_rag.get("served_by"))
