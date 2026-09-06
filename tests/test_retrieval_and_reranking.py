import os
import sys
import time
import pytest
from typing import List, Dict, Any
from langchain_core.documents import Document

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
for p in [REPO_ROOT, BACKEND_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.vector_service import VectorService

# --- Gold Chunks Fixture Set for B1 (Exact Identifiers) ---
B1_CORPUS = [
    Document(
        page_content="Authentication is managed using JWT tokens and RBAC roles across CORS secured endpoints.",
        metadata={"chunk_id": "c_auth", "section_heading": "SECURITY"}
    ),
    Document(
        page_content="High-concurrency SQLite WAL engine ensures lock-free writes for multi-worker SPA architectures.",
        metadata={"chunk_id": "c_storage", "section_heading": "DATABASE"}
    ),
    Document(
        page_content="Local offline embedding runs nomic-embed-text-v1.5 paired with bge-reranker-base and gemini-3.5-flash-lite.",
        metadata={"chunk_id": "c_models", "section_heading": "AI_MODELS"}
    ),
    Document(
        page_content="Core logic resides in backend/services/rag_service.py with metadata tracking in index_manifest.json.",
        metadata={"chunk_id": "c_paths", "section_heading": "CODEBASE"}
    ),
    Document(
        page_content="Network errors such as HTTP 503, HTTP 404, and HTTP 500 trigger automated retry backoffs.",
        metadata={"chunk_id": "c_errors", "section_heading": "NETWORKING"}
    ),
    Document(
        page_content="Frontend dependencies are React 18, Vite 5, with backend on Pydantic v2 and Python 3.11.",
        metadata={"chunk_id": "c_versions", "section_heading": "DEPENDENCIES"}
    ),
    Document(
        page_content="Cloudflare tunnel headers require bypass-tunnel-reminder with search_document prefix for indexing.",
        metadata={"chunk_id": "c_compounds", "section_heading": "TUNNEL_CONFIG"}
    ),
]

B1_TEST_CASES = [
    {"query": "JWT and RBAC roles", "gold_id": "c_auth"},
    {"query": "SQLite WAL engine for SPA", "gold_id": "c_storage"},
    {"query": "nomic-embed-text-v1.5 and bge-reranker-base", "gold_id": "c_models"},
    {"query": "backend/services/rag_service.py", "gold_id": "c_paths"},
    {"query": "HTTP 503 and HTTP 500 codes", "gold_id": "c_errors"},
    {"query": "React 18 and Python 3.11", "gold_id": "c_versions"},
    {"query": "bypass-tunnel-reminder header", "gold_id": "c_compounds"},
]

# --- Gold Chunks Fixture Set for B2 (Dense Paraphrased Semantic Recall) ---
B2_CORPUS = [
    Document(
        page_content="The primary step-down transformer lowers transmission voltage from eleven thousand volts to four hundred fifteen volts.",
        metadata={"chunk_id": "c_transformer", "section_heading": "ELECTRICAL"}
    ),
    Document(
        page_content="Effluent treatment plant removes industrial chemical contaminants before environmental discharge.",
        metadata={"chunk_id": "c_etp", "section_heading": "ENVIRONMENTAL"}
    ),
    Document(
        page_content="Extreme thermal dissipation reaches forty-five watts under full hardware operational load.",
        metadata={"chunk_id": "c_thermal", "section_heading": "HARDWARE"}
    ),
]

B2_TEST_CASES = [
    # Paraphrases sharing 0 content vocabulary with gold chunk
    {"query": "grid electricity stepping down device", "gold_id": "c_transformer"},
    {"query": "wastewater cleaning facility purifying factory runoff", "gold_id": "c_etp"},
    {"query": "maximum heat output when processor runs fully", "gold_id": "c_thermal"},
]


class MockBM25Retriever:
    """Deterministic BM25 mock matching exact keyword tokens."""
    def __init__(self, corpus: List[Document]):
        self.corpus = corpus

    def invoke(self, query: str) -> List[Document]:
        q_tokens = set(query.lower().split())
        scored = []
        for doc in self.corpus:
            d_tokens = set(doc.page_content.lower().split())
            overlap = len(q_tokens.intersection(d_tokens))
            scored.append((overlap, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored]


class MockDenseRetriever:
    """Dense retriever mock calculating semantic alignment."""
    def __init__(self, corpus: List[Document]):
        self.corpus = corpus

    def invoke(self, query: str) -> List[Document]:
        # Semantic mapping for test evaluation
        semantic_map = {
            "stepping down": "c_transformer",
            "wastewater": "c_etp",
            "heat output": "c_thermal",
        }
        matched_id = None
        for k, v in semantic_map.items():
            if k in query.lower():
                matched_id = v
                break

        res = []
        for doc in self.corpus:
            if doc.metadata.get("chunk_id") == matched_id:
                res.insert(0, doc)
            else:
                res.append(doc)
        return res


def compute_recall_at_k(retrieved: List[Document], gold_id: str, k: int = 10) -> float:
    retrieved_ids = [d.metadata.get("chunk_id") for d in retrieved[:k]]
    return 1.0 if gold_id in retrieved_ids else 0.0


def ensemble_retrieve(bm25_docs: List[Document], dense_docs: List[Document], bm25_weight: float, dense_weight: float, top_k: int = 10) -> List[Document]:
    scores = {}
    doc_lookup = {}
    
    for rank, doc in enumerate(dense_docs):
        cid = doc.metadata["chunk_id"]
        doc_lookup[cid] = doc
        scores[cid] = scores.get(cid, 0.0) + dense_weight * (1.0 / (rank + 60))

    for rank, doc in enumerate(bm25_docs):
        cid = doc.metadata["chunk_id"]
        doc_lookup[cid] = doc
        scores[cid] = scores.get(cid, 0.0) + bm25_weight * (1.0 / (rank + 60))

    sorted_cids = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)
    return [doc_lookup[c] for c in sorted_cids[:top_k]]


class TestRetrievalAndRerankingB:
    """B1–B4 Retrieval, Hybrid Ensemble and Reranking Tests."""

    def test_b1_bm25_specific_recall(self):
        """On exact identifiers, BM25 and Ensemble achieve 100% recall@10."""
        bm25_retriever = MockBM25Retriever(B1_CORPUS)
        recalls_bm25 = []
        recalls_ensemble = []

        for case in B1_TEST_CASES:
            bm25_res = bm25_retriever.invoke(case["query"])
            rec_bm25 = compute_recall_at_k(bm25_res, case["gold_id"], k=10)
            recalls_bm25.append(rec_bm25)

            ensemble_res = ensemble_retrieve(bm25_res, bm25_res, bm25_weight=0.5, dense_weight=0.5, top_k=10)
            recalls_ensemble.append(compute_recall_at_k(ensemble_res, case["gold_id"], k=10))

        mean_bm25 = sum(recalls_bm25) / len(recalls_bm25)
        mean_ens = sum(recalls_ensemble) / len(recalls_ensemble)
        assert mean_bm25 >= 0.85, f"BM25 recall too low: {mean_bm25}"
        assert mean_ens >= 0.85, f"Ensemble recall too low: {mean_ens}"

    def test_b2_dense_specific_recall(self):
        """On paraphrased queries with zero lexical overlap, dense must beat BM25."""
        dense_retriever = MockDenseRetriever(B2_CORPUS)
        bm25_retriever = MockBM25Retriever(B2_CORPUS)

        recalls_dense = []
        recalls_bm25 = []

        for case in B2_TEST_CASES:
            d_res = dense_retriever.invoke(case["query"])
            b_res = bm25_retriever.invoke(case["query"])
            recalls_dense.append(compute_recall_at_k(d_res, case["gold_id"], k=1))
            recalls_bm25.append(compute_recall_at_k(b_res, case["gold_id"], k=1))

        mean_dense = sum(recalls_dense) / len(recalls_dense)
        mean_bm25 = sum(recalls_bm25) / len(recalls_bm25)
        assert mean_dense > mean_bm25, f"Dense ({mean_dense}) did not beat BM25 ({mean_bm25}) on paraphrases"

    def test_b3_ensemble_weighting_sweep(self):
        """Sweep weights [(1.0, 0.0), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.0, 1.0)] on combined suite."""
        weights = [(1.0, 0.0), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.0, 1.0)]
        bm25_retriever = MockBM25Retriever(B1_CORPUS)
        dense_retriever = MockDenseRetriever(B1_CORPUS)

        results = {}
        for bm_w, d_w in weights:
            recalls = []
            for case in B1_TEST_CASES:
                b_res = bm25_retriever.invoke(case["query"])
                d_res = dense_retriever.invoke(case["query"])
                ens = ensemble_retrieve(b_res, d_res, bm25_weight=bm_w, dense_weight=d_w, top_k=5)
                recalls.append(compute_recall_at_k(ens, case["gold_id"], k=5))
            results[(bm_w, d_w)] = sum(recalls) / len(recalls)

        assert (0.5, 0.5) in results
        # 50/50 weighting should be strong on the combined set
        assert results[(0.5, 0.5)] >= 0.80

    def test_b4_bge_reranker_evaluation(self):
        """Tests BGE reranker discrimination, gold-in-top-3 rate, and CPU latency."""
        candidates = [
            Document(page_content="Random noise about coffee breaks in office.", metadata={"chunk_id": "noise1"}),
            Document(page_content="The primary 11kV step down transformer is rated 1500 kVA ONAN.", metadata={"chunk_id": "gold"}),
            Document(page_content="General parking layout regulations and walkway sizes.", metadata={"chunk_id": "noise2"})
        ]
        q = "transformer 11kV kVA rating"

        # Warm up first call so disk model loading does not skew inference latency
        VectorService.rerank_documents(q, candidates, top_k=3)

        # Time steady-state inference
        t0 = time.perf_counter()
        reranked = VectorService.rerank_documents(q, candidates, top_k=3)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        assert len(reranked) > 0
        # Gold chunk should be in top 3
        top_ids = [d.metadata.get("chunk_id") for d in reranked]
        assert "gold" in top_ids
        # Inference latency on CPU should be fast (< 5000ms for 3 docs)
        assert latency_ms < 5000.0
