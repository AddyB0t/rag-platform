"""Send every evaluation question through the running API (so each request is traced in LangSmith).

Usage: python eval/replay_api.py [http://127.0.0.1:8000]
"""

import json
import sys
from pathlib import Path

import httpx

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
questions = [json.loads(line) for line in (Path(__file__).parent / "questions.jsonl").open(encoding="utf-8")]
with httpx.Client(timeout=300) as client:
    for q in questions:
        r = client.post(f"{base}/chat", json={"question": q["question"]},
                        headers={"Authorization": f"Bearer {q['role']}-token"})
        r.raise_for_status()
        d = r.json()
        print(f"{q['id']:8s} {'IDK' if d['idk'] else 'ans'} {d['latency_ms']['total']:5d}ms", flush=True)
