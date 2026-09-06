import os
import sys
import unittest

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(repo_root, "backend")
tests_dir = os.path.join(repo_root, "tests")

for p in [repo_root, backend_dir, tests_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.metadata_service import MetadataService
from services.rag_service import RAGService
from services.query_understanding_service import QueryUnderstandingService

TEST_DOCX_ID = "test_docx_defect_doc"

def setup_test_docx_registry():
    """Sets up a registered test DOCX document in SQLite registry with 4 sections."""
    MetadataService.init_db()
    
    # Register document with NULL unit_count and unit_kind='section'
    MetadataService.register_document(
        doc_id=TEST_DOCX_ID,
        content_hash="test_docx_hash_123",
        filename="B_28_Final_Water_Potability_ML_Model_Assignment_Shubham_Kumar (1).docx",
        format_ext="docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=45000,
        unit_count=None,
        unit_kind="section",
        storage_path="storage/uploads/test.docx",
        status="READY"
    )
    
    MetadataService.save_identity(TEST_DOCX_ID, {
        "title": "Water Potability Prediction Using Machine Learning Models",
        "doc_type": "Academic Research Paper / Technical Project Report",
        "domain": "Environmental Engineering & Machine Learning",
        "purpose": "Evaluate and compare multiple machine learning algorithms for classifying drinking water potability based on physicochemical metrics.",
        "key_entities": ["pH", "Hardness", "Solids", "Chloramines", "Sulfate", "Conductivity", "Random Forest", "XGBoost"],
        "authors": "Shubham Kumar",
        "doc_date": "2026",
        "structure_outline": [
            "1. Introduction & Problem Statement",
            "2. Dataset Exploration & Preprocessing",
            "3. Model Training & Hyperparameter Tuning",
            "4. Comparative Evaluation & Conclusions"
        ]
    })
    
    MetadataService.save_outline(TEST_DOCX_ID, [
        {"heading": "1. Introduction & Problem Statement", "locator_kind": "section", "locator_index": 1, "char_count": 1200},
        {"heading": "2. Dataset Exploration & Preprocessing", "locator_kind": "section", "locator_index": 2, "char_count": 2400},
        {"heading": "3. Model Training & Hyperparameter Tuning", "locator_kind": "section", "locator_index": 3, "char_count": 3100},
        {"heading": "4. Comparative Evaluation & Conclusions", "locator_kind": "section", "locator_index": 4, "char_count": 1800}
    ])


class TestDefect1(unittest.TestCase):
    """Defect 1: unit_count fabricated for DOCX and wrong structural/locational answers."""

    def test_defect_1_docx_registry_unit_count_is_none(self):
        setup_test_docx_registry()
        doc = MetadataService.get_document(TEST_DOCX_ID)
        self.assertIsNotNone(doc)
        self.assertIsNone(doc["unit_count"], f"Expected unit_count to be None, got {doc['unit_count']}")
        self.assertEqual(doc["unit_kind"], "section", f"Expected unit_kind to be 'section', got {doc['unit_kind']}")
        
        struct = MetadataService.get_structural_summary(TEST_DOCX_ID)
        self.assertGreaterEqual(struct["section_count"], 4, f"Expected section_count >= 4, got {struct['section_count']}")

    def test_defect_1_structural_page_query_on_docx_explains_sections(self):
        setup_test_docx_registry()
        res = RAGService.query(document_id=TEST_DOCX_ID, question="how many pages in this pdf")
        ans = res["answer"].lower()
        
        self.assertEqual(res["strategy"], "registry_metadata", f"Expected strategy registry_metadata, got {res.get('strategy')}")
        self.assertEqual(len(res["sources"]), 0, "Structural query must attach 0 citations/retrieval chunks")
        
        self.assertTrue("word" in ans or "not have fixed pages" in ans or "sections" in ans, f"Answer did not explain pagination: {ans}")
        self.assertTrue("4" in ans or "section" in ans, f"Answer did not mention sections: {ans}")
        self.assertNotIn("this document has 1 page", ans)

    def test_defect_1_locational_page_query_on_docx_explains_sections(self):
        setup_test_docx_registry()
        res = RAGService.query(document_id=TEST_DOCX_ID, question="what is written in second page")
        ans = res["answer"].lower()
        
        self.assertNotIn("this specific information is not mentioned or found", ans)
        self.assertTrue("page" in ans and ("section" in ans or "word" in ans or "fixed page" in ans or "does not have fixed pages" in ans), f"Did not explain pages/sections: {ans}")


class TestDefect2(unittest.TestCase):
    """Defect 2: GLOBAL path ignores identity card and fails on ungrammatical queries."""

    GLOBAL_QUERIES = [
        "tell me main topic about this document why it is exist",
        "analyse document and give me answer",
        "tell me something about this document",
        "what is this document about",
        "give me an overview of this document",
        "summarize this document",
        "what is the aim of this project",
        "explain what this document covers",
        "what is this file doing"
    ]

    def test_defect_2_classifier_routes_all_global_phrasings_to_global(self):
        for query in self.GLOBAL_QUERIES:
            with self.subTest(query=query):
                understanding = QueryUnderstandingService.process(query)
                self.assertEqual(
                    understanding["intent"],
                    "GLOBAL",
                    f"Query '{query}' classified as '{understanding['intent']}' instead of GLOBAL"
                )

    def test_defect_2_global_path_synthesizes_from_identity(self):
        setup_test_docx_registry()
        query = "tell me main topic about this document why it is exist"
        res = RAGService.query(document_id=TEST_DOCX_ID, question=query)
        ans = res["answer"]
        ans_lower = ans.lower()
        
        self.assertIn(res.get("strategy"), ["zero_config_global_synopsis", "llm_global_synthesis", "registry_synopsis"], f"Unexpected strategy: {res.get('strategy')}")
        self.assertNotIn("not mentioned or found in the uploaded document", ans_lower)
        
        words = ans.split()
        self.assertGreaterEqual(len(words), 25, f"Expected answer length >= 25 words, got {len(words)}")
        self.assertTrue(any(k in ans_lower for k in ["water potability", "machine learning", "potability", "environmental"]), f"Missing key domain facts: {ans}")
        self.assertNotIn("• (1):", ans)
        self.assertNotIn("(page 1):", ans_lower)


class TestDefect3(unittest.TestCase):
    """Defect 3: Page count discrepancy & fallback hardcoding bug (defaulting to 15)."""

    def test_defect_3_registered_page_counts_match_chunks(self):
        """Ensures all registered test document unit counts reflect their actual page count."""
        test_cases = [
            ("eval_electrical_layout_drawing", 1),
            ("eval_adversarial_injection", 1),
            ("757636a1", 2),
            ("eval_water_quality_report", 3),
            ("eval_technical_manual_long", 15)
        ]
        for doc_id, expected_pages in test_cases:
            with self.subTest(doc_id=doc_id):
                struct = MetadataService.get_structural_summary(doc_id)
                self.assertEqual(
                    struct.get("unit_count"),
                    expected_pages,
                    f"Document {doc_id} expected {expected_pages} pages, got {struct.get('unit_count')}"
                )

    def test_defect_3_page_count_query_answers_accurately(self):
        """Ensures structural page count queries return exact page counts and grammar."""
        test_cases = [
            ("eval_electrical_layout_drawing", "This document contains exactly 1 page."),
            ("757636a1", "This document contains exactly 2 pages."),
            ("eval_water_quality_report", "This document contains exactly 3 pages."),
            ("eval_technical_manual_long", "This document contains exactly 15 pages."),
            (TEST_DOCX_ID, "This is a DOCX document, which has no fixed page numbers. It contains 4 sections.")
        ]
        for doc_id, expected_ans in test_cases:
            with self.subTest(doc_id=doc_id):
                res = QueryUnderstandingService.classify_and_route("how many pages does this document have", doc_id=doc_id)
                self.assertEqual(
                    res.get("direct_answer"),
                    expected_ans,
                    f"Query on {doc_id} returned '{res.get('direct_answer')}', expected '{expected_ans}'"
                )

    def test_defect_3_auto_discovery_for_unregistered_collection(self):
        """Ensures auto-discovery dynamically recovers unit_count from chunks without defaulting to 15."""
        struct = MetadataService.get_structural_summary("eval_electrical_layout_drawing")
        self.assertIsNotNone(struct)
        self.assertEqual(struct.get("unit_count"), 1)
        self.assertNotEqual(struct.get("unit_count"), 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)

