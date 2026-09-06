"""
tests/test_index_manifest.py
============================
Unit tests for VectorService index manifest save/validate round-trip.
Covers:
  - Missing manifest → IncompatibleIndexError
  - Embedding model mismatch → IncompatibleIndexError
  - Embedding dimension mismatch → IncompatibleIndexError
  - Document prefix mismatch → IncompatibleIndexError
  - Query prefix mismatch → IncompatibleIndexError
  - Happy-path round-trip (save then validate succeeds)
"""

import json
import os
import pytest
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Ensure the backend package is importable regardless of where pytest is run.
# ---------------------------------------------------------------------------
import sys

_BACKEND = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from services.vector_service import (
    VectorService,
    IncompatibleIndexError,
    _CURRENT_EMBEDDING_MODEL,
    _CURRENT_EMBEDDING_DIMS,
    _CURRENT_DOC_PREFIX,
    _CURRENT_QUERY_PREFIX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_manifest(index_dir: str, overrides: dict) -> None:
    """Write a minimal manifest, applying *overrides* on top of valid defaults."""
    os.makedirs(index_dir, exist_ok=True)
    manifest = {
        "doc_id": os.path.basename(index_dir),
        "embedding_model": _CURRENT_EMBEDDING_MODEL,
        "embedding_dims": _CURRENT_EMBEDDING_DIMS,
        "document_prefix": _CURRENT_DOC_PREFIX,
        "query_prefix": _CURRENT_QUERY_PREFIX,
        "normalized": True,
        "chunk_count": 10,
        "bm25_indexed": True,
    }
    manifest.update(overrides)
    with open(os.path.join(index_dir, "index_manifest.json"), "w") as f:
        json.dump(manifest, f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidateIndexManifest:
    """Tests for VectorService.validate_index_manifest."""

    def _index_dir(self, tmp_path, name):
        return os.path.join(str(tmp_path), name)

    def _patch_store_dir(self, tmp_path):
        import config as cfg
        return patch.object(cfg, "VECTOR_STORE_DIR", str(tmp_path))

    # --- missing manifest --------------------------------------------------

    def test_missing_manifest_raises(self, tmp_path):
        """No index_manifest.json -> IncompatibleIndexError."""
        name = "no_manifest_col"
        os.makedirs(os.path.join(str(tmp_path), name), exist_ok=True)
        with self._patch_store_dir(tmp_path):
            with pytest.raises(IncompatibleIndexError, match="Missing index_manifest"):
                VectorService.validate_index_manifest(name)

    # --- model mismatch ----------------------------------------------------

    def test_model_mismatch_raises(self, tmp_path):
        """Different embedding_model -> IncompatibleIndexError."""
        name = "model_mismatch_col"
        index_dir = self._index_dir(tmp_path, name)
        _write_manifest(index_dir, {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"})
        with self._patch_store_dir(tmp_path):
            with pytest.raises(IncompatibleIndexError, match="Embedding model mismatch"):
                VectorService.validate_index_manifest(name)

    # --- dimension mismatch ------------------------------------------------

    def test_dimension_mismatch_raises(self, tmp_path):
        """Different embedding_dims -> IncompatibleIndexError."""
        name = "dim_mismatch_col"
        index_dir = self._index_dir(tmp_path, name)
        _write_manifest(index_dir, {"embedding_dims": 384})  # Nomic is 768
        with self._patch_store_dir(tmp_path):
            with pytest.raises(IncompatibleIndexError, match="Embedding dimension mismatch"):
                VectorService.validate_index_manifest(name)

    # --- document prefix mismatch ------------------------------------------

    def test_doc_prefix_mismatch_raises(self, tmp_path):
        """Wrong document prefix -> IncompatibleIndexError."""
        name = "doc_prefix_col"
        index_dir = self._index_dir(tmp_path, name)
        _write_manifest(index_dir, {"document_prefix": ""})  # missing prefix
        with self._patch_store_dir(tmp_path):
            with pytest.raises(IncompatibleIndexError, match="Asymmetric prefix mismatch"):
                VectorService.validate_index_manifest(name)

    # --- query prefix mismatch ---------------------------------------------

    def test_query_prefix_mismatch_raises(self, tmp_path):
        """Wrong query prefix -> IncompatibleIndexError."""
        name = "query_prefix_col"
        index_dir = self._index_dir(tmp_path, name)
        _write_manifest(index_dir, {"query_prefix": "query: "})
        with self._patch_store_dir(tmp_path):
            with pytest.raises(IncompatibleIndexError, match="Asymmetric prefix mismatch"):
                VectorService.validate_index_manifest(name)

    # --- corrupt JSON ------------------------------------------------------

    def test_corrupt_manifest_raises(self, tmp_path):
        """Corrupt JSON -> IncompatibleIndexError wrapping the parse error."""
        name = "corrupt_col"
        index_dir = self._index_dir(tmp_path, name)
        os.makedirs(index_dir, exist_ok=True)
        with open(os.path.join(index_dir, "index_manifest.json"), "w") as f:
            f.write("{ this is not valid json }")
        with self._patch_store_dir(tmp_path):
            with pytest.raises(IncompatibleIndexError, match="Corrupt index_manifest"):
                VectorService.validate_index_manifest(name)

    # --- happy path --------------------------------------------------------

    def test_valid_manifest_returns_dict(self, tmp_path):
        """A correctly written manifest passes validation and returns its contents."""
        name = "valid_col"
        index_dir = self._index_dir(tmp_path, name)
        _write_manifest(index_dir, {})  # no overrides -> all defaults valid
        with self._patch_store_dir(tmp_path):
            result = VectorService.validate_index_manifest(name)
        assert result["embedding_model"] == _CURRENT_EMBEDDING_MODEL
        assert result["embedding_dims"] == _CURRENT_EMBEDDING_DIMS
        assert result["document_prefix"] == _CURRENT_DOC_PREFIX
        assert result["query_prefix"] == _CURRENT_QUERY_PREFIX

    # --- save + validate round-trip ----------------------------------------

    def test_save_then_validate_round_trip(self, tmp_path):
        """save_index_manifest output must pass validate_index_manifest unchanged."""
        name = "roundtrip_col"
        with self._patch_store_dir(tmp_path):
            VectorService.save_index_manifest(name, chunk_count=42)
            result = VectorService.validate_index_manifest(name)
        assert result["chunk_count"] == 42
        assert result["bm25_indexed"] is True
        assert result["normalized"] is True
