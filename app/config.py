import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ROLES = ("finance", "research", "hr", "employee", "admin")
PUBLIC_ROLE = "all"


def _tokens() -> dict[str, str]:
    raw = os.getenv(
        "DEMO_TOKENS",
        "finance-token:finance,research-token:research,hr-token:hr,"
        "employee-token:employee,admin-token:admin",
    )
    pairs = (p.split(":", 1) for p in raw.split(",") if ":" in p)
    return {tok.strip(): role.strip() for tok, role in pairs}


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    cohere_api_key: str = os.getenv("COHERE_API_KEY", "")
    cohere_model: str = os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5")
    cohere_calls_per_minute: int = int(os.getenv("COHERE_CALLS_PER_MINUTE", "10"))
    local_reranker: str = os.getenv("LOCAL_RERANKER", "BAAI/bge-reranker-base")
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    qdrant_url: str = os.getenv("QDRANT_URL", "")
    qdrant_path: Path = ROOT / "storage" / "qdrant"
    collection: str = os.getenv("QDRANT_COLLECTION", "enterprise_docs")
    chunks_path: Path = ROOT / "storage" / "chunks.jsonl"
    docs_path: Path = ROOT / "storage" / "docs.json"
    feedback_path: Path = ROOT / "storage" / "feedback.jsonl"
    raw_dir: Path = ROOT / "data" / "raw"
    upload_dir: Path = ROOT / "data" / "uploads"
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_candidates: int = int(os.getenv("TOP_K_CANDIDATES", "30"))
    top_n_final: int = int(os.getenv("TOP_N_FINAL", "5"))
    rerank_threshold: float = float(os.getenv("RERANK_THRESHOLD", "0.15"))
    tokens: dict[str, str] = field(default_factory=_tokens)


settings = Settings()


def visible_roles(role: str) -> list[str] | None:
    """Values of `allowed_roles` a user may see. None means no filter (admin)."""
    if role == "admin":
        return None
    return [role, PUBLIC_ROLE]
