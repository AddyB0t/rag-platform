"""FastAPI service.

Auth is a demo stand-in: send `Authorization: Bearer <token>`; DEMO_TOKENS in .env maps
tokens to roles. Real authentication is out of scope for this project.
"""

import json
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import PUBLIC_ROLE, ROLES, ROOT, settings
from app.loaders import LOADERS
from app.rag import answer
from app.retrieval import MODES, get_reranker
from app.store import get_store

app = FastAPI(title="Enterprise RAG Knowledge Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def current_role(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    role = settings.tokens.get(token)
    if role is None:
        raise HTTPException(status_code=401, detail="Unknown or missing demo token")
    return role


def admin_only(role: str = Depends(current_role)) -> str:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return role


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = "hybrid_rerank"


class FeedbackRequest(BaseModel):
    request_id: str
    rating: int = Field(description="1 = thumbs up, -1 = thumbs down")
    comment: str = ""


@app.on_event("startup")
def _warm():
    get_store()
    get_reranker()


@app.get("/health")
def health():
    return {"status": "ok", "reranker": get_reranker().name, "llm_model": settings.llm_model, **get_store().stats()}


@app.get("/me")
def me(role: str = Depends(current_role)):
    return {"role": role}


@app.post("/chat")
def chat(req: ChatRequest, role: str = Depends(current_role)):
    if req.mode not in MODES:
        raise HTTPException(400, f"mode must be one of {MODES}")
    result = answer(req.question, role, req.mode)
    result.pop("contexts", None)
    return {"request_id": uuid.uuid4().hex, **result}


@app.post("/feedback")
def feedback(req: FeedbackRequest, role: str = Depends(current_role)):
    if req.rating not in (1, -1):
        raise HTTPException(400, "rating must be 1 or -1")
    settings.feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.feedback_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**req.model_dump(), "role": role, "ts": time.time()}) + "\n")
    return {"ok": True}


@app.post("/admin/upload")
async def upload(
    file: UploadFile = File(...),
    allowed_roles: str = Form(PUBLIC_ROLE, description="Comma-separated roles, or 'all'"),
    title: str = Form(""),
    _: str = Depends(admin_only),
):
    name = Path(file.filename or "upload").name
    if Path(name).suffix.lower() not in LOADERS:
        raise HTTPException(400, f"Supported types: {sorted(LOADERS)}")
    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    bad = [r for r in roles if r not in (*ROLES, PUBLIC_ROLE)]
    if not roles or bad:
        raise HTTPException(400, f"Unknown roles: {bad}")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.upload_dir / name
    dest.write_bytes(await file.read())
    meta = {
        "path": str(dest.relative_to(ROOT)),
        "source": "upload",
        "url": "",
        "title": title or Path(name).stem,
        "allowed_roles": roles,
    }
    try:
        n = get_store().add_document(meta)
    except Exception as e:
        raise HTTPException(422, f"Could not index file: {e}") from e
    return {"ok": True, "title": meta["title"], "chunks": n, "allowed_roles": roles}


@app.get("/admin/docs")
def list_docs(_: str = Depends(admin_only)):
    store = get_store()
    return {"stats": store.stats(), "documents": store.docs}


_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(_dist / "index.html")
