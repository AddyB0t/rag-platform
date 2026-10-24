"""Chunking, the Qdrant vector index (via LlamaIndex) and the role-filtered BM25 index."""

import hashlib
import json
import os
import re
import threading
import uuid
from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi

from app.config import ROOT, settings, visible_roles
from app.loaders import load_file

_STOP = set(
    "a an and are as at be by for from has have in is it its of on or that the this to was "
    "were will with what which who how when where why does do did can".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-'][a-z0-9]+)*")


def bm25_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def doc_id_for(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()[:12]


def chunk_document(meta: dict) -> list[dict]:
    """Split one document into ~512-token chunks that never cross a section boundary."""
    splitter = SentenceSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    path = ROOT / meta["path"]
    doc_id = meta.get("doc_id") or doc_id_for(meta["path"])
    chunks = []
    for sec in load_file(path):
        header = f"{meta['title']} - {sec.section}".strip(" -")
        for piece in splitter.split_text(sec.text):
            n = len(chunks)
            chunks.append({
                "chunk_id": f"{doc_id}:{n}",
                "doc_id": doc_id,
                "text": piece,
                "header": header,
                "title": meta["title"],
                "source": meta["source"],
                "section": sec.section,
                "page": sec.page,
                "url": meta.get("url", ""),
                "allowed_roles": meta["allowed_roles"],
            })
    return chunks


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class Store:
    def __init__(self):
        self._lock = threading.Lock()
        self.embed = FastEmbedEmbedding(
            model_name=settings.embed_model,
            embed_batch_size=64,
            threads=os.cpu_count(),
            cache_dir=str(ROOT / "storage" / "models"),
        )
        if settings.qdrant_url:
            self.client = QdrantClient(url=settings.qdrant_url)
        else:
            settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(settings.qdrant_path))
        self.vector_store = QdrantVectorStore(client=self.client, collection_name=settings.collection)
        self.index = VectorStoreIndex.from_vector_store(self.vector_store, embed_model=self.embed)
        self.chunks: dict[str, dict] = {}
        self.docs: list[dict] = []
        self._bm25_cache: dict[tuple, tuple[BM25Okapi, list[str]]] = {}
        self._load()

    def _load(self):
        if settings.chunks_path.exists():
            with settings.chunks_path.open(encoding="utf-8") as f:
                for line in f:
                    c = json.loads(line)
                    self.chunks[c["chunk_id"]] = c
        if settings.docs_path.exists():
            self.docs = json.loads(settings.docs_path.read_text(encoding="utf-8"))

    def _save(self):
        settings.chunks_path.parent.mkdir(parents=True, exist_ok=True)
        with settings.chunks_path.open("w", encoding="utf-8") as f:
            for c in self.chunks.values():
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        settings.docs_path.write_text(json.dumps(self.docs, indent=2), encoding="utf-8")

    def add_document(self, meta: dict) -> int:
        meta = {**meta, "doc_id": meta.get("doc_id") or doc_id_for(meta["path"])}
        chunks = chunk_document(meta)
        nodes = []
        for c in chunks:
            node = TextNode(
                id_=_point_id(c["chunk_id"]),
                text=f"{c['header']}\n{c['text']}",
                metadata={k: c[k] for k in ("chunk_id", "doc_id", "title", "source", "section", "page", "url", "allowed_roles")},
            )
            node.excluded_embed_metadata_keys = list(node.metadata)
            node.excluded_llm_metadata_keys = list(node.metadata)
            nodes.append(node)
        with self._lock:
            if nodes:
                self.index.insert_nodes(nodes)
            for c in chunks:
                self.chunks[c["chunk_id"]] = c
            self.docs = [d for d in self.docs if d["doc_id"] != meta["doc_id"]]
            self.docs.append({**meta, "chunks": len(chunks)})
            self._bm25_cache.clear()
            self._save()
        return len(chunks)

    def _filters(self, role: str) -> MetadataFilters | None:
        roles = visible_roles(role)
        if roles is None:
            return None
        return MetadataFilters(filters=[MetadataFilter(key="allowed_roles", value=roles, operator=FilterOperator.IN)])

    def dense_search(self, query: str, role: str, k: int) -> list[tuple[str, float]]:
        retriever = self.index.as_retriever(similarity_top_k=k, filters=self._filters(role))
        return [(n.node.metadata["chunk_id"], float(n.score or 0.0)) for n in retriever.retrieve(query)]

    def _bm25_for(self, role: str) -> tuple[BM25Okapi, list[str]]:
        roles = visible_roles(role)
        key = tuple(roles) if roles else ("*",)
        with self._lock:
            if key not in self._bm25_cache:
                ids = [
                    cid for cid, c in self.chunks.items()
                    if roles is None or set(c["allowed_roles"]) & set(roles)
                ]
                corpus = [bm25_tokens(f"{self.chunks[i]['header']} {self.chunks[i]['text']}") for i in ids]
                self._bm25_cache[key] = (BM25Okapi(corpus), ids)
            return self._bm25_cache[key]

    def bm25_search(self, query: str, role: str, k: int) -> list[tuple[str, float]]:
        bm25, ids = self._bm25_for(role)
        if not ids:
            return []
        scores = bm25.get_scores(bm25_tokens(query))
        top = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)[:k]
        return [(ids[i], float(scores[i])) for i in top if scores[i] > 0]

    def stats(self) -> dict:
        by_source: dict[str, int] = {}
        for c in self.chunks.values():
            by_source[c["source"]] = by_source.get(c["source"], 0) + 1
        return {"documents": len(self.docs), "chunks": len(self.chunks), "chunks_by_source": by_source}


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def reset_storage():
    import shutil

    for p in (settings.qdrant_path, settings.chunks_path, settings.docs_path):
        if Path(p).is_dir():
            shutil.rmtree(p)
        elif Path(p).exists():
            Path(p).unlink()
