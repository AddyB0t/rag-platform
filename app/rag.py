"""Answer generation with forced inline citations and an "I don't know" fallback."""

import re
import time
from functools import lru_cache

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from app.config import settings
from app.retrieval import get_reranker, retrieve
from app.store import get_store

IDK = "I don't know. The documents you can access do not contain enough evidence to answer this."

SYSTEM = """You answer questions for employees using ONLY the numbered context passages.
Rules:
- Every factual sentence must end with one or more citations like [1] or [2][3], using the passage numbers.
- Use only facts stated in the passages. Do not use outside knowledge.
- If the passages do not contain the answer, reply with exactly: I don't know
- Be concise: at most 5 sentences."""

_CITE = re.compile(r"\[(\d+)\]")


@lru_cache(maxsize=1)
def llm() -> OpenAI:
    return wrap_openai(OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key))


def _context(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{i}] ({c['title']} - {c['section']})\n{c['text']}" for i, c in enumerate(chunks, 1))


@traceable(run_type="chain", name="rag_chat")
def answer(question: str, role: str, mode: str = "hybrid_rerank") -> dict:
    t0 = time.perf_counter()
    store = get_store()
    hits = retrieve(question, role, mode)
    t_retrieve = time.perf_counter() - t0
    chunks = [store.chunks[h.chunk_id] for h in hits]
    top_rerank = max((h.rerank_score for h in hits if h.rerank_score is not None), default=None)

    base = {
        "question": question,
        "role": role,
        "mode": mode,
        "reranker": get_reranker().name if mode == "hybrid_rerank" else None,
        "top_rerank_score": top_rerank,
        "contexts": [c["text"] for c in chunks],
    }

    if not chunks or (top_rerank is not None and top_rerank < settings.rerank_threshold):
        return {**base, "answer": IDK, "idk": True, "citations": [], "reason": "low_retrieval_score",
                "latency_ms": {"retrieve": round(t_retrieve * 1000), "total": round((time.perf_counter() - t0) * 1000)}}

    resp = llm().chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n{_context(chunks)}\n\nQuestion: {question}"},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    used = sorted({int(m) for m in _CITE.findall(text) if 1 <= int(m) <= len(chunks)})
    idk = text.lower().startswith("i don't know") or not used
    citations = [] if idk else [
        {
            "n": n,
            "chunk_id": chunks[n - 1]["chunk_id"],
            "title": chunks[n - 1]["title"],
            "section": chunks[n - 1]["section"],
            "page": chunks[n - 1]["page"],
            "url": chunks[n - 1]["url"],
            "source": chunks[n - 1]["source"],
            "snippet": chunks[n - 1]["text"][:600],
        }
        for n in used
    ]
    return {
        **base,
        "answer": IDK if idk else text,
        "idk": idk,
        "citations": citations,
        "reason": "model_abstained" if idk else "answered",
        "usage": resp.usage.model_dump() if resp.usage else None,
        "latency_ms": {"retrieve": round(t_retrieve * 1000), "total": round((time.perf_counter() - t0) * 1000)},
    }
