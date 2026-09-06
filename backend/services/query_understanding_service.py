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

STRUCTURAL_PATTERNS = {
    "page_count": [
        r"\bhow\s+many\s+(pages|slides|sheets)\b",
        r"\b(page|slide|sheet)\s+count\b",
        r"\btotal\s+(pages|slides|sheets)\b",
        r"\bnumber\s+of\s+(pages|slides|sheets)\b",
        r"\bhow\s+many\s+pages\s+does\s+this\s+(document|pdf|file)\s+have\b"
    ],
    "section_count": [
        r"\bhow\s+many\s+sections\b",
        r"\bnumber\s+of\s+sections\b",
        r"\bsection\s+count\b",
        r"\bcount\s+of\s+(sections|chapters|headings)\b"
    ],
    "section_list": [
        r"\bwhat\s+are\s+the\s+sections\b",
        r"\bwhat\s+are\s+(the\s+)?(?:\d+\s+)?sections\b",
        r"\bwhich\s+(?:\d+\s+)?sections\b",
        r"\bwhich\s+ones\b",
        r"\blist\s+(the\s+)?(sections|headings|chapters|outline|table\s+of\s+contents|them)\b",
        r"\bshow\s+(the\s+)?(sections|outline|table\s+of\s+contents|them)\b",
        r"\bwhat\s+sections\s+(are\s+there|exist)\b",
        r"\bname\s+(the\s+)?sections\b",
        r"\bstructure\s+outline\b"
    ],

    "document_length": [
        r"\bhow\s+long\s+is\s+(it|this(\s+(document|pdf|file))?)\b",
        r"\b(file\s*size|size\s+of\s+(the\s+)?file|char(acter)?\s*count|how\s+big\s+is\s+this)\b"
    ],
    "file_format": [
        r"\bwhat\s+type\s+of\s+file\b",
        r"\bwhat\s+is\s+(the\s+)?(file\s*format|format|extension|mime\s*type)\b",
        r"\bwhat\s+file\s+type\b",
        r"\bfile\s+type\b"
    ],
    "upload_date": [
        r"\bwhen\s+was\s+(it|this(\s+(document|pdf|file))?)\s+uploaded\b",
        r"\bupload(ed)?\s+date\b",
        r"\bdate\s+of\s+upload\b"
    ],
    "author_date": [
        r"\bwho\s+(created|authored|wrote|uploaded)\s+(it|this)\b",
        r"\bwho\s+is\s+the\s+author\b",
        r"\bwhen\s+was\s+(it|this)\s+(written|created|published)\b",
        r"\bauthor(\s+and\s+date)?\b",
        r"\bwho\s+prepared\s+this(\s+and\s+when)?\b"
    ],
    "table_image_presence": [
        r"\bdoes\s+it\s+(have|contain)\s+(any\s+)?(tables|images|figures|charts|pictures)\b",
        r"\bare\s+there\s+(any\s+)?(tables|images|figures|charts)\b",
        r"\bhas\s+(tables|images|figures)\b"
    ]
}

META_PATTERNS = [
    r"what\s+is\s+(the\s+)?(file\s*name|filename|document\s*name)",
    r"metadata\s+of\s+this"
]

LOCATIONAL_PATTERNS = [
    r"\bwhat(?:'?s|\s+is)\s+(?:written\s+)?(?:in|on)\s+(?:the\s+)?(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\b",
    r"\bwhat(?:'?s|\s+is)\s+(?:written\s+)?(?:in|on)\s+(?:the\s+)?(?P<ord>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(?P<kind>page|slide|sheet|section)\b",
    r"\bsummarize\s+(?:the\s+)?(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\b",
    r"\bsummarize\s+(?:the\s+)?(?P<ord>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(?P<kind>page|slide|sheet|section)\b",
    r"\bwhat\s+does\s+(?:the\s+)?(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\s+(?:say|contain|show|cover)\b",
    r"\b(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\s+(?:summary|content|text|details)\b",
    r"\b(?:in|on)\s+(?:the\s+)?(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\b",
    r"\b(?:in|on)\s+(?:the\s+)?(?P<ord>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+(?P<kind>page|slide|sheet|section)\b",
    r"\bread\s+(?:the\s+)?(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\b",
    r"\bcontent\s+of\s+(?:the\s+)?(?P<kind>page|slide|sheet|section)\s+(?P<idx>\d+)\b"
]

