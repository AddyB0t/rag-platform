"""CLI: python scripts/ask.py <role> "<question>" [mode]"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.rag import answer  # noqa: E402

if __name__ == "__main__":
    role, question = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "hybrid_rerank"
    res = answer(question, role, mode)
    res.pop("contexts")
    for c in res["citations"]:
        c["snippet"] = c["snippet"][:120]
    print(json.dumps(res, indent=2, ensure_ascii=False))
