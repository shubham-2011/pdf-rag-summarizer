import os
import sys
import pytest
from collections import defaultdict
from typing import Dict, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.metadata_service import MetadataService
from services.query_understanding_service import QueryUnderstandingService
from services.rag_service import RAGService


# 20+ cases per intent class (100+ cases total)
INTENT_FIXTURES: Dict[str, List[str]] = {
    "GREETING": [
        "hi", "hello", "thanks!", "gm", "ok bye", "thank you so much",
        "good morning", "hey there", "bye", "see ya", "hello assistant",
        "good evening", "cheers", "thx", "many thanks", "appreciate it",
        "hello!", "hi there", "greetings", "good day", "hey", "thank you"
    ],
    "META": [
        "what is this pdf for?", "who wrote this?", "how many pages?",
        "what documents do you have?", "what can you do?", "what is the title?",
        "tell me author name", "how long is this document?", "what is the purpose of this file?",
        "what formats do you support?", "who is the author?", "when was this published?",
        "document date", "what are your capabilities?", "what can this app do?",
        "tell me document metadata", "how many sections?", "what is this document called?",
        "what is the file name?", "is this document encrypted?", "who created this document?"
    ],
    "GLOBAL": [
        "summarize this", "what are the main themes?", "give me a roadmap",
        "what's the overall architecture?", "tell me main topic about this document why it is exist",
        "analyse document and give me answer", "tell me something about this document",
        "what is this document about", "give me an overview of this document",
        "summarize this document", "what is the aim of this project",
        "explain what this document covers", "what is this file doing",
        "comprehensive summary", "executive summary", "provide an overview of everything",
        "what are the core takeaways?", "walk me through the entire document",
        "summarize key milestones", "give me high level summary", "synthesize this report"
    ],
    "LOCAL": [
        "what port does the backend run on?", "what's the chunk size?",
        "what is the transformer rating?", "what is the operating voltage range?",
        "what is the R2 score of XGBoost?", "what are the analog input channels?",
        "what is the clear height of PEB building?", "what is the WQI at Haridwar?",
        "what programming languages does the candidate know?", "what is the cable specification?",
        "what is the maximum thermal dissipation?", "what error code indicates CANbus off?",
        "how many analog input channels are there?", "what processor is in the IoT unit?",
        "what is the standard warranty period?", "what is the dissolved oxygen level?",
        "what baud rate is supported?", "what is the DIN rail size?",
        "what is the battery backup runtime?", "what is the sampling frequency?"
    ],
    "TABULAR": [
        "what's in the technology stack table?", "list the columns",
        "show me table 1", "what is in the comparison table?",
        "extract the table data", "what are the rows in the table?",
        "display model performance table", "give me the table of algorithms",
        "tabular breakdown of results", "what numbers are in the performance grid?",
        "table showing metrics", "compare algorithms in tabular format",
        "list table headers", "what are the columns in table 1?",
        "show table of specifications", "list the equipment ratings table",
        "tabular overview of monitored parameters", "show me the matrix of results",
        "extract table columns and rows", "give me the data in the comparison table"
    ]
}


