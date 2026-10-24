"""Draft candidate QA pairs from random chunks with the LLM. Output is reviewed by hand
before anything is copied into eval/questions.jsonl."""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402
from app.rag import llm  # noqa: E402

ROLE_FOR = {"sec": "finance", "arxiv": "research", "wikipedia": "employee"}
PROMPT = """Write ONE factual question that this passage answers, plus the short answer.
The question must make sense on its own: name the company, paper, or topic explicitly
(e.g. "According to NVIDIA's 10-K, ..." or "In the DPR paper, ..."). Avoid yes/no questions.
Return JSON: {{"question": "...", "answer": "..."}}

Source: {title} - {section}
Passage:
{text}"""


def main(per_source: int = 16, seed: int = 7):
    random.seed(seed)
    chunks = [json.loads(line) for line in settings.chunks_path.open(encoding="utf-8")]
    out = Path(__file__).parent / "drafts.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for source, role in ROLE_FOR.items():
            pool = [c for c in chunks if c["source"] == source and len(c["text"]) > 900 and c["text"].count("|") < 10]
            for c in random.sample(pool, per_source):
                r = llm().chat.completions.create(
                    model=settings.llm_model,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": PROMPT.format(**c)}],
                )
                qa = json.loads(r.choices[0].message.content)
                row = {"question": qa["question"], "ground_truth": qa["answer"], "role": role,
                       "type": "answerable", "source_chunk": c["chunk_id"], "title": c["title"]}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"[{source}] {qa['question']}\n    -> {qa['answer']}")


if __name__ == "__main__":
    main()
