"""Run the evaluation set through every retrieval mode and score it.

Outputs (eval/results/):
  <mode>.jsonl   one row per question with answer, contexts and RAGAS scores
  summary.json   all metrics
  REPORT.md      ablation table

Usage: python eval/run_eval.py [--modes dense,hybrid,hybrid_rerank] [--no-ragas]
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings, visible_roles  # noqa: E402
from app.rag import answer  # noqa: E402
from app.retrieval import MODES  # noqa: E402
from app.store import get_store  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "results"


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return float("nan")
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def run_mode(mode: str, questions: list[dict]) -> list[dict]:
    store = get_store()
    rows = []
    for q in questions:
        res = answer(q["question"], q["role"], mode)
        roles = visible_roles(q["role"])
        retrieved = [store.chunks[c] for c in res["retrieved"]]
        leaked_chunks = [
            c["chunk_id"] for c in retrieved
            if roles is not None and not set(c["allowed_roles"]) & set(roles)
        ]
        rows.append({
            **q,
            "mode": mode,
            "answer": res["answer"],
            "idk": res["idk"],
            "reason": res["reason"],
            "contexts": res["contexts"],
            "retrieved_titles": [c["title"] for c in retrieved],
            "top_rerank_score": res["top_rerank_score"],
            "latency_ms": res["latency_ms"]["total"],
            "leaked_chunks": leaked_chunks,
            "secret_in_answer": bool(q.get("secret")) and not res["idk"] and q["secret"] in res["answer"],
            "cost_usd": (res.get("usage") or {}).get("cost", 0.0) or 0.0,
        })
        flag = "IDK" if res["idk"] else "ans"
        print(f"  [{mode}] {q['id']:8s} {flag} {res['latency_ms']['total']:5d}ms")
    return rows


class LocalEmbeddings:
    """Minimal LangChain-style embeddings over fastembed (same model as the index)."""

    def __init__(self, name: str):
        from fastembed import TextEmbedding

        self.model = name
        self._m = TextEmbedding(model_name=name)

    def embed_documents(self, texts):
        return [v.tolist() for v in self._m.embed(list(texts))]

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


RAGAS_KEYS = ("faithfulness", "answer_relevancy", "llm_context_precision_with_reference")


def _missing(v) -> bool:
    return v is None or v != v


def ragas_scores(rows: list[dict], only: str | None = None, workers: int = 16, timeout: int = 90) -> list[dict]:
    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference, ResponseRelevancy
    from ragas.run_config import RunConfig

    judge = LangchainLLMWrapper(ChatOpenAI(
        model=settings.llm_model, base_url=settings.llm_base_url, api_key=settings.llm_api_key, temperature=0,
    ))
    emb = LangchainEmbeddingsWrapper(LocalEmbeddings(settings.embed_model))
    ds = EvaluationDataset.from_list([
        {"user_input": r["question"], "response": r["answer"], "retrieved_contexts": r["contexts"] or [""],
         "reference": r["ground_truth"]}
        for r in rows
    ])
    metrics = {
        "faithfulness": Faithfulness(),
        "answer_relevancy": ResponseRelevancy(strictness=1),
        "llm_context_precision_with_reference": LLMContextPrecisionWithReference(),
    }
    result = evaluate(
        ds,
        metrics=[metrics[only]] if only else list(metrics.values()),
        llm=judge,
        embeddings=emb,
        run_config=RunConfig(max_workers=workers, timeout=timeout, max_retries=3, max_wait=20),
        show_progress=True,
    )
    return result.to_pandas().to_dict("records")


def mean(xs):
    xs = [x for x in xs if x is not None and x == x]
    return round(statistics.mean(xs), 3) if xs else None


def summarize(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["type"] == "answerable"]
    una = [r for r in rows if r["type"] == "unanswerable"]
    leak = [r for r in rows if r["type"] == "role_leak"]
    lat = [r["latency_ms"] for r in rows]
    return {
        "n_questions": len(rows),
        "faithfulness": mean([r.get("faithfulness") for r in ans]),
        "answer_relevancy": mean([r.get("answer_relevancy") for r in ans]),
        "context_precision": mean([r.get("llm_context_precision_with_reference") for r in ans]),
        "ragas_scored": "/".join(
            str(sum(r.get(k) is not None and r.get(k) == r.get(k) for r in ans))
            for k in ("faithfulness", "answer_relevancy", "llm_context_precision_with_reference")
        ),
        "doc_hit_at_5": round(sum(r["title"] in r["retrieved_titles"] for r in ans) / len(ans), 3),
        "answered_rate_answerable": round(sum(not r["idk"] for r in ans) / len(ans), 3),
        "idk_accuracy_unanswerable": round(sum(r["idk"] for r in una) / len(una), 3),
        "role_leak_retrieval": sum(bool(r["leaked_chunks"]) for r in rows),
        "role_leak_answers": sum(r["secret_in_answer"] for r in leak),
        "role_leak_questions_refused": f"{sum(r['idk'] for r in leak)}/{len(leak)}",
        "latency_p50_ms": round(pct(lat, 0.5)),
        "latency_p95_ms": round(pct(lat, 0.95)),
        "llm_cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
    }


def write_report(summary: dict, n_ans: int, n_una: int, n_leak: int):
    cols = [
        ("faithfulness", "Faithfulness"), ("answer_relevancy", "Answer relevancy"),
        ("context_precision", "Context precision"), ("doc_hit_at_5", "Doc hit@5"),
        ("answered_rate_answerable", "Answered (answerable)"),
        ("idk_accuracy_unanswerable", "IDK accuracy (unanswerable)"),
        ("role_leak_retrieval", "Role leaks: retrieval"), ("role_leak_answers", "Role leaks: answers"),
        ("latency_p50_ms", "p50 ms"), ("latency_p95_ms", "p95 ms"),
    ]
    lines = [
        "# Evaluation results",
        "",
        f"Questions: {n_ans} answerable, {n_una} unanswerable, {n_leak} role-leak tests. "
        f"LLM `{settings.llm_model}` (answers and RAGAS judge), embeddings `{settings.embed_model}`.",
        "",
        "| Mode | " + " | ".join(c[1] for c in cols) + " |",
        "|---" * (len(cols) + 1) + "|",
    ]
    for mode, s in summary["modes"].items():
        lines.append(f"| {mode} | " + " | ".join(str(s[c[0]]) for c in cols) + " |")
    lines += [
        "",
        "RAGAS metrics are averaged over the answerable questions that the judge scored without a timeout; "
        "the scored counts (faithfulness/relevancy/precision) are in `summary.json` as `ragas_scored`. Doc hit@5 = the expected source "
        "document is among the 5 passages sent to the LLM. The rerank-score \"I don't know\" threshold "
        f"({settings.rerank_threshold}) only exists in `hybrid_rerank`; the other modes rely on the LLM to abstain.",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M')}.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--no-ragas", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="score saved answers instead of regenerating them")
    ap.add_argument("--rescore-missing", action="store_true",
                    help="with --reuse: re-run only RAGAS metrics that timed out, with a longer timeout")
    args = ap.parse_args()

    questions = [json.loads(line) for line in (HERE / "questions.jsonl").open(encoding="utf-8")]
    OUT.mkdir(exist_ok=True)
    summary = {"llm_model": settings.llm_model, "modes": {}}
    for mode in args.modes.split(","):
        print(f"== {mode}")
        saved = OUT / f"{mode}.jsonl"
        if args.reuse and saved.exists():
            rows = [json.loads(line) for line in saved.open(encoding="utf-8")]
            print(f"  reusing {len(rows)} saved answers")
        else:
            rows = run_mode(mode, questions)
            with saved.open("w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
        if args.rescore_missing:
            for k in RAGAS_KEYS:
                idx = [i for i, r in enumerate(rows) if r["type"] == "answerable" and _missing(r.get(k))]
                if idx:
                    print(f"  rescoring {k} for {len(idx)} questions")
                    for i, s in zip(idx, ragas_scores([rows[i] for i in idx], only=k, workers=4, timeout=600)):
                        rows[i][k] = s.get(k)
        elif not args.no_ragas:
            ans_idx = [i for i, r in enumerate(rows) if r["type"] == "answerable"]
            scores = ragas_scores([rows[i] for i in ans_idx])
            for i, s in zip(ans_idx, scores):
                for k in RAGAS_KEYS:
                    rows[i][k] = s.get(k)
        with (OUT / f"{mode}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
        summary["modes"][mode] = summarize(rows)
        print(json.dumps(summary["modes"][mode], indent=2))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    counts = {t: sum(q["type"] == t for q in questions) for t in ("answerable", "unanswerable", "role_leak")}
    write_report(summary, counts["answerable"], counts["unanswerable"], counts["role_leak"])


if __name__ == "__main__":
    main()
