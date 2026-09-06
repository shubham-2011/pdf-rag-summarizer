import os
import sys
import json
import math
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
import config
from services.vector_service import VectorService
from services.rag_service import RAGService


def dcg_at_k(r: List[int], k: int) -> float:
    r = list(r)[:k]
    if not r:
        return 0.0
    return sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(r))


def ndcg_at_k(retrieved_chunk_ids: List[str], relevant_chunk_ids: List[str], k: int = 5) -> float:
    r = [1 if cid in relevant_chunk_ids else 0 for cid in retrieved_chunk_ids[:k]]
    actual_dcg = dcg_at_k(r, k)
    ideal_r = sorted([1] * min(len(relevant_chunk_ids), k) + [0] * max(0, k - len(relevant_chunk_ids)), reverse=True)
    ideal_dcg = dcg_at_k(ideal_r, k)
    if ideal_dcg == 0.0:
        return 1.0 if not relevant_chunk_ids else 0.0
    return actual_dcg / ideal_dcg


def reciprocal_rank(retrieved_chunk_ids: List[str], relevant_chunk_ids: List[str], k: int = 5) -> float:
    for idx, cid in enumerate(retrieved_chunk_ids[:k]):
        if cid in relevant_chunk_ids:
            return 1.0 / (idx + 1)
    return 0.0


def recall_at_k(retrieved_chunk_ids: List[str], relevant_chunk_ids: List[str], k: int = 20) -> float:
    retrieved_set = set(retrieved_chunk_ids[:k])
    relevant_set = set(relevant_chunk_ids)
    if not relevant_set:
        return 1.0
    hits = len(retrieved_set.intersection(relevant_set))
    return hits / len(relevant_set)


def evaluate_ranking_suite(dataset_path: str = None) -> Dict[str, Any]:
    if dataset_path is None:
        dataset_path = os.path.join(os.path.dirname(__file__), "fixtures", "ranking_eval_dataset.json")

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    recalls_20 = []
    mrrs_5 = []
    ndcgs_5 = []
    noise_counts = []
    total_top5_chunks = 0

    print(f"\n=======================================================")
    print(f"[EVAL] RUNNING RANKING EVALUATION SUITE ({len(cases)} test cases)")
    print(f"=======================================================")

    for i, item in enumerate(cases):
        q = item["query"]
        doc_id = item["doc_id"]
        relevant = item["relevant_chunk_ids"]
        must_not = item.get("must_not_return", [])

        # Step A: Base retrieval candidates (dense + bm25 pool)
        vs = VectorService.get_collection(doc_id)
        bm25 = VectorService.get_bm25_retriever(doc_id)
        
        candidates = []
        if vs:
            try:
                candidates.extend(vs.as_retriever(search_kwargs={"k": 20}).invoke(q))
            except Exception:
                pass
        if bm25:
            try:
                candidates.extend(bm25.invoke(q)[:10])
            except Exception:
                pass

        base_chunk_ids = [d.metadata.get("chunk_id") for d in candidates if d.metadata.get("chunk_id")]
        # Deduplicate while preserving rank
        seen = set()
        deduped_base = []
        for cid in base_chunk_ids:
            if cid not in seen:
                seen.add(cid)
                deduped_base.append(cid)

        # Calculate Recall@20 on base retrieval
        rec_20 = recall_at_k(deduped_base, relevant, k=20)
        recalls_20.append(rec_20)

        # Step B: Reranked candidates
        reranked_docs = VectorService.rerank_documents(q, candidates, top_k=5)
        reranked_ids = [d.metadata.get("chunk_id") for d in reranked_docs if d.metadata.get("chunk_id")]

        # Calculate MRR@5 & nDCG@5
        mrr = reciprocal_rank(reranked_ids, relevant, k=5)
        ndcg = ndcg_at_k(reranked_ids, relevant, k=5)
        mrrs_5.append(mrr)
        ndcgs_5.append(ndcg)

        # Noise@5 check
        top_5_ids = reranked_ids[:5]
        noise_in_top5 = sum(1 for cid in top_5_ids if cid in must_not)
        noise_counts.append(noise_in_top5)
        total_top5_chunks += len(top_5_ids)

        print(f"[{i+1}/{len(cases)}] Query: '{q[:45]}...' | Recall@20: {rec_20:.2f} | MRR@5: {mrr:.2f} | nDCG@5: {ndcg:.2f} | Noise: {noise_in_top5}")

    mean_recall_20 = sum(recalls_20) / len(recalls_20) if recalls_20 else 0.0
    mean_mrr_5 = sum(mrrs_5) / len(mrrs_5) if mrrs_5 else 0.0
    mean_ndcg_5 = sum(ndcgs_5) / len(ndcgs_5) if ndcgs_5 else 0.0
    noise_rate_5 = sum(noise_counts) / total_top5_chunks if total_top5_chunks > 0 else 0.0

    print(f"\n=======================================================")
    print(f"[RESULTS] EVALUATION BENCHMARK METRICS")
    print(f"=======================================================")
    print(f" * Recall@20 : {mean_recall_20:.4f}  (Target: >0.95) -> {'[PASS]' if mean_recall_20 >= 0.95 else '[FAIL]'}")
    print(f" * MRR@5     : {mean_mrr_5:.4f}  (Target: >0.80) -> {'[PASS]' if mean_mrr_5 >= 0.80 else '[FAIL]'}")
    print(f" * nDCG@5    : {mean_ndcg_5:.4f}  (Target: >0.75) -> {'[PASS]' if mean_ndcg_5 >= 0.75 else '[FAIL]'}")
    print(f" * Noise@5   : {noise_rate_5:.4f}  (Target: <0.05) -> {'[PASS]' if noise_rate_5 <= 0.05 else '[FAIL]'}")
    print(f"=======================================================\n")


    return {
        "recall_at_20": mean_recall_20,
        "mrr_at_5": mean_mrr_5,
        "ndcg_at_5": mean_ndcg_5,
        "noise_at_5": noise_rate_5,
        "total_queries": len(cases),
        "all_passed": (mean_recall_20 >= 0.95 and mean_mrr_5 >= 0.80 and mean_ndcg_5 >= 0.75 and noise_rate_5 <= 0.05)
    }


if __name__ == "__main__":
    evaluate_ranking_suite()
