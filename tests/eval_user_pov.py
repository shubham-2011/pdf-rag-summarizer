import sys
import os
import time
import json
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(repo_root, "backend")
tests_dir = os.path.join(repo_root, "tests")

for p in [repo_root, backend_dir, tests_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from services.pdf_service import PDFService
from services.vector_service import VectorService
from services.rag_service import RAGService
from services.document_service import DocumentService
from services.metadata_service import MetadataService
from mechanical_validators import MechanicalValidators
from llm_judge import LLMJudge

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_documents")
GOLDEN_DATASET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_dataset.json")
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_user_pov_results.json")

def prepare_documents():
    """Indexes all golden test documents into MetadataService and VectorService."""
    print("📦 Ingesting and indexing Golden Benchmark documents...")
    if not os.path.exists(GOLDEN_DATASET_PATH):
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "generate_eval_dataset.py")], check=True)

    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    indexed_docs = {}
    for doc_key, doc_info in dataset["documents"].items():
        doc_filename = doc_info["file"]
        file_path = os.path.join(DOCS_DIR, doc_filename)
        if not os.path.exists(file_path):
            continue

        doc_id = f"eval_{doc_key}"
        file_size = os.path.getsize(file_path)

        # Audit & Parse
        chunks, total_units = DocumentService.process_document(file_path)
        id_card = DocumentService.generate_identity_card(chunks, doc_filename, total_units)
        
        # Override / ensure title
        if doc_info.get("title"):
            id_card["title"] = doc_info["title"]
        if doc_info.get("authors"):
            id_card["authors"] = doc_info["authors"]
        if doc_info.get("doc_date"):
            id_card["doc_date"] = doc_info["doc_date"]

        # Store in Vector Store
        VectorService.create_collection(chunks, collection_name=doc_id, identity_card=id_card)
        import config
        index_dir = os.path.join(getattr(config, "VECTOR_STORE_DIR", "./vector_store_data"), doc_id)
        
        # Register in SQLite Metadata Registry
        content_hash = MetadataService.calculate_file_hash(open(file_path, "rb").read())
        format_ext = doc_info.get("format", doc_filename.split(".")[-1])
        unit_count = doc_info.get("unit_count", len(chunks))
        unit_kind = doc_info.get("unit_kind", "page")

        MetadataService.register_document(
            doc_id=doc_id,
            content_hash=content_hash,
            filename=doc_filename,
            format_ext=format_ext,
            mime_type=f"application/{format_ext}",
            size_bytes=file_size,
            unit_count=unit_count,
            unit_kind=unit_kind,
            storage_path=file_path,
            status="READY"
        )
        MetadataService.update_status(doc_id, "READY", index_path=index_dir)
        MetadataService.save_identity(doc_id, id_card)
        
        # Save outline if available
        outline = [{"heading": s, "locator_index": i+1, "char_count": 200} for i, s in enumerate(id_card.get("structure_outline", []))]
        MetadataService.save_outline(doc_id, outline)

        # Build page-to-text mapping for mechanical citation checks
        pages_text = {}
        for c in chunks:
            p_num = int(c.metadata.get("page_label", c.metadata.get("page", 1)))
            pages_text[p_num] = pages_text.get(p_num, "") + "\n" + c.page_content

        indexed_docs[doc_key] = {
            "doc_id": doc_id,
            "info": doc_info,
            "pages_text": pages_text,
            "total_pages": unit_count,
            "chunks": chunks
        }

    return dataset, indexed_docs

