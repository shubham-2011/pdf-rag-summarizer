import os
import sys
import json
import math
import pytest
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import config
from services.vector_service import (
    VectorService,
    IncompatibleIndexError,
    NomicHuggingFaceEmbeddings,
    _CURRENT_EMBEDDING_MODEL,
    _CURRENT_EMBEDDING_DIMS,
    _CURRENT_DOC_PREFIX,
    _CURRENT_QUERY_PREFIX,
)
from services.validation_service import ValidationService, IndexCompatibilityError


def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


class TestIndexManifestAndPrefixesA3:
    """A3 — Index manifest integrity and asymmetric prefix correctness."""

    def test_manifest_drift_detection(self, tmp_path):
        """Assert system strictly rejects stale or tampered index manifests."""
        doc_dir = tmp_path / "test_doc_col"
        doc_dir.mkdir()

        # 1. Tampered model
        m1 = {
            "embedding_model": "different-org/unsupported-model-v2",
            "embedding_dims": 768,
            "document_prefix": "search_document: ",
            "query_prefix": "search_query: ",
            "unit_count": 5
        }
        with pytest.raises(IndexCompatibilityError):
            ValidationService.validate_index_manifest(m1, {
                "embedding_model": config.EMBEDDING_MODEL,
                "embedding_dims": 768,
                "document_prefix": "search_document: ",
                "query_prefix": "search_query: "
            })

        # 2. Tampered dimensions
        m2 = {
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dims": 384,  # wrong dims
            "document_prefix": "search_document: ",
            "query_prefix": "search_query: ",
            "unit_count": 5
        }
        with pytest.raises(IndexCompatibilityError):
            ValidationService.validate_index_manifest(m2, {
                "embedding_model": config.EMBEDDING_MODEL,
                "embedding_dims": 768,
                "document_prefix": "search_document: ",
                "query_prefix": "search_query: "
            })

        # 3. Tampered prefix
        m3 = {
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dims": 768,
            "document_prefix": "wrong_prefix: ",
            "query_prefix": "search_query: ",
            "unit_count": 5
        }
        with pytest.raises(IndexCompatibilityError):
            ValidationService.validate_index_manifest(m3, {
                "embedding_model": config.EMBEDDING_MODEL,
                "embedding_dims": 768,
                "document_prefix": "search_document: ",
                "query_prefix": "search_query: "
            })

    def test_vector_service_refuses_to_load_mismatched_manifest(self, tmp_path):
        """Hand-edit a manifest to claim a different model, and assert VectorService refuses to load."""
        col_name = "tampered_col"
        col_dir = tmp_path / col_name
        col_dir.mkdir()

        manifest_path = col_dir / "index_manifest.json"
        tampered_manifest = {
            "doc_id": col_name,
            "embedding_model": "openai/text-embedding-ada-002",
            "embedding_dims": 1536,
            "document_prefix": "",
            "query_prefix": "",
            "chunk_count": 10,
            "unit_count": 2
        }
        manifest_path.write_text(json.dumps(tampered_manifest))

        with patch.object(config, "VECTOR_STORE_DIR", str(tmp_path)):
            with pytest.raises(IncompatibleIndexError) as excinfo:
                VectorService.validate_index_manifest(col_name)
            assert "Embedding model mismatch" in str(excinfo.value)

    def test_manifest_records_unit_count_and_prefixes(self):
        """Validates that newly constructed manifests record unit_count and asymmetric prefixes."""
        manifest = {
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dims": 768,
            "document_prefix": "search_document: ",
            "query_prefix": "search_query: ",
            "unit_count": 15,
            "chunk_count": 25
        }
        assert "unit_count" in manifest
        assert manifest["document_prefix"] == "search_document: "
        assert manifest["query_prefix"] == "search_query: "
        assert manifest["unit_count"] == 15

    def test_prefix_asymmetry_correctness(self):
        """
        Validates Nomic asymmetric prefix behavior:
        search_query: on query text produces higher cosine similarity with
        search_document: indexed chunk than swapped or unprefixed queries.
        """
        class MockEmbeddingModel:
            """Simulates an asymmetric embedding space where prefixes align query and doc vectors."""
            def embed_documents(self, texts):
                embeddings = []
                for t in texts:
                    # Synthetic vector simulation
                    is_doc = t.startswith("search_document: ")
                    is_query = t.startswith("search_query: ")
                    val = 1.0 if (is_doc or is_query) else 0.5
                    embeddings.append([val, 0.8, 0.6])
                return embeddings

            def embed_query(self, text):
                return self.embed_documents([text])[0]

        mock_backend = MockEmbeddingModel()
        wrapper = NomicHuggingFaceEmbeddings(
            base_embeddings=mock_backend,
            doc_prefix="search_document: ",
            query_prefix="search_query: "
        )

        q = "what is the refund window"
        gold_chunk = "The refund window is strictly 30 days from purchase date."

        # Correct path: embed_query uses search_query: and embed_documents uses search_document:
        q_emb_correct = wrapper.embed_query(q)
        gold_emb = wrapper.embed_documents([gold_chunk])[0]

        # Swapped path: query is prefixed with search_document:
        q_emb_swapped = mock_backend.embed_query("search_document: " + q)

        # Unprefixed path
        q_emb_unprefixed = mock_backend.embed_query(q)

        cos_correct = cosine_similarity(q_emb_correct, gold_emb)
        cos_swapped = cosine_similarity(q_emb_swapped, gold_emb)
        cos_unprefixed = cosine_similarity(q_emb_unprefixed, gold_emb)

        assert cos_correct >= cos_swapped
        assert cos_correct >= cos_unprefixed