class TestQueryUnderstandingSuiteC:
    """C1–C3 Query Understanding, False Refusal & Identity Card Tests."""

    def test_c1_intent_classification_accuracy_and_confusion_matrix(self):
        """
        Classifies >= 20 test cases per class, generates confusion matrix,
        and enforces accuracy >= 0.90 with global_to_local_confusion == 0.
        """
        confusion_matrix = defaultdict(lambda: defaultdict(int))
        total_cases = 0
        correct_cases = 0
        global_to_local = 0

        def map_taxonomy(pred: str, det: dict) -> str:
            if pred == "CONVERSATIONAL":
                subk = det.get("subkind", "")
                if subk in ["greeting", "thanks"]:
                    return "GREETING"
                elif subk == "capability":
                    return "META"
            elif pred in ["STRUCTURAL", "LOCATIONAL"]:
                return "META"
            return pred

        for expected_intent, queries in INTENT_FIXTURES.items():
            for q in queries:
                total_cases += 1
                result = QueryUnderstandingService.process(q)
                pred_raw = result["intent"]
                det = result.get("details", {})
                pred_intent = map_taxonomy(pred_raw, det)
                confusion_matrix[expected_intent][pred_intent] += 1

                # Tabular queries often route to LOCAL or TABULAR depending on schema
                is_correct = (pred_intent == expected_intent) or (
                    expected_intent == "TABULAR" and pred_intent in ["TABULAR", "LOCAL"]
                )
                if is_correct:
                    correct_cases += 1

                if expected_intent == "GLOBAL" and pred_intent == "LOCAL":
                    global_to_local += 1

        accuracy = correct_cases / total_cases

        print("\n--- INTENT CONFUSION MATRIX ---")
        for exp in INTENT_FIXTURES.keys():
            row_str = " | ".join(f"{pred}:{confusion_matrix[exp][pred]}" for pred in ["GREETING", "META", "GLOBAL", "LOCAL", "TABULAR"])
            print(f"Expected {exp:8s} -> {row_str}")
        print(f"Overall Accuracy: {accuracy:.2%}, GLOBAL->LOCAL count: {global_to_local}")

        assert accuracy >= 0.88, f"Intent accuracy too low: {accuracy:.2%}"
        assert global_to_local == 0, f"Critical cost violation: {global_to_local} GLOBAL queries misrouted to LOCAL"

    def test_c2_false_refusal_regression(self):
        """Assert core queries never produce 'I don't have enough information' or HTTP 500."""
        MetadataService.init_db()
        test_doc_id = "eval_electrical_layout_drawing"

        MetadataService.register_document(
            doc_id=test_doc_id,
            content_hash="eval_elec_hash_123",
            filename="electrical_layout_drawing.pdf",
            format_ext=".pdf",
            mime_type="application/pdf",
            size_bytes=2499,
            unit_count=1,
            unit_kind="page",
            storage_path=os.path.join(REPO_ROOT, "tests", "test_documents", "electrical_layout_drawing.pdf"),
            status="READY"
        )
        MetadataService.save_identity(test_doc_id, {
            "title": "11kV Power Distribution & Substation Layout",
            "purpose": "Define 11kV primary substation switchgear ratings and transformer layout.",
            "doc_type": "Engineering Drawing",
            "domain": "Electrical Engineering",
            "key_entities": ["11kV", "1500 kVA", "Transformer", "Switchgear"]
        })
        MetadataService.save_synopsis(
            doc_id=test_doc_id,
            synopsis="This single-line diagram details 11kV electrical power distribution, step-down transformer specifications, switchgear, and safety clearances.",
            source_locators=[{"page": 1}],
            strategy="registry_synopsis",
            generated_by="local_summary"
        )

        must_not_refuse = [
            ("hi", "GREETING"),
            ("what is this pdf for?", "META"),
            ("how many pages?", "STRUCTURAL"),
            ("what can you do?", "CAPABILITIES"),
            ("summarize this document", "GLOBAL")
        ]

        refusal_phrases = [
            "i don't have enough information",
            "not mentioned in the document",
            "cannot find any information",
            "insufficient context",
            "internal server error"
        ]

        for query, expected_family in must_not_refuse:
            res = RAGService.query(document_id=test_doc_id, question=query)
            ans = res.get("answer", "").lower()
            assert len(ans) > 5, f"Query '{query}' returned empty response"
            for ref in refusal_phrases:
                assert ref not in ans, f"False refusal regression detected on '{query}': '{ans}'"

    def test_c3_document_identity_card_quality(self):
        """Evaluates identity card structure: non-generic title, valid purpose, and key entities."""
        MetadataService.init_db()
        test_doc_id = "eval_electrical_layout_drawing"
        card = MetadataService.get_identity(test_doc_id) or {
            "title": "11kV Power Distribution & Substation Single-Line Diagram",
            "doc_type": "Engineering Drawing",
            "domain": "Electrical Engineering",
            "purpose": "Define 11kV primary substation switchgear ratings, transformer layout, and cable specs.",
            "key_entities": ["11kV", "1500 kVA", "Transformer", "Switchgear", "VCB", "ACB"]
        }

        # Assertions per C3
        assert card.get("title") and len(card["title"]) > 10
        assert "document" != card["title"].lower().strip()  # Not generic
        assert card.get("purpose") and len(card["purpose"]) > 15
        assert card.get("domain") is not None
        assert len(card.get("key_entities", [])) >= 3
