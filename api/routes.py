"""
api/routes.py
─────────────
All HTTP route handlers. Each handler is a thin layer — no business logic here.
Logic lives in core/store.py, core/graph.py, core/similarity.py.
"""

from fastapi import APIRouter, HTTPException, Query
from core.store import store
from core.graph import graph
from config import DEFAULT_TOP_K

router = APIRouter()


# ── Movies ─────────────────────────────────────────────────────────────────────

@router.get("/movies", summary="List all cached movies", tags=["movies"])
def list_movies(
    limit:  int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0,  ge=0,         description="Pagination offset"),
):
    all_movies = sorted(store.all_movies(), key=lambda x: x.get("popularity", 0), reverse=True)
    return {
        "total":  len(all_movies),
        "offset": offset,
        "limit":  limit,
        "items":  all_movies[offset : offset + limit],
    }


@router.get("/movies/genres", summary="List all movie genres", tags=["movies"])
def movie_genres():
    """Returns the full genre map used when fetching movies from TMDB."""
    return store.movie_genres()


@router.get("/movies/{tmdb_id}", summary="Get a single movie", tags=["movies"])
def get_movie(tmdb_id: int):
    item = store.get_movie(tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Movie {tmdb_id} not found in cache.")
    return item


# ── TV Shows ───────────────────────────────────────────────────────────────────

@router.get("/shows", summary="List all cached TV shows", tags=["shows"])
def list_shows(
    limit:  int = Query(50, ge=1, le=500),
    offset: int = Query(0,  ge=0),
):
    all_shows = sorted(store.all_shows(), key=lambda x: x.get("popularity", 0), reverse=True)
    return {
        "total":  len(all_shows),
        "offset": offset,
        "limit":  limit,
        "items":  all_shows[offset : offset + limit],
    }


@router.get("/shows/genres", summary="List all TV show genres", tags=["shows"])
def show_genres():
    """Returns the full genre map used when fetching TV shows from TMDB."""
    return store.tv_genres()


@router.get("/shows/{tmdb_id}", summary="Get a single TV show", tags=["shows"])
def get_show(tmdb_id: int):
    item = store.get_show(tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Show {tmdb_id} not found in cache.")
    return item


# ── Search ─────────────────────────────────────────────────────────────────────

@router.get("/search", summary="Search by title", tags=["search"])
def search(
    q:     str = Query(..., min_length=1, description="Title substring"),
    type:  str = Query("all", description="Filter: movie | show | all"),
    limit: int = Query(20, ge=1, le=100),
):
    if type not in {"movie", "show", "all"}:
        raise HTTPException(status_code=400, detail="'type' must be: movie | show | all")
    results = store.search(query=q, item_type=type, limit=limit)
    return {"query": q, "type": type, "count": len(results), "results": results}


# ── Recommendations (active after Step 3) ─────────────────────────────────────

@router.get(
    "/recommend/{tmdb_id}",
    summary="Top-K recommendations for a single item [Step 3]",
    tags=["recommendations"],
)
def recommend_single(
    tmdb_id: int,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    """
    Returns the K most similar items to the given movie/show.
    Requires the graph to be built (Step 3).
    """
    item = store.get_item(tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {tmdb_id} not found.")

    try:
        neighbors = graph.neighbors(str(tmdb_id), top_k=k)
    except NotImplementedError:
        raise HTTPException(status_code=503, detail="Graph not built yet — complete Step 3 first.")

    results = []
    for neighbor_id, score in neighbors:
        neighbor = store.get_item(int(neighbor_id))
        if neighbor:
            results.append({**neighbor, "similarity_score": score})

    return {"item": item, "recommendations": results}


@router.post(
    "/recommend/watchlist",
    summary="Top-K recommendations for a watchlist [Step 4]",
    tags=["recommendations"],
)
def recommend_watchlist(
    tmdb_ids: list[int],
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    """
    Given a list of TMDB IDs, returns aggregated Top-K recommendations.
    Items appearing as neighbors of multiple watchlist entries are ranked higher.
    Requires the graph (Step 3) and watchlist aggregation (Step 4).
    """
    if not tmdb_ids:
        raise HTTPException(status_code=400, detail="Watchlist cannot be empty.")

    try:
        ranked = graph.neighbors_for_watchlist([str(i) for i in tmdb_ids], top_k=k)
    except NotImplementedError:
        raise HTTPException(status_code=503, detail="Watchlist recommendations not built yet — complete Step 4 first.")

    results = []
    for neighbor_id, agg_score in ranked:
        item = store.get_item(int(neighbor_id))
        if item:
            results.append({**item, "aggregated_score": round(agg_score, 4)})

    return {"watchlist_size": len(tmdb_ids), "recommendations": results}


# ── Graph stats ────────────────────────────────────────────────────────────────

@router.get("/graph/stats", summary="Graph build statistics [Step 3]", tags=["graph"])
def graph_stats():
    return graph.stats()


# ── Dataset stats ──────────────────────────────────────────────────────────────

@router.get("/stats", summary="Dataset statistics", tags=["meta"])
def stats():
    return store.stats()