def run_user_pov_evaluation():
    print("================================================================================")
    print("🎯 USER-POV EVALUATION HARNESS & MULTI-CLASS JUDGE SUITE")
    print("================================================================================")

    dataset, indexed_docs = prepare_documents()

    QUESTION_CLASSES = [
        "STRUCTURAL",
        "LOCATIONAL",
        "GLOBAL",
        "LOCAL",
        "VERIFICATION",
        "TABULAR",
        "CONVERSATIONAL"
    ]

    class_stats = {
        cls: {
            "total": 0,
            "passed": 0,
            "refusals": 0,
            "unwarranted_refusals": 0,
            "hallucinations": 0,
            "fragments": 0,
            "wrong_class": 0,
            "misled": 0,
            "latencies": []
        }
        for cls in QUESTION_CLASSES
    }

    all_citations_evaluated = []
    detailed_log = []

    for doc_key, doc_data in indexed_docs.items():
        doc_id = doc_data["doc_id"]
        doc_info = doc_data["info"]
        questions = doc_info.get("questions", [])

        print(f"\n📄 Testing Document: {doc_info.get('title', doc_key)} ({doc_info.get('unit_count')} {doc_info.get('unit_kind', 'page')}s)")

        for q_item in questions:
            q_class = q_item["class"]
            question_text = q_item["question"]
            subkind = q_item.get("subkind", "")

            t0 = time.time()
            res = RAGService.query(document_id=doc_id, question=question_text)
            latency = time.time() - t0

            answer = res.get("answer", "")
            strategy = res.get("strategy", "")
            sources = res.get("sources", [])
            resp_class = res.get("question_class", "")

            class_stats[q_class]["total"] += 1
            class_stats[q_class]["latencies"].append(latency)

            # 1. STRUCTURAL mechanical check
            if q_class == "STRUCTURAL":
                struct_res = MechanicalValidators.validate_structural_response(
                    response=res,
                    expected_metadata=doc_info,
                    subkind=subkind or "page_count"
                )
                passed = (struct_res["verdict"] == "PASS")
                if passed:
                    class_stats[q_class]["passed"] += 1
                else:
                    if not struct_res["is_metadata_strategy"]:
                        class_stats[q_class]["wrong_class"] += 1

                print(f"  [{struct_res['verdict']}] STRUCTURAL ({subkind}): '{question_text}' -> Strategy: {strategy}")

                detailed_log.append({
                    "doc": doc_key,
                    "class": q_class,
                    "question": question_text,
                    "strategy": strategy,
                    "answer": answer[:200],
                    "verdict": struct_res["verdict"],
                    "metrics": struct_res
                })
                continue

            # 2. Citation Mechanical Check
            citation_res = MechanicalValidators.verify_citations_mechanically(
                sources=sources,
                doc_pages_text=doc_data["pages_text"],
                total_pages=doc_data["total_pages"]
            )
            all_citations_evaluated.append(citation_res)

            # 3. Locational Precision Check
            loc_precision_res = None
            if q_class == "LOCATIONAL":
                target_pg = q_item.get("target_page", 1)
                actual_text = doc_data["pages_text"].get(target_pg, "")
                loc_precision_res = LLMJudge.evaluate_locational_precision(
                    question=question_text,
                    actual_page_text=actual_text,
                    answer=answer
                )

            # 4. LLM Answer Quality Judge
            all_text = "\n".join(doc_data["pages_text"].values())
            retrieved_ctx = "\n".join([s.get("text", "") for s in sources])
            quality_res = LLMJudge.evaluate_answer_quality(
                doc_facts=doc_info,
                source_excerpts=all_text,
                retrieved_context=retrieved_ctx,
                question=question_text,
                question_class=q_class,
                answer=answer,
                response_strategy=strategy
            )

            # Aggregate stats
            passed = (quality_res.get("verdict") == "PASS")
            if loc_precision_res and loc_precision_res.get("verdict") == "FAIL":
                passed = False

            if passed:
                class_stats[q_class]["passed"] += 1
            if quality_res.get("unwarranted_refusal"):
                class_stats[q_class]["unwarranted_refusals"] += 1
            if quality_res.get("hallucinated_claims"):
                class_stats[q_class]["hallucinations"] += 1
            if quality_res.get("fragment_answer"):
                class_stats[q_class]["fragments"] += 1
            if quality_res.get("wrong_class_handling"):
                class_stats[q_class]["wrong_class"] += 1
            if quality_res.get("user_outcome") == "misled":
                class_stats[q_class]["misled"] += 1

            verdict_str = "PASS" if passed else "FAIL"
            print(f"  [{verdict_str}] {q_class}: '{question_text}' (Outcome: {quality_res.get('user_outcome')})")

            detailed_log.append({
                "doc": doc_key,
                "class": q_class,
                "question": question_text,
                "strategy": strategy,
                "answer": answer[:200],
                "verdict": verdict_str,
                "quality_judge": quality_res,
                "citation_check": citation_res,
                "locational_check": loc_precision_res
            })

    # =========================================================
    # §6 REPORTING TABLE
    # =========================================================
    print("\n================================================================================")
    print("📊 USER-POV EVALUATION SCORECARD BY QUESTION CLASS (§6)")
    print("================================================================================")
    header = f"{'CLASS':<15} | {'N':<4} | {'PASS':<6} | {'REFUSE':<8} | {'HALLUC':<7} | {'FRAGMENT':<8} | {'WRONG-CLASS':<11}"
    print(header)
    print("-" * len(header))

    total_n = 0
    total_passed = 0
    total_unwarranted_refusals = 0
    total_hallucinations = 0
    total_fragments_global = 0
    total_wrong_class = 0
    total_misled = 0

    for cls in QUESTION_CLASSES:
        st = class_stats[cls]
        n = st["total"]
        if n == 0:
            continue
        total_n += n
        total_passed += st["passed"]
        total_unwarranted_refusals += st["unwarranted_refusals"]
        total_hallucinations += st["hallucinations"]
        if cls == "GLOBAL":
            total_fragments_global += st["fragments"]
        total_wrong_class += st["wrong_class"]
        total_misled += st["misled"]

        pass_pct = f"{round((st['passed'] / n) * 100, 1)}%"
        ref_str = f"{st['unwarranted_refusals']}" if st['unwarranted_refusals'] > 0 else "0"
        hal_str = f"{st['hallucinations']}" if st['hallucinations'] > 0 else "0"
        frag_str = f"{st['fragments']}" if st['fragments'] > 0 else "0"
        wc_str = f"{st['wrong_class']}" if st['wrong_class'] > 0 else "0"

        print(f"{cls:<15} | {n:<4} | {pass_pct:<6} | {ref_str:<8} | {hal_str:<7} | {frag_str:<8} | {wc_str:<11}")

    print("-" * len(header))

    # Calculate overall citation validity
    total_citations_count = sum(c["citations_count"] for c in all_citations_evaluated)
    total_valid_citations = sum(c["valid_citations"] for c in all_citations_evaluated)
    overall_citation_validity = (total_valid_citations / total_citations_count) if total_citations_count > 0 else 1.0

    # Structural accuracy
    struct_total = class_stats["STRUCTURAL"]["total"]
    struct_passed = class_stats["STRUCTURAL"]["passed"]
    structural_accuracy = (struct_passed / struct_total) if struct_total > 0 else 1.0

    # Gating checks
    unwarranted_refusal_rate = (total_unwarranted_refusals / total_n) if total_n > 0 else 0.0
    hallucination_rate = (total_hallucinations / total_n) if total_n > 0 else 0.0
    wrong_class_rate = (total_wrong_class / total_n) if total_n > 0 else 0.0

    g1 = (structural_accuracy == 1.0)
    g2 = (overall_citation_validity >= 0.98)
    g3 = (unwarranted_refusal_rate <= 0.02)
    g4 = (hallucination_rate <= 0.02)
    g5 = (total_fragments_global == 0)
    g6 = (total_wrong_class == 0)
    g7 = (total_misled == 0)

    overall_ci_gate_pass = all([g1, g2, g3, g4, g5, g6, g7])

    print("\n================================================================================")
    print("🛡️ SECTION 4: CI GATING COMPLIANCE CHECK")
    print("================================================================================")
    print(f"1. structural_accuracy       == 100%   -> {structural_accuracy*100:.1f}% [{'PASS' if g1 else 'FAIL'}]")
    print(f"2. citation_validity         >= 98%    -> {overall_citation_validity*100:.1f}% [{'PASS' if g2 else 'FAIL'}]")
    print(f"3. unwarranted_refusal_rate  <= 2%     -> {unwarranted_refusal_rate*100:.1f}% [{'PASS' if g3 else 'FAIL'}]")
    print(f"4. hallucination_rate        <= 2%     -> {hallucination_rate*100:.1f}% [{'PASS' if g4 else 'FAIL'}]")
    print(f"5. fragment_answer_rate      == 0%     -> {total_fragments_global} fragments [{'PASS' if g5 else 'FAIL'}]")
    print(f"6. wrong_class_handling      == 0%     -> {total_wrong_class} errors [{'PASS' if g6 else 'FAIL'}]")
    print(f"7. user_outcome == 'misled'  == 0%     -> {total_misled} misled [{'PASS' if g7 else 'FAIL'}]")
    print(f"\nOVERALL CI GATE VERDICT: {'🟢 PASSED' if overall_ci_gate_pass else '🔴 FAILED'}")
    print("================================================================================")

    # Save results
    results_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "class_summary": class_stats,
        "gating_compliance": {
            "structural_accuracy": structural_accuracy,
            "citation_validity": overall_citation_validity,
            "unwarranted_refusal_rate": unwarranted_refusal_rate,
            "hallucination_rate": hallucination_rate,
            "fragments_in_global": total_fragments_global,
            "wrong_class_handling_count": total_wrong_class,
            "misled_outcomes_count": total_misled,
            "gate_verdict": "PASS" if overall_ci_gate_pass else "FAIL"
        },
        "detailed_test_log": detailed_log
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as rf:
        json.dump(results_payload, rf, indent=2)
    print(f"Detailed evaluation payload saved to: {RESULTS_PATH}")

if __name__ == "__main__":
    run_user_pov_evaluation()
