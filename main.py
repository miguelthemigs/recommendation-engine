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
from core.store import store
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Step 1: load cached data into memory ──────────────────────────────────
    store.load()

    # ── Step 3 (TODO): build similarity graph ─────────────────────────────────
    # Uncomment once core/similarity.py and core/graph.py are implemented:
    # from core.graph import graph
    # graph.build(store.all_items())

    yield


app = FastAPI(
    title="TV/Movie Recommendation Engine",
    description="""
Graph-based recommendation engine for movies and TV shows.

**Steps:**
- ✅ Step 1 — Data ingestion & local cache (current)
- 🔲 Step 2 — Similarity scoring (Jaccard)
- 🔲 Step 3 — Graph building (adjacency list)
- 🔲 Step 4 — Watchlist recommendations
- 🔲 Step 5 — Performance analysis
""",
    version="0.1.0",
    lifespan=lifespan,
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
