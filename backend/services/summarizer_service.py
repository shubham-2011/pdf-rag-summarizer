from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from services.llm_service import LLMService
import config

class SummarizerService:
    """PDF Map-Reduce summarizer and roadmap generator service with fallback."""
    
    @staticmethod
    def generate_summary(chunks: List[Document], api_key: str = None, model_name: str = None) -> str:
        key = api_key or config.OPENAI_API_KEY
        model = model_name or config.DEFAULT_MODEL
        
        # Filter out raw image metadata placeholders for summary text generation so only actual document text is summarized
        text_chunks = [c for c in chunks if c.metadata.get("content_type") != "image_figure" and not c.page_content.startswith("[Picture/Figure")]
        
        # Fallback to all chunks if document contains only images
        chunks_to_summarize = text_chunks if text_chunks else chunks
        
        # Attempt LLM synthesis (Gemini or OpenAI)
        llm = LLMService.get_synthesis_model(api_key=api_key, temperature=0.0) or LLMService.get_chat_model(api_key=api_key, model_name=model_name, temperature=0.0)
        
        if llm:
            try:
                map_prompt = ChatPromptTemplate.from_messages([
                    ("system", "Summarize the key points of the following document section concisely:"),
                    ("human", "{text}")
                ])
                map_chain = map_prompt | llm | StrOutputParser()
                
                chunk_summaries = []
                for chunk in chunks_to_summarize[:12]:
                    summary = map_chain.invoke({"text": chunk.page_content})
                    chunk_summaries.append(str(summary).strip())
                    
                combined_summaries = "\n\n".join(chunk_summaries)
                
                reduce_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are an expert technical analyst and executive briefing specialist."),
                    ("human", (
                        "Based on the following document section summaries:\n\n"
                        "{text}\n\n"
                        "Generate a clear, beautifully structured report formatted in Markdown with two main sections:\n\n"
                        "### EXECUTIVE SUMMARY\n"
                        "Provide a high-level summary of the document, core objectives, and major takeaways.\n\n"
                        "### STEP-BY-STEP ROADMAP & ACTION PLAN\n"
                        "Create a chronological, phased learning or implementation roadmap based on the document contents."
                    ))
                ])
                reduce_chain = reduce_prompt | llm | StrOutputParser()
                return reduce_chain.invoke({"text": combined_summaries})
            except Exception as e:
                print(f"[SummarizerService] LLM synthesis error: {e}. Using extractive fallback.")


        # Zero-Config Extractive Summary Fallback (Uses text chunks only)
        doc_text_snippets = [c.page_content[:250].strip() for c in chunks_to_summarize[:6]]
        summary_bullets = "\n".join([f"- {s}..." for s in doc_text_snippets])
        
        roadmap_phases = "\n".join([
            f"{i+1}. **Phase {i+1}**: {chunk.page_content[:140].strip()}..."
            for i, chunk in enumerate(chunks_to_summarize[:5])
        ])
        
        return f"""### EXECUTIVE SUMMARY (Extractive Fallback)
The document contains {len(text_chunks)} text passages across key topics. Key sections include:

{summary_bullets}

---

### STEP-BY-STEP ROADMAP & ACTION PLAN
{roadmap_phases}

> Note: Paste a valid OpenAI API key in the top bar to unlock full LLM synthesis.
"""
