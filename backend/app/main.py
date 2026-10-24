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

from . import config, db, importer
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


def db_call(fn, *args, **kwargs):
    """Run a database function, turning its errors into clear HTTP errors."""
    try:
        return fn(*args, **kwargs)
    except db.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except db.ReadOnly as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------ request bodies
class ExtractRequest(BaseModel):
    post_text: str = Field(..., min_length=1, max_length=5000)


class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=1000)
    collection_id: str | None = None          # None = check against all topics


class ReviewRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=1000)
    model_verdict: Literal[VERDICTS]
    reviewer_verdict: Literal[VERDICTS]
    note: str = Field("", max_length=2000)
    collection_id: str | None = None


class CollectionRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: str = Field("", max_length=500)


class PassageIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    source: str = Field(..., min_length=1, max_length=120)
    url: str = Field("", max_length=2000)
    date: str = Field("", max_length=40)
    text: str = Field(..., min_length=20, max_length=3000)


class AddPassagesRequest(BaseModel):
    collection_id: str
    passages: list[PassageIn] = Field(..., min_length=1, max_length=200)


class PassageUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=300)
    source: str | None = Field(None, min_length=1, max_length=120)
    url: str | None = Field(None, max_length=2000)
    date: str | None = Field(None, max_length=40)
    text: str | None = Field(None, min_length=20, max_length=3000)


class ImportUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)


class ImportTextRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=100_000)
    title: str = Field(..., min_length=2, max_length=300)
    source: str = Field(..., min_length=1, max_length=120)
    url: str = Field("", max_length=2000)
    date: str = Field("", max_length=40)


# ------------------------------------------------------------------ status
@app.get("/health")
def health():
    return {"status": "ok", "device": pipeline().device, "database": str(config.DB_PATH.name),
            **db.stats(),
            "models": {"spacy": config.SPACY_MODEL, "embedding": config.EMBEDDING_MODEL,
                       "nli": config.NLI_MODEL}}


@app.get("/stats")
def stats():
    return db.stats()


# ------------------------------------------------------------------ topics (collections)
@app.get("/collections")
def collections():
    return db.get_collections()


@app.post("/collections")
def create_collection(req: CollectionRequest):
    return db_call(db.create_collection, req.name, req.description)


@app.delete("/collections/{collection_id}")
def delete_collection(collection_id: str):
    db_call(db.delete_collection, collection_id)
    return {"deleted": collection_id}


# ------------------------------------------------------------------ reference passages
@app.get("/references")
def references(collection_id: str | None = None):
    return db.get_passages(collection_id)


@app.post("/references")
def add_references(req: AddPassagesRequest):
    return db_call(db.add_passages, req.collection_id, [p.model_dump() for p in req.passages])


@app.put("/references/{passage_id}")
def update_reference(passage_id: str, req: PassageUpdate):
    return db_call(db.update_passage, passage_id, req.model_dump(exclude_none=True))


@app.delete("/references/{passage_id}")
def delete_reference(passage_id: str):
    db_call(db.delete_passage, passage_id)
    return {"deleted": passage_id}


@app.post("/import/url")
def import_url(req: ImportUrlRequest):
    """Download a page and split it into passages. PREVIEW only: nothing is saved."""
    try:
        return importer.preview_from_url(pipeline().nlp, req.url)
    except importer.ImportError_ as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/import/text")
def import_text(req: ImportTextRequest):
    """Split pasted text into passages. PREVIEW only: nothing is saved."""
    try:
        return importer.preview_from_text(pipeline().nlp, req.text, req.title, req.source, req.url, req.date)
    except importer.ImportError_ as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------------ claim checking
@app.get("/examples")
def examples(collection_id: str | None = None):
    """Test claims, used by the frontend's 'Load example' dropdown."""
    return db.get_test_claims(collection_id)


@app.post("/extract")
def extract(req: ExtractRequest):
    return pipeline().extract(req.post_text)


@app.post("/verify")
def verify(req: VerifyRequest):
    if not req.claim.strip():
        raise HTTPException(status_code=422, detail="Claim is empty.")
    if req.collection_id:
        db_call(db.get_collection, req.collection_id)     # 404 if the topic doesn't exist
    result = pipeline().verify(req.claim, req.collection_id)
    db.add_check(result, req.collection_id)              # keep a history of every check
    return result


@app.post("/review")
def review(req: ReviewRequest):
    entry = db.add_review(req.claim, req.model_verdict, req.reviewer_verdict, req.note, req.collection_id)
    return {"saved": True, "entry": entry, "total": db.stats()["reviews"]}


@app.get("/review-log")
def review_log():
    return db.get_reviews()


@app.get("/history")
def history(limit: int = 50):
    """Most recent checks first."""
    return db.get_checks(min(max(limit, 1), 500))


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
