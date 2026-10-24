"""Hybrid retrieval: dense (Qdrant) + BM25, fused with RRF, then reranked."""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from langsmith import traceable

from app.config import settings
from app.store import get_store

MODES = ("dense", "hybrid", "hybrid_rerank")


@dataclass
class Hit:
    chunk_id: str
    score: float
    rerank_score: float | None = None


def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class Reranker:
    """Cohere Rerank when a key is set, otherwise a local cross-encoder via fastembed."""

    def __init__(self):
        if settings.cohere_api_key:
            import cohere

            self.client = cohere.ClientV2(api_key=settings.cohere_api_key)
            self.name = f"cohere/{settings.cohere_model}"
            self._calls: deque[float] = deque()
            self._lock = threading.Lock()
        else:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self.encoder = TextCrossEncoder(model_name=settings.local_reranker)
            self.name = f"local/{settings.local_reranker}"

    def _cohere(self, query: str, docs: list[str], top_n: int):
        from cohere.errors import TooManyRequestsError

        self.last_wait = 0.0
        for attempt in range(8):
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] > 60:
                    self._calls.popleft()
                if len(self._calls) >= settings.cohere_calls_per_minute:
                    wait = 60.5 - (now - self._calls[0])
                    time.sleep(wait)
                    self.last_wait += wait
                self._calls.append(time.monotonic())
            try:
                return self.client.rerank(model=settings.cohere_model, query=query, documents=docs, top_n=top_n)
            except TooManyRequestsError:
                time.sleep(10 * (attempt + 1))
                self.last_wait += 10 * (attempt + 1)
        raise RuntimeError("Cohere rerank kept returning 429")

    last_wait = 0.0

    def rerank(self, query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]:
        self.last_wait = 0.0
        if not docs:
            return []
        if hasattr(self, "client"):
            res = self._cohere(query, docs, top_n)
            return [(r.index, float(r.relevance_score)) for r in res.results]
        scores = list(self.encoder.rerank(query, docs))
        probs = [1 / (1 + math.exp(-s)) for s in scores]
        order = sorted(range(len(docs)), key=lambda i: probs[i], reverse=True)[:top_n]
        return [(i, probs[i]) for i in order]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return Reranker()


@traceable(run_type="retriever", name="hybrid_retrieve")
def retrieve(query: str, role: str, mode: str = "hybrid_rerank") -> list[Hit]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    store = get_store()
    k, n = settings.top_k_candidates, settings.top_n_final
    dense = store.dense_search(query, role, k)
    if mode == "dense":
        return [Hit(cid, s) for cid, s in dense[:n]]

    sparse = store.bm25_search(query, role, k)
    fused = rrf([[c for c, _ in dense], [c for c, _ in sparse]])[:k]
    if mode == "hybrid":
        return [Hit(cid, s) for cid, s in fused[:n]]

    texts = [f"{store.chunks[c]['header']}\n{store.chunks[c]['text']}" for c, _ in fused]
    ranked = get_reranker().rerank(query, texts, n)
    return [Hit(fused[i][0], fused[i][1], rs) for i, rs in ranked]
