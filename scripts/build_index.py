"""Chunk every document in data/manifest.json and index it (Qdrant + BM25)."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import ROOT  # noqa: E402
from app.store import get_store, reset_storage  # noqa: E402


def main():
    reset_storage()
    store = get_store()
    docs = json.loads((ROOT / "data" / "manifest.json").read_text())
    t0 = time.time()
    for meta in docs:
        t = time.time()
        n = store.add_document(meta)
        print(f"{n:5d} chunks  {time.time() - t:6.1f}s  {meta['title']}")
    print(f"\n{store.stats()}  total {time.time() - t0:.0f}s")
    store.client.close()


if __name__ == "__main__":
    main()