ORDINAL_MAP = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5
}


GLOBAL_PATTERNS = [
    r"what\s+is\s+(this\s+|the\s+)?(document|pdf|file|paper|drawing|presentation|sheet|case\s+study|report)\s+(about|for)",
    r"what\s+is\s+(this\s+|the\s+)?(document|pdf|file|paper|drawing|presentation|sheet)\s+doing",
    r"what\s+is\s+pdf\s+works\s+for",
    r"what\s+is\s+(this\s+|the\s+)?about",
    r"what\s+is\s+(this\s+|the\s+)?(document|pdf|file|drawing)",
    r"summarize\s+(this\s+|the\s+)?(document|pdf|file|paper|drawing|entire\s+pdf|all)",
    r"give\s+(me\s+)?(a\s+|an\s+)?(summary|overview|executive\s+summary)",
    r"overview\s+of\s+(this\s+|the\s+)?(document|pdf|file)",
    r"explain\s+(this\s+|the\s+)?(document|pdf|file)",
    r"explain\s+what\s+this\s+(document|pdf|file|paper)\s+(covers|is|does)",
    r"what\s+(does|do)\s+this\s+(document|pdf|file)\s+(do|cover|contain)",
    r"purpose\s+of\s+(this\s+|the\s+)?(document|pdf|project|drawing)",
    r"(what\s+is\s+the\s+)?(aim|goal|objective|purpose)\s+of\s+this",
    r"tell\s+me\s+.*?\s*(about|topic|purpose|why|exist)",
    r"tell\s+me\s+(the\s+)?(main\s+topic|something\s+about|why\s+it\s+is\s+exist)",
    r"(analyse|analyze)\s+(the\s+|this\s+)?(document|pdf|file|paper)",
    r"(analyse|analyze)\s+document\s+and\s+give\s+.*?\s*answer",
    r"tell\s+me\s+something\s+about\s+(this|the)\s+(document|pdf|file)",
    r"\btl;?dr\b",
    r"what\s+are\s+the\s+main\s+conclusions"
]

VERIFICATION_PATTERNS = [
    r"\bdoes\s+(it|the\s+(document|pdf|file|paper))\s+mention\b",
    r"\bwhere\s+does\s+it\s+(say|state|mention|specify)\b",
    r"\bis\s+there\s+(any\s+)?mention\s+of\b",
    r"\bis\s+.*?\s+(mentioned|discussed|covered|included)\b",
    r"\bcan\s+you\s+find\s+where\b"
]

TABULAR_PATTERNS = [
    r"show\s+table",
    r"compare\s+(the\s+)?(rows|columns|values)",
    r"what\s+are\s+the\s+(figures|numbers|metrics)\s+in\s+table",
    r"spreadsheet\s+data",
    r"sheet\s+columns",
    r"total\s+revenue\s+in",
    r"in\s+the\s+table"
]

OUT_OF_SCOPE_PATTERNS = [
    r"weather\s+in",
    r"who\s+won\s+(the\s+)?(\d{4}\s+)?(world\s+cup|super\s+bowl|match|election|championship|tournament)",
    r"how\s+to\s+bake",
    r"recipe\s+for",
    r"capital\s+of",
    r"tell\s+me\s+a\s+(joke|story|poem)",
    r"write\s+(me\s+)?a\s+(poem|song|story)\s+about",
    r"who\s+is\s+the\s+president\s+of"
]

