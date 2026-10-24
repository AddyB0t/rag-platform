# Evaluation results

Questions: 43 answerable, 12 unanswerable, 8 role-leak tests. LLM `openai/gpt-4o-mini` (answers and RAGAS judge), embeddings `BAAI/bge-small-en-v1.5`.

| Mode | Faithfulness | Answer relevancy | Context precision | Doc hit@5 | Answered (answerable) | IDK accuracy (unanswerable) | Role leaks: retrieval | Role leaks: answers | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| dense | 0.904 | 0.821 | 0.812 | 1.0 | 0.93 | 1.0 | 0 | 0 | 1738 | 2811 |
| hybrid | 0.951 | 0.881 | 0.902 | 1.0 | 1.0 | 1.0 | 0 | 0 | 1809 | 2675 |
| hybrid_rerank | 0.98 | 0.88 | 0.955 | 1.0 | 1.0 | 1.0 | 0 | 0 | 2163 | 3237 |

RAGAS metrics are averaged over the answerable questions that the judge scored without a timeout; the scored counts (faithfulness/relevancy/precision) are in `summary.json` as `ragas_scored`. Doc hit@5 = the expected source document is among the 5 passages sent to the LLM. The rerank-score "I don't know" threshold (0.15) only exists in `hybrid_rerank`; the other modes rely on the LLM to abstain.

Generated 2026-10-24 20:42.
