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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
def health():
    s = store.stats()
    return {
        "status":        "ok",
        "movies_loaded": s["total_movies"],
        "shows_loaded":  s["total_shows"],
    }