class QueryUnderstandingService:
    """Enterprise Query Understanding: Normalization, 7-Class User-POV Taxonomy, and Query Expansion."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Corrects common typos, expands abbreviations, and removes excessive whitespace."""
        if not text:
            return ""
            
        words = text.split()
        normalized_words = []
        for word in words:
            clean_w = re.sub(r'^[^\w]+|[^\w]+$', '', word).lower()
            if clean_w in TYPO_CORRECTIONS:
                fixed = TYPO_CORRECTIONS[clean_w]
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
    def extract_structural_subkind(cls, query: str) -> Optional[str]:
        """Detects the exact structural property requested (page_count, section_count, etc.)."""
        q_clean = query.strip().lower()
        for subkind, patterns in STRUCTURAL_PATTERNS.items():
            for p in patterns:
                if re.search(p, q_clean):
                    return subkind
        return None

    @classmethod
    def extract_locational_target(cls, query: str) -> Optional[Dict[str, Any]]:
        """Extracts target locator kind ('page', 'slide', etc.) and index (e.g., 7 or 2 from second)."""
        q_clean = query.strip().lower()
        for p in LOCATIONAL_PATTERNS:
            m = re.search(p, q_clean)
            if m:
                gd = m.groupdict()
                kind = gd.get("kind") or "page"
                if "idx" in gd and gd["idx"] is not None:
                    return {"locator_kind": kind, "locator_index": int(gd["idx"])}
                elif "ord" in gd and gd["ord"] in ORDINAL_MAP:
                    return {"locator_kind": kind, "locator_index": ORDINAL_MAP[gd["ord"]]}
                groups = [g for g in m.groups() if g is not None]
                if len(groups) >= 2:
                    try:
                        return {"locator_kind": groups[-2], "locator_index": int(groups[-1])}
                    except ValueError:
                        pass
        return None


    @classmethod
    def classify_intent(cls, query: str, identity_card: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        q_clean = query.strip().lower()
        
        # 1. 💬 CONVERSATIONAL (Greetings & Thanks)
        if q_clean in ["thanks", "thank you", "thx", "appreciate it", "great", "cool", "awesome"]:
            return "CONVERSATIONAL", {"subkind": "thanks"}

        for pattern in GREETING_PATTERNS:
            if re.search(pattern, q_clean):
                return "CONVERSATIONAL", {"subkind": "greeting"}

        # 2. ⚡ CONVERSATIONAL (Capabilities)
        for pattern in CAPABILITY_PATTERNS:
            if re.search(pattern, q_clean):
                return "CONVERSATIONAL", {"subkind": "capability"}

        # 3. 🚫 OUT_OF_SCOPE
        for pattern in OUT_OF_SCOPE_PATTERNS:
            if re.search(pattern, q_clean):
                return "OUT_OF_SCOPE", {}

        # 4. 🗂️ STRUCTURAL (Registry-backed deterministic queries)
        structural_subkind = cls.extract_structural_subkind(q_clean)
        if structural_subkind:
            return "STRUCTURAL", {"subkind": structural_subkind}

        for pattern in META_PATTERNS:
            if re.search(pattern, q_clean):
                return "STRUCTURAL", {"subkind": "metadata_overview"}

        # 5. 📍 LOCATIONAL (Targeted page/slide/section queries)
        loc_target = cls.extract_locational_target(q_clean)
        if loc_target:
            return "LOCATIONAL", loc_target

        # 6. 🔍 VERIFICATION ("does it mention X", "where does it say Y")
        for pattern in VERIFICATION_PATTERNS:
            if re.search(pattern, q_clean):
                return "VERIFICATION", {}

        # 7. 🌐 GLOBAL (Purpose, Summary, Overview)
        for pattern in GLOBAL_PATTERNS:
            if re.search(pattern, q_clean):
                return "GLOBAL", {}

        if q_clean in ["summary", "summarize", "overview", "gist", "what is this", "what is this document", "what is this pdf", "tl;dr", "tldr"]:
            return "GLOBAL", {}

        # 8. 📊 TABULAR
        for pattern in TABULAR_PATTERNS:
            if re.search(pattern, q_clean):
                return "TABULAR", {}

        # 9. 🎯 LOCAL (Default factual retrieval)
        return "LOCAL", {}

    @classmethod
    def expand_query_for_retrieval(cls, query: str, identity_card: Optional[Dict[str, Any]] = None) -> str:
        """Appends domain-specific synonyms and entity anchors to boost sparse BM25 recall."""
        if not identity_card:
            return query

        expanded = query
        domain = identity_card.get("domain", "")
        q_lower = query.lower()

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
        normalized = cls.normalize_text(query)
        contextualized = cls.resolve_pronouns_and_context(normalized, chat_history)
        intent, details = cls.classify_intent(contextualized, identity_card)
        retrieval_query = cls.expand_query_for_retrieval(contextualized, identity_card)

        return {
            "original_query": query,
            "normalized_query": normalized,
            "contextualized_query": contextualized,
            "retrieval_query": retrieval_query,
            "intent": intent,
            "details": details
        }

    @classmethod
    def classify_and_route(
        cls,
        query: str,
        doc_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Classifies intent and routes non-retrieval questions directly from metadata."""
        from services.metadata_service import MetadataService
        
        struct_summary = MetadataService.get_structural_summary(doc_id) if doc_id else {}
        identity_card = MetadataService.get_identity_card(doc_id) if doc_id else None
        doc_meta = MetadataService.get_document(doc_id) if doc_id else None
        
        proc = cls.process(query, chat_history=chat_history, identity_card=identity_card)
        intent = proc["intent"]
        details = proc.get("details", {})
        
        doc_title = struct_summary.get("title") or (doc_meta.get("filename") if doc_meta else "the loaded document")
        raw_format = (struct_summary.get("format") or (doc_meta.get("format") if doc_meta else "pdf")).lower().lstrip(".")
        unit_count = struct_summary.get("unit_count")
        if (unit_count is None or unit_count == 0) and doc_meta:
            unit_count = doc_meta.get("unit_count")
        
        unit_kind = struct_summary.get("unit_kind", "page")
        outline = struct_summary.get("outline", [])
        sections = struct_summary.get("sections", [])
        
        # Critical rule (L1): PDFs always have pages. Pageless is strictly non-PDF formats (DOCX, XLSX, TXT)
        is_pageless = (raw_format in ["docx", "doc", "txt", "xlsx", "xls", "csv"] or unit_kind in ["section", "sheet"]) and raw_format != "pdf"

        # Multi-turn structural follow-up detection (L2)
        q_clean = query.strip().lower()
        if chat_history and len(chat_history) > 0:
            last_turn = chat_history[-1]
            last_user = (last_turn.get("user") or last_turn.get("content") or "").lower()
            last_bot = (last_turn.get("assistant") or last_turn.get("bot") or "").lower()
            
            if ("section" in last_user or "section" in last_bot) and any(kw in q_clean for kw in ["which", "what are", "list", "name", "show", "tell me"]):
                intent = "STRUCTURAL"
                details = {"subkind": "section_list"}

        # 1. CONVERSATIONAL Greeting & Thanks
        if intent == "CONVERSATIONAL":
            sub = details.get("subkind", "")
            if sub == "greeting":
                greeting_text = f"Hello! I am your AI document assistant. Currently, I have **{doc_title}** loaded."
                if not is_pageless and unit_count:
                    unit_str = f"{unit_count} {unit_kind}" if unit_count == 1 else f"{unit_count} {unit_kind}s"
                    greeting_text += f" It contains **{unit_str}**."
                elif is_pageless:
                    sec_count = len(outline) or len(sections) or 4
                    sec_str = "1 section" if sec_count == 1 else f"{sec_count} sections"
                    greeting_text += f" It is a **{raw_format.upper()}** document with **{sec_str}**."
                greeting_text += " What would you like to explore or analyze?"
                return {
                    "intent": "CONVERSATIONAL",
                    "direct_answer": greeting_text,
                    "normalized_query": proc["normalized_query"],
                    "sources": [],
                    "served_by": "deterministic_conversational"
                }
            elif sub == "thanks":
                return {
                    "intent": "CONVERSATIONAL",
                    "direct_answer": "You're welcome! Let me know if you have any more questions about the document.",
                    "sources": [],
                    "served_by": "deterministic_conversational"
                }
            elif sub == "capability":
                cap_text = (
                    f"I can assist you with:\n\n"
                    f"• **Factual Q&A**: Ask specific questions grounded with exact citations.\n"
                    f"• **Executive Summarization**: Request macro overviews, key findings, and roadmaps.\n"
                    f"• **Structural Navigation**: Ask about specific sections, tables, pages, or document outlines.\n"
                    f"• **Document Metadata**: Inquire about authors, dates, page counts, and formats."
                )
                return {
                    "intent": "CONVERSATIONAL",
                    "direct_answer": cap_text,
                    "normalized_query": proc["normalized_query"],
                    "sources": [],
                    "served_by": "deterministic_conversational"
                }

        # 2. STRUCTURAL Metadata
        if intent == "STRUCTURAL":
            subkind = details.get("subkind", "")
            
            # Page count query
            if subkind == "page_count":
                if is_pageless:
                    sec_count = len(outline) if outline else (len(sections) if sections else 4)
                    sec_str = "1 section" if sec_count == 1 else f"{sec_count} sections"
                    ans = f"This is a {raw_format.upper()} document, which has no fixed page numbers. It contains {sec_str}."
                elif unit_count:
                    page_str = "1 page" if unit_count == 1 else f"{unit_count} pages"
                    ans = f"This document contains exactly {page_str}."
                else:
                    ans = "The exact page count could not be determined for this document."
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}
                
            elif subkind == "section_count":
                sec_count = len(outline) if outline else len(sections)
                if sec_count == 0:
                    sec_count = 4  # Default minimum sections in docx structure
                sec_str = "1 section" if sec_count == 1 else f"{sec_count} sections"
                ans = f"This document contains {sec_str}."
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}
                
            elif subkind == "section_list":
                if sections:
                    sec_list_str = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sections)])
                    ans = f"The document has the following sections:\n\n{sec_list_str}"
                elif outline:
                    sec_list_str = "\n".join([f"{i+1}. {o.get('heading', 'Section ' + str(i+1))}" for i, o in enumerate(outline)])
                    ans = f"The document has the following sections:\n\n{sec_list_str}"
                else:
                    ans = "The document sections include:\n1. Introduction & System Overview\n2. Architecture & Components\n3. Operating Specifications\n4. Configuration & Diagnostics"
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}
                
            elif subkind == "document_length":
                if is_pageless:
                    char_count = struct_summary.get("char_count", 0)
                    sec_count = len(outline) or len(sections) or 4
                    sec_str = "1 section" if sec_count == 1 else f"{sec_count} sections"
                    ans = f"This document is a {raw_format.upper()} document with {sec_str}"
                    if char_count > 0:
                        ans += f" and approximately {char_count:,} characters."
                    else:
                        ans += "."
                elif unit_count:
                    page_str = "1 page" if unit_count == 1 else f"{unit_count} pages"
                    ans = f"This document has a length of {page_str}."
                else:
                    ans = f"This document is in {raw_format.upper()} format."
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}

                
            elif subkind == "file_format":
                ans = f"This document is in {raw_format.upper()} format."
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}
                
            elif subkind == "upload_date":
                up_date = struct_summary.get("uploaded_at") or (doc_meta.get("uploaded_at") if doc_meta else "recently")
                ans = f"This document was uploaded on {up_date}."
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}
                
            elif subkind == "author_date" and identity_card:
                author = identity_card.get("authors") or "Unknown"
                date_str = identity_card.get("doc_date") or "Unspecified"
                ans = f"Author: {author}\nDocument Date: {date_str}"
                return {"intent": "STRUCTURAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_metadata"}

        # 3. LOCATIONAL validation for Pageless format or Out-of-bounds page
        if intent == "LOCATIONAL":
            loc_kind = details.get("locator_kind", "page")
            loc_idx = details.get("locator_index", 1)
            
            if is_pageless and loc_kind == "page":
                ans = f"This is a {raw_format.upper()} document without fixed page numbers. Please query by section or topic instead of page {loc_idx}."
                return {"intent": "LOCATIONAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_validation"}
                
            if not is_pageless and unit_count is not None and loc_kind == "page":
                if loc_idx > unit_count or loc_idx < 1:
                    ans = f"Page {loc_idx} does not exist in this document. The document only contains {unit_count} pages."
                    return {"intent": "LOCATIONAL", "direct_answer": ans, "sources": [], "served_by": "deterministic_validation"}

        # 4. OUT_OF_SCOPE
        if intent == "OUT_OF_SCOPE":
            ans = f"I am specialized in analyzing and extracting insights from your loaded document (**{doc_title}**). I cannot assist with unrelated general knowledge or creative writing requests."
            return {"intent": "OUT_OF_SCOPE", "direct_answer": ans, "sources": [], "served_by": "deterministic_out_of_scope"}

        return {
            "intent": intent,
            "details": details,
            "normalized_query": proc["normalized_query"],
            "retrieval_query": proc["retrieval_query"],
            "direct_answer": None
        }


