"""Offline evaluation harness.

Runs the golden dataset through the live pipeline and reports the metrics that
matter for an LLM app: intent-routing accuracy, SQL execution success,
keyword-grounding (a cheap faithfulness proxy), refusal correctness, and
latency. Writes a JSON report and PNG charts so results are easy to showcase.

Usage:
    python eval/evaluate.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Make the app package importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from config import FAQ_RERANK_K, FAQ_RETRIEVE_K  # noqa: E402
from faq import _rerank, _retrieve, faq_chain, ingest_faq_data  # noqa: E402
from llm import chat  # noqa: E402
from router import route  # noqa: E402
from smalltalk import small_talk_chain  # noqa: E402
from sql import sql_chain  # noqa: E402

DATA = Path(__file__).parent / "golden_dataset.json"
REPORT_DIR = Path(__file__).parent / "reports"

SQL_FAILURE_MARKERS = ("sorry", "couldn't", "trouble")


def _answer(intent: str, query: str) -> str:
    if intent == "faq":
        return faq_chain(query)
    if intent == "sql":
        return sql_chain(query)
    return small_talk_chain(query)


def _faithful(query: str, answer: str, context: str) -> bool:
    """LLM-as-judge: is the answer fully supported by the retrieved context?

    This is the real anti-hallucination signal — it checks groundedness, not
    keyword overlap. The judge sees only question, context and answer.
    """
    prompt = (
        "You are a strict evaluator. Reply with a single word, PASS or FAIL.\n"
        "PASS only if the ANSWER is fully supported by the CONTEXT and adds no "
        "facts that are not in the CONTEXT. A correct refusal (the answer says "
        "it doesn't know) also counts as PASS.\n\n"
        f"QUESTION: {query}\nCONTEXT: {context}\nANSWER: {answer}"
    )
    # gpt-oss spends tokens on hidden reasoning first, so give the verdict room.
    verdict = chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=256)
    return "PASS" in verdict.strip().upper()


def _faq_context(query: str) -> str:
    ranked = _rerank(query, _retrieve(query, FAQ_RETRIEVE_K))
    return "\n".join(a for _, _, a in ranked[:FAQ_RERANK_K])


def run() -> dict:
    cases = json.loads(DATA.read_text())
    ingest_faq_data()

    rows = []
    for c in cases:
        t0 = time.time()
        predicted = route(c["query"])
        answer = _answer(c["intent"], c["query"])
        latency = time.time() - t0

        routed_ok = predicted.name == c["intent"]
        # Keyword check relaxed to "any expected fact present".
        grounded = any(k.lower() in answer.lower() for k in c["expect_contains"]) \
            if c["expect_contains"] else None
        # LLM-as-judge faithfulness, only meaningful for retrieval-based FAQ answers.
        faithful = _faithful(c["query"], answer, _faq_context(c["query"])) \
            if c["intent"] == "faq" else None
        sql_ok = None
        if c["intent"] == "sql":
            sql_ok = not any(m in answer.lower() for m in SQL_FAILURE_MARKERS)

        rows.append({
            "id": c["id"], "query": c["query"], "intent": c["intent"],
            "predicted": predicted.name, "confidence": round(predicted.confidence, 3),
            "routed_ok": routed_ok, "grounded": grounded, "faithful": faithful,
            "sql_ok": sql_ok, "latency_s": round(latency, 2), "answer": answer,
        })
        print(f"[{c['id']:>2}] {c['intent']:<10} routed={'OK' if routed_ok else 'X'} "
              f"({predicted.confidence:.2f})  {latency:5.2f}s  {c['query']}")

    def rate(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    metrics = {
        "n_cases": len(rows),
        "routing_accuracy": rate("routed_ok"),
        "faithfulness_rate": rate("faithful"),
        "grounding_rate": rate("grounded"),
        "sql_success_rate": rate("sql_ok"),
        "avg_latency_s": round(sum(r["latency_s"] for r in rows) / len(rows), 2),
    }

    REPORT_DIR.mkdir(exist_ok=True)
    report = {"metrics": metrics, "rows": rows}
    (REPORT_DIR / "report.json").write_text(json.dumps(report, indent=2))
    _charts(metrics)
    print("\nMETRICS:", json.dumps(metrics, indent=2))
    return metrics


def _charts(metrics: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    labels = ["routing_accuracy", "faithfulness_rate", "grounding_rate", "sql_success_rate"]
    values = [(metrics.get(k) or 0) * 100 for k in labels]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar([name.replace("_", "\n") for name in labels], values, color="#4C7BF3")
    ax.set_ylim(0, 100)
    ax.set_ylabel("%")
    ax.set_title("Chatbot quality metrics")
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}%", ha="center")
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "metrics.png", dpi=120)


if __name__ == "__main__":
    run()
