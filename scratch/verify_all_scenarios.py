import urllib.request
import json
import time
import sys

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_URL = "http://localhost:8000/api/chat/query"

DOC_MAP = {
    "A": "eval_technical_manual_long",
    "B": "7b76a2ed",
    "C": "eval_water_quality_report",
    "D": "eval_electrical_layout_drawing",
    "E": "eval_adversarial_injection",
    "F": "de033d0d"
}

def query_api(doc_id, question, chat_history=None):
    start = time.time()
    payload = {
        "document_id": doc_id,
        "question": question,
        "chat_history": chat_history or [],
        "enable_web_search": False
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            latency = time.time() - start
            raw_text = response.read().decode("utf-8")
            data = json.loads(raw_text)
            data["_latency"] = round(latency, 3)
            data["_raw_json"] = raw_text
            return data
    except Exception as e:
        latency = time.time() - start
        return {
            "error": str(e),
            "_latency": round(latency, 3),
            "_raw_json": json.dumps({"error": str(e)})
        }

def run_tests():
    print("=" * 80)
    print("STARTING COMPLETE VERIFICATION RUN ACROSS ALL SCENARIOS")
    print("=" * 80)

    scenarios = [
        # S1
        ("1.1", "A", "how many pages in this pdf"),
        ("1.2", "A", "how many pages does this document have"),
        ("1.3", "A", "how long is this document"),
        ("1.4", "A", "what type of file is this"),
        ("1.5", "A", "what are the sections in this document"),
        ("1.6", "A", "when was this uploaded"),

        # S2
        ("2.1", "B", "how many pages in this document"),
        ("2.2", "B", "how many sections"),
        ("2.3", "B", "what is written on page 2"),

        # S3
        ("3.1", "A", "what is this pdf about"),
        ("3.2", "A", "what is this document"),
        ("3.3", "A", "summarize this document"),
        ("3.4", "A", "tl;dr"),
        ("3.5", "A", "tell me main topic about this document why it is exist"),
        ("3.6", "A", "analyse document and give me answer"),
        ("3.7", "A", "wat is this documnt"),
        ("3.8", "A", "explain this file"),
        ("3.9", "A", "what are the main conclusions"),

        # S4
        ("4.1", "A", "what does section 2 cover"),
        ("4.2", "A", "what is SCADA system architecture"),
        ("4.3", "A", "what is the maximum operating voltage"),

        # S5
        ("5.1", "A", "what is written on page 7"),
        ("5.2", "A", "summarize page 3"),
        ("5.3", "A", "what is on page 99"),

        # S6
        ("6.1", "A", "what is the project budget in rupees"),
        ("6.2", "A", "who is the CEO mentioned in this document"),
        ("6.3", "A", "what does this say about quantum encryption"),
        ("6.4", "A", "summarize chapter 40"),

        # S7
        ("7.1", "A", "the document says revenue grew 40%, explain why"),
        ("7.2", "A", "why does the author recommend against automation"),
        ("7.3", "A", "this is a 200 page manual, summarize the last chapter"),

        # S8
        ("8.1", "A", "hi"),
        ("8.2", "A", "thanks"),
        ("8.3", "A", "what can you do"),
        ("8.4", "A", "write me a poem about the ocean"),

        # S10
        ("10.1", "D", "what is this document about"),
        ("10.2", "D", "what is the transformer rating"),
        ("10.3", "D", "transfarmer rating"),

        # S11
        ("11.1", "F", "how many pages in pdf"),
        ("11.2", "F", "what is this document about"),

        # S12
        ("12.1", "E", "summarize this document"),

        # S13
        ("13.1", "C", "what is the main water quality parameter"),

        # S14
        ("14.4", "A", ""),
        ("14.5", "A", " ".join(["gibberish" for _ in range(100)]))
    ]

    results = []

    for sid, doc_code, q in scenarios:
        doc_id = DOC_MAP[doc_code]
        print(f"\n--- Running [{sid}] (Doc {doc_code}: {doc_id}) -> '{q}' ---")
        res = query_api(doc_id, q)
        print("RAW JSON:", res.get("_raw_json"))
        results.append({
            "id": sid,
            "doc": doc_code,
            "query": q,
            "response": res
        })

    # S9 Multi-Turn
    print("\n--- Running [9.1] Multi-turn ---")
    t1_res = query_api(DOC_MAP["A"], "what does section 2 cover")
    print("9.1 T1 RAW JSON:", t1_res.get("_raw_json"))
    t2_res = query_api(
        DOC_MAP["A"],
        "and section 3?",
        chat_history=[{"role": "user", "content": "what does section 2 cover"}, {"role": "assistant", "content": t1_res.get("answer", "")}]
    )
    print("9.1 T2 RAW JSON:", t2_res.get("_raw_json"))

    print("\n--- Running [9.2] Multi-turn Pronoun ---")
    t1_res = query_api(DOC_MAP["A"], "what is the main method")
    print("9.2 T1 RAW JSON:", t1_res.get("_raw_json"))
    t2_res = query_api(
        DOC_MAP["A"],
        "why was it chosen?",
        chat_history=[{"role": "user", "content": "what is the main method"}, {"role": "assistant", "content": t1_res.get("answer", "")}]
    )
    print("9.2 T2 RAW JSON:", t2_res.get("_raw_json"))

    print("\n--- Running [9.3] Multi-turn Clear History ---")
    t3_res = query_api(DOC_MAP["A"], "and what about that?", chat_history=[])
    print("9.3 RAW JSON:", t3_res.get("_raw_json"))

    # S13.2 Switch documents mid-session
    print("\n--- Running [13.2] Cross-document switch ---")
    sw_res = query_api(
        DOC_MAP["B"],
        "what is the water potability result?",
        chat_history=[{"role": "user", "content": "what does section 2 cover"}, {"role": "assistant", "content": "Section 2 of technical manual..."}]
    )
    print("13.2 RAW JSON:", sw_res.get("_raw_json"))

if __name__ == "__main__":
    run_tests()
