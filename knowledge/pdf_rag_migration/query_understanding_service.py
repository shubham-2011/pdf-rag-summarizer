import re
from typing import Dict, Any, List, Optional, Tuple

TYPO_CORRECTIONS = {
    "wat": "what",
    "wht": "what",
    "abt": "about",
    "abou": "about",
    "sumarize": "summarize",
    "summarise": "summarize",
    "sumary": "summary",
    "overiew": "overview",
    "documnt": "document",
    "docmnt": "document",
    "papre": "paper",
    "drawin": "drawing",
    "transfomer": "transformer",
    "accurcy": "accuracy",
    "paramters": "parameters",
    "clasification": "classification",
    "predct": "predict",
    "algoritm": "algorithm",
    "substn": "substation",
    "diagrm": "diagram",
    "voltge": "voltage",
    "repot": "report",
    "experiance": "experience",
    "tecnical": "technical",
    "eduction": "education"
}

GREETING_PATTERNS = [
    r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|howdy|hola|namaste|sup|yo)(\s+(there|assistant|bot|ai|friend|team))?[\s!.,?]*$",
    r"^(who\s+are\s+you|what\s+is\s+your\s+name|introduce\s+yourself)[\s!.,?]*$",
    r"^(hi|hello|hey)\s+(there|assistant|bot|ai)[\s!.,?]*$"
]

CAPABILITY_PATTERNS = [
    r"what\s+can\s+you\s+do",
    r"how\s+can\s+you\s+help",
    r"what\s+can\s+i\s+ask",
    r"what\s+questions\s+can\s+i\s+ask",
    r"what\s+are\s+your\s+capabilities",
    r"help\s+me\s+with\s+this\s+document",
    r"what\s+features\s+do\s+you\s+have"
]

META_PATTERNS = [
    r"what\s+is\s+(the\s+)?(file\s*name|filename|document\s*name)",
    r"how\s+many\s+pages",
    r"how\s+many\s+slides",
    r"how\s+many\s+sheets",
    r"what\s+type\s+of\s+file",
    r"what\s+is\s+(the\s+)?format",
    r"when\s+was\s+this\s+(uploaded|created)",
    r"who\s+(created|authored|wrote|uploaded)\s+this",
    r"metadata\s+of\s+this"
]

GLOBAL_PATTERNS = [
    r"what\s+is\s+(this\s+|the\s+)?(document|pdf|file|paper|drawing|presentation|sheet|case\s+study|report)\s+(about|for)",
    r"what\s+is\s+(this\s+|the\s+)?(document|pdf|file|paper|drawing|presentation|sheet)\s+doing",
    r"what\s+is\s+pdf\s+works\s+for",
    r"what\s+is\s+(this\s+|the\s+)?about",
    r"what\s+is\s+(this\s+|the\s+)?(document|pdf|file|drawing)",
    r"summarize\s+(this\s+|the\s+)?(document|pdf|file|paper|drawing|entire\s+pdf|all)",
    r"give\s+(me\s+)?(a\s+)?(summary|overview|executive\s+summary)",
    r"overview\s+of\s+(this\s+|the\s+)?(document|pdf|file)",
    r"explain\s+(this\s+|the\s+)?(document|pdf|file)",
    r"what\s+(does|do)\s+this\s+(document|pdf|file)\s+(do|cover|contain)",
    r"main\s+sections|structure\s+of\s+(the|this)\s+(document|pdf)",
    r"purpose\s+of\s+(this\s+|the\s+)?(document|pdf|project|drawing)"
]

TABULAR_PATTERNS = [
    r"show\s+table",
    r"compare\s+(the\s+)?(rows|columns|values)",
    r"what\s+are\s+the\s+(figures|numbers|metrics)\s+in\s+table",
    r"spreadsheet\s+data",
    r"sheet\s+columns"
]

OUT_OF_SCOPE_PATTERNS = [
    r"weather\s+in",
    r"who\s+won\s+(the\s+)?(\d{4}\s+)?(world\s+cup|super\s+bowl|match|election|championship|tournament)",
    r"how\s+to\s+bake",
    r"recipe\s+for",
    r"capital\s+of",
    r"tell\s+me\s+a\s+(joke|story|poem)",
    r"write\s+a\s+(poem|song|story)\s+about",
    r"who\s+is\s+the\s+president\s+of"
]

