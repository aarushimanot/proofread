"""
Proofread API (FastAPI) + the built web UI, served together on one port.

Easiest way to run everything (from the proofread/ folder):
    ./start.sh                 -> http://localhost:8000

Backend only, from backend/:
    uvicorn app.main:app --reload --port 8000

Models are loaded and the SQLite database is prepared once at startup (see
`lifespan`), so the first start takes a little while; requests after that are fast.
"""
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db
from .aggregator import VERDICTS
from .pipeline import ProofreadPipeline

state: dict = {}  # holds the loaded pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["pipeline"] = ProofreadPipeline()   # also creates/syncs the database
    yield
    state.clear()


app = FastAPI(title="Proofread API", description="AI-assisted claim review aid", lifespan=lifespan)
# CORS is only needed when the Vite dev server (:5173) talks to the API (:8000).
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


def pipeline() -> ProofreadPipeline:
    return state["pipeline"]


# ------------------------------------------------------------------ request bodies
class ExtractRequest(BaseModel):
    post_text: str = Field(..., min_length=1, max_length=5000)


class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=1000)


class ReviewRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=1000)
    model_verdict: Literal[VERDICTS]
    reviewer_verdict: Literal[VERDICTS]
    note: str = Field("", max_length=2000)


# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health():
    return {"status": "ok", "device": pipeline().device, "database": str(config.DB_PATH.name),
            **db.stats(),
            "models": {"spacy": config.SPACY_MODEL, "embedding": config.EMBEDDING_MODEL,
                       "nli": config.NLI_MODEL}}


@app.get("/references")
def references():
    return db.get_passages()


@app.get("/examples")
def examples():
    """Test claims, used by the frontend's 'Load example' dropdown."""
    return db.get_test_claims()


@app.post("/extract")
def extract(req: ExtractRequest):
    return pipeline().extract(req.post_text)


@app.post("/verify")
def verify(req: VerifyRequest):
    if not req.claim.strip():
        raise HTTPException(status_code=422, detail="Claim is empty.")
    result = pipeline().verify(req.claim)
    db.add_check(result)                      # keep a history of every check
    return result


@app.post("/review")
def review(req: ReviewRequest):
    entry = db.add_review(req.claim, req.model_verdict, req.reviewer_verdict, req.note)
    return {"saved": True, "entry": entry, "total": db.stats()["reviews"]}


@app.get("/review-log")
def review_log():
    return db.get_reviews()


@app.get("/history")
def history(limit: int = 50):
    """Most recent checks first."""
    return db.get_checks(min(max(limit, 1), 500))


@app.get("/stats")
def stats():
    return db.stats()


# ------------------------------------------------------------------ web UI
# Serve the built React app (frontend/dist) from "/". Registered last so the API
# routes above take priority.
if (config.FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse)
    def ui_not_built():
        return ("<h1>Proofread API is running</h1><p>The web UI has not been built yet. "
                "Run <code>./start.sh</code> from the proofread folder, or "
                "<code>npm run build</code> in frontend/.</p><p>API docs: <a href='/docs'>/docs</a></p>")
