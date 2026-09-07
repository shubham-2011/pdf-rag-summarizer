import os
from typing import Optional, Any, Dict, List, Union
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import config

class LLMService:
    """
    Unified LLM provider service supporting Google Gemini and OpenAI
    with automatic provider routing and zero-downtime extractive fallback.
    """
    
    @staticmethod
    def get_chat_model(
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.0
    ) -> Optional[BaseChatModel]:
        """
        Instantiates and returns the configured ChatModel.
        Prefers Google Gemini (gemini-1.5-flash / gemini-2.0-flash) when GEMINI_API_KEY is available.
        """
        gemini_key = (
            api_key if (api_key and (api_key.startswith("AIza") or api_key.startswith("AQ.") or "gemini" in (model_name or "").lower()))
            else os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or getattr(config, "GEMINI_API_KEY", "")
        )
        
        openai_key = (
            api_key if (api_key and api_key.startswith("sk-"))
            else os.getenv("OPENAI_API_KEY") or getattr(config, "OPENAI_API_KEY", "")
        )
        if openai_key == "your_openai_api_key_here":
            openai_key = ""

        # Route 1: Google Gemini (Valid Google AI Studio keys start with 'AIza' or 'AQ.')
        if gemini_key and (gemini_key.startswith("AIza") or gemini_key.startswith("AQ.")):
            chosen_model = model_name if (model_name and "gemini" in model_name.lower()) else getattr(config, "GEMINI_MODEL", "gemini-3.5-flash-lite")
            if chosen_model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]:
                chosen_model = "gemini-3.5-flash-lite"
            try:
                return ChatGoogleGenerativeAI(
                    model=chosen_model,
                    google_api_key=gemini_key,
                    temperature=temperature,
                    timeout=25,
                    max_retries=3
                )
            except Exception as e:
                print(f"[LLMService] Gemini model initialization error with {chosen_model}: {e}")
                # Fallback to gemini-3.5-flash-lite
                try:
                    return ChatGoogleGenerativeAI(
                        model="gemini-3.5-flash-lite",
                        google_api_key=gemini_key,
                        temperature=temperature,
                        timeout=25,
                        max_retries=3
                    )
                except Exception as e2:
                    print(f"[LLMService] Gemini fallback model error: {e2}")

        # Route 2: OpenAI (Valid OpenAI keys start with 'sk-')
        if openai_key and openai_key.startswith("sk-") and len(openai_key) > 20:
            chosen_model = model_name if (model_name and "gpt" in model_name.lower()) else "gpt-4o-mini"
            try:
                return ChatOpenAI(
                    model=chosen_model,
                    openai_api_key=openai_key,
                    temperature=temperature,
                    request_timeout=15,
                    max_retries=2
                )
            except Exception as e:
                print(f"[LLMService] OpenAI model initialization error: {e}")

        # Route 3: Explicit API key fallback
        if api_key and not gemini_key and not openai_key:
            try:
                if "gemini" in (model_name or "").lower():
                    return ChatGoogleGenerativeAI(
                        model=model_name or "gemini-3.5-flash-lite",
                        google_api_key=api_key,
                        temperature=temperature,
                        timeout=25,
                        max_retries=3
                    )
                else:
                    return ChatOpenAI(
                        model=model_name or "gpt-4o-mini",
                        openai_api_key=api_key,
                        temperature=temperature,
                        request_timeout=15,
                        max_retries=2
                    )
            except Exception as e:
                print(f"[LLMService] Fallback LLM initialization error: {e}")

        return None

    @classmethod
    def get_fast_model(cls, api_key: Optional[str] = None, temperature: float = 0.0) -> Optional[BaseChatModel]:
        """Returns the fast/small tier model configured for classification, routing, and scoring (Temp 0.0)."""
        fast_model_name = getattr(config, "LLM_FAST_MODEL", "gemini-3.5-flash-lite")
        return cls.get_chat_model(api_key=api_key, model_name=fast_model_name, temperature=temperature)

    @classmethod
    def get_synthesis_model(cls, api_key: Optional[str] = None, temperature: float = 0.2) -> Optional[BaseChatModel]:
        """Returns the synthesis/large tier model configured for answer generation and revision (Temp 0.2)."""
        synthesis_model_name = getattr(config, "LLM_SYNTHESIS_MODEL", "gemini-3.5-flash-lite")
        return cls.get_chat_model(api_key=api_key, model_name=synthesis_model_name, temperature=temperature)

    @classmethod
    def invoke_prompt_with_fallback(
        cls,
        prompt: ChatPromptTemplate,
        input_vars: Dict[str, Any],
        api_key: Optional[str] = None,
        preferred_model: Optional[str] = None,
        temperature: float = 0.0
    ) -> Optional[str]:
        """
        Executes prompt across a resilient candidate model ladder.
        Automatically falls back if a model throws 429 RESOURCE_EXHAUSTED or 404 NOT_FOUND.
        """
        from langchain_core.output_parsers import StrOutputParser
        candidate_models = []
        if preferred_model:
            candidate_models.append(preferred_model)
        for m in ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gpt-4o-mini"]:
            if m not in candidate_models:
                candidate_models.append(m)

        for m_name in candidate_models:
            model = cls.get_chat_model(api_key=api_key, model_name=m_name, temperature=temperature)
            if not model:
                continue
            try:
                chain = prompt | model | StrOutputParser()
                output = chain.invoke(input_vars)
                if output and output.strip():
                    return output.strip()
            except Exception as e:
                print(f"[LLMService] Invocation error with {m_name}: {e}. Trying next model in ladder...")
                continue
        return None

    @staticmethod
    def extract_json(raw_text: str) -> Optional[Any]:
        """
        Robustly extracts and parses a JSON object or array from LLM output,
        handling markdown code fences, leading/trailing text, and unicode quirks.
        """
        if not raw_text or not isinstance(raw_text, str):
            return None
            
        cleaned = raw_text.strip()
        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
            
        import json
        try:
            return json.loads(cleaned)
        except Exception:
            # Attempt to find innermost or first { ... } or [ ... ]
            import re
            match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return None

    @classmethod
    def verify_models(cls) -> Dict[str, Any]:
        """Verifies configured LLM providers and connectivity."""
        model = cls.get_chat_model()
        status = {
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", "")),
            "openai_configured": bool(os.getenv("OPENAI_API_KEY") or getattr(config, "OPENAI_API_KEY", "")),
            "active_model": type(model).__name__ if model else "None (Offline Extractive Fallback)"
        }
        print(f"[LLMService] Verification: {status}")
        return status

def get_llm_service():
    """Factory helper returning LLMService."""
    return LLMService