class QueryUnderstandingService:
    """Enterprise Query Understanding: Normalization, 7-Intent Classification, and Query Expansion."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Corrects common typos, expands abbreviations, and removes excessive whitespace."""
        if not text:
            return ""
            
        words = text.split()
        normalized_words = []
        for word in words:
            # Strip punctuation for lookup
            clean_w = re.sub(r'^[^\w]+|[^\w]+$', '', word).lower()
            if clean_w in TYPO_CORRECTIONS:
                fixed = TYPO_CORRECTIONS[clean_w]
                # Preserve capitalization
                if word.isupper():
                    fixed = fixed.upper()
                elif word.istitle():
                    fixed = fixed.title()
                normalized_words.append(word.lower().replace(clean_w, fixed))
            else:
                normalized_words.append(word)
                
        return " ".join(normalized_words)

    @staticmethod
    def resolve_pronouns_and_context(query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Rewrites ambiguous follow-up queries with pronoun references using previous turn history."""
        if not chat_history or len(chat_history) == 0:
            return query

        last_turn = chat_history[-1]
        last_user = last_turn.get("user", last_turn.get("content", ""))
        
        q_lower = query.lower().strip()
        pronouns = [" it", " its", " they", " their", " them", " that", " this", " those", " these", " he", " she", " his", " her"]
        has_pronoun = any(p in f" {q_lower} " for p in pronouns) or q_lower.startswith(("and ", "what about", "how about", "where is it", "why is it", "its ", "their "))
        
        if has_pronoun and last_user:
            stopwords = {"what", "how", "where", "why", "when", "which", "is", "are", "the", "this", "that", "about", "tell", "show", "find", "document", "pdf"}
            prev_tokens = [w for w in re.findall(r'\b\w+\b', last_user) if w.lower() not in stopwords and len(w) > 2]
            if prev_tokens:
                subject = " ".join(prev_tokens[:3])
                return f"{query} (referring to {subject})"

        return query

    @classmethod
    def classify_intent(cls, query: str, identity_card: Optional[Dict[str, Any]] = None) -> str:
        """
        Classifies user query into one of 7 distinct taxonomy intents:
        - GREETING: Conversational greetings
        - CAPABILITY: Questions about what the assistant can do
        - META: Questions about document metadata (pages, filename, author, format)
        - GLOBAL: Document purpose, executive summary, high-level overview
        - TABULAR: Structured table and spreadsheet inquiries
        - OUT_OF_SCOPE: General knowledge completely unrelated to document
        - LOCAL: Default grounded factual retrieval
        """
        q_clean = query.strip().lower()
        
        # 1. 💬 GREETING
        for pattern in GREETING_PATTERNS:
            if re.search(pattern, q_clean):
                return "GREETING"

        # 2. ⚡ CAPABILITY
        for pattern in CAPABILITY_PATTERNS:
            if re.search(pattern, q_clean):
                return "CAPABILITY"

        # 3. 🪪 META (Metadata)
        for pattern in META_PATTERNS:
            if re.search(pattern, q_clean):
                return "META"

        # 4. 🌐 GLOBAL (Purpose, Summary, Overview)
        for pattern in GLOBAL_PATTERNS:
            if re.search(pattern, q_clean):
                return "GLOBAL"

        # Catch single-word summaries or short global queries
        if q_clean in ["summary", "summarize", "overview", "gist", "what is this", "what is this document", "what is this pdf"]:
            return "GLOBAL"

        # 5. 📊 TABULAR
        for pattern in TABULAR_PATTERNS:
            if re.search(pattern, q_clean):
                return "TABULAR"

        # 6. 🚫 OUT_OF_SCOPE
        for pattern in OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, q_clean):
                return "OUT_OF_SCOPE"

        # 7. 🎯 LOCAL (Default factual retrieval)
        return "LOCAL"

    @classmethod
    def expand_query_for_retrieval(cls, query: str, identity_card: Optional[Dict[str, Any]] = None) -> str:
        """Appends domain-specific synonyms and entity anchors to boost sparse BM25 recall."""
        if not identity_card:
            return query

        expanded = query
        key_entities = identity_card.get("key_entities", [])
        domain = identity_card.get("domain", "")
        q_lower = query.lower()

        # Add domain expansions if relevant concepts are queried
        if "accuracy" in q_lower or "performance" in q_lower or "model" in q_lower:
            if "Environmental" in domain or "Machine Learning" in domain:
                expanded += " WQI machine learning algorithms prediction evaluation"
        elif "transformer" in q_lower or "rating" in q_lower or "substation" in q_lower:
            if "Electrical" in domain:
                expanded += " Single Line Diagram MVA kV voltage busbar"
        elif "skill" in q_lower or "experience" in q_lower:
            if "Portfolio" in domain:
                expanded += " technical competencies programming technologies projects"

        return expanded

    @classmethod
    def process(
        cls,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        identity_card: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Full pipeline: normalizes text, resolves pronouns, classifies intent, and expands BM25 query."""
        normalized = cls.normalize_text(query)
        contextualized = cls.resolve_pronouns_and_context(normalized, chat_history)
        intent = cls.classify_intent(contextualized, identity_card)
        retrieval_query = cls.expand_query_for_retrieval(contextualized, identity_card)

        return {
            "original_query": query,
            "normalized_query": normalized,
            "contextualized_query": contextualized,
            "retrieval_query": retrieval_query,
            "intent": intent
        }
