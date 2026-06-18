"""
main.py
───────
FastAPI entry point.

Startup sequence:
  1. store.load()  → reads data/movies.json + data/shows.json into RAM
  2. graph ready   → Step 3 will call graph.build(store.all_items()) here

Run:
    uvicorn main:app --reload
Then visit: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS, ALLOWED_ORIGIN_REGEX
from core.store import store
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Step 1: load cached data into memory ──────────────────────────────────
    store.load()

    # ── Step 3: build similarity graph (Jaccard) ──────────────────────────────
    from core.graph import graph
    graph.build(store.all_items())

    # ── TF-IDF index (overview cosine similarity) ──────────────────────────────
    from core.tfidf import tfidf_index
    tfidf_index.build(store.all_items())

    yield


app = FastAPI(
    title="TV/Movie Recommendation Engine",
    description="""
Graph-based recommendation engine for movies and TV shows.
""",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
def health():
    """Liveness probe — the process is up and the store is loaded."""
    s = store.stats()
    return {
        "status":        "ok",
        "movies_loaded": s["total_movies"],
        "shows_loaded":  s["total_shows"],
    }


@app.get("/ready", tags=["meta"])
def ready(response: Response):
    """
    Readiness probe — returns 200 only once BOTH the Jaccard graph and the
    TF-IDF index have finished building (the ~30-60s startup work). Until then
    returns 503 so k8s keeps the pod out of the Service. Unlike /graph/stats
    (which returns 200 even when "not built"), this is a real readiness gate.
    """
    from core.graph import graph
    from core.tfidf import tfidf_index

    g = graph.stats()
    t = tfidf_index.stats()
    ok = g.get("status") == "ready" and t.get("status") == "ready"
    if not ok:
        response.status_code = 503
    return {"ready": ok, "jaccard": g, "tfidf": t}
