"""
api/routes.py
─────────────
All HTTP route handlers. Each handler is a thin layer — no business logic here.
Logic lives in core/store.py, core/graph.py, core/similarity.py.
"""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from core.store import store
from core.graph import graph
from core.tfidf import tfidf_index
from core.watchlist_direct import recommend_direct
from core.watchlist_bfs import recommend_bfs
from core.watchlist_pagerank import recommend_pagerank
from config import DEFAULT_TOP_K
from api.auth import get_current_user, get_optional_user

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


# ── Recommendations ────────────────────────────────────────────────────────────

def _resolve_neighbors(
    neighbors: list[tuple[str, float]],
) -> list[dict]:
    results = []
    for neighbor_id, score in neighbors:
        neighbor = store.get_item(int(neighbor_id))
        if neighbor:
            results.append({**neighbor, "similarity_score": round(score, 4)})
    return results


@router.get(
    "/recommend/jaccard/{tmdb_id}",
    summary="Top-K recommendations — Jaccard similarity (genres/keywords/cast)",
    tags=["recommendations"],
)
def recommend_jaccard(
    tmdb_id: int,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    item = store.get_item(tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {tmdb_id} not found.")

    t0        = time.perf_counter()
    neighbors = graph.neighbors(str(tmdb_id), top_k=k)
    query_ms  = round((time.perf_counter() - t0) * 1000, 3)

    return {
        "algorithm":       "jaccard",
        "query_time_ms":   query_ms,
        "item":            item,
        "recommendations": _resolve_neighbors(neighbors),
    }


@router.get(
    "/recommend/tfidf/{tmdb_id}",
    summary="Top-K recommendations — TF-IDF cosine similarity (overview text)",
    tags=["recommendations"],
)
def recommend_tfidf(
    tmdb_id: int,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    item = store.get_item(tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {tmdb_id} not found.")

    t0        = time.perf_counter()
    neighbors = tfidf_index.neighbors(str(tmdb_id), top_k=k)
    query_ms  = round((time.perf_counter() - t0) * 1000, 3)

    return {
        "algorithm":       "tfidf",
        "query_time_ms":   query_ms,
        "item":            item,
        "recommendations": _resolve_neighbors(neighbors),
    }


@router.get(
    "/recommend/compare/{tmdb_id}",
    summary="Compare Jaccard vs TF-IDF recommendations side by side",
    tags=["recommendations"],
)
def recommend_compare(
    tmdb_id: int,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    item = store.get_item(tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {tmdb_id} not found.")

    id_str = str(tmdb_id)

    t0              = time.perf_counter()
    jaccard_nbrs    = graph.neighbors(id_str, top_k=k)
    jaccard_ms      = round((time.perf_counter() - t0) * 1000, 3)

    t0              = time.perf_counter()
    tfidf_nbrs      = tfidf_index.neighbors(id_str, top_k=k)
    tfidf_ms        = round((time.perf_counter() - t0) * 1000, 3)

    jaccard_ids = {nid for nid, _ in jaccard_nbrs}
    tfidf_ids   = {nid for nid, _ in tfidf_nbrs}
    overlap_ids = jaccard_ids & tfidf_ids

    return {
        "item": item,
        "jaccard": {
            "algorithm":       "jaccard",
            "query_time_ms":   jaccard_ms,
            "recommendations": _resolve_neighbors(jaccard_nbrs),
        },
        "tfidf": {
            "algorithm":       "tfidf",
            "query_time_ms":   tfidf_ms,
            "recommendations": _resolve_neighbors(tfidf_nbrs),
        },
        "overlap": {
            "count": len(overlap_ids),
            "ids":   sorted(overlap_ids),
        },
    }


@router.get(
    "/recommend/{tmdb_id}",
    summary="Top-K recommendations — Jaccard (default)",
    tags=["recommendations"],
)
def recommend_single(
    tmdb_id: int,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    """Alias for /recommend/jaccard/{tmdb_id} — kept for backwards compatibility."""
    return recommend_jaccard(tmdb_id, k)


def _resolve_watchlist_neighbors(ranked: list[tuple[str, float]]) -> list[dict]:
    results = []
    for item_id, score in ranked:
        item = store.get_item(int(item_id))
        if item:
            results.append({**item, "score": round(score, 6)})
    return results


# ── Watchlist CRUD ─────────────────────────────────────────────────────────────

class WatchlistAddBody(BaseModel):
    tmdb_id: int
    media_type: str  # "movie" | "show"


@router.get(
    "/watchlist",
    summary="Get the authenticated user's watchlist",
    tags=["watchlist"],
)
def get_watchlist(user: dict = Depends(get_current_user)):
    from core.supabase_client import get_supabase
    client = get_supabase()
    user_id = user["sub"]

    resp = client.table("watchlists") \
        .select("tmdb_id, media_type, added_at") \
        .eq("user_id", user_id) \
        .order("added_at", desc=True) \
        .execute()

    items = []
    for row in resp.data:
        tmdb_id = row["tmdb_id"]
        if row["media_type"] == "movie":
            item = store.get_movie(tmdb_id)
        else:
            item = store.get_show(tmdb_id)
        if item:
            items.append({**item, "added_at": row["added_at"]})

    return {"count": len(items), "items": items}


@router.post(
    "/watchlist",
    summary="Add an item to the authenticated user's watchlist",
    tags=["watchlist"],
)
def add_to_watchlist(body: WatchlistAddBody, user: dict = Depends(get_current_user)):
    if body.media_type not in ("movie", "show"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie' or 'show'.")

    # Verify item exists in store
    if body.media_type == "movie":
        item = store.get_movie(body.tmdb_id)
    else:
        item = store.get_show(body.tmdb_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{body.media_type} {body.tmdb_id} not found.")

    from core.supabase_client import get_supabase
    client = get_supabase()

    client.table("watchlists").upsert({
        "user_id":    user["sub"],
        "tmdb_id":    body.tmdb_id,
        "media_type": body.media_type,
    }, on_conflict="user_id,tmdb_id,media_type").execute()

    return {"status": "added", "tmdb_id": body.tmdb_id, "media_type": body.media_type}


@router.delete(
    "/watchlist/{tmdb_id}",
    summary="Remove an item from the authenticated user's watchlist",
    tags=["watchlist"],
)
def remove_from_watchlist(
    tmdb_id: int,
    media_type: str = Query(..., description="movie or show"),
    user: dict = Depends(get_current_user),
):
    if media_type not in ("movie", "show"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie' or 'show'.")

    from core.supabase_client import get_supabase
    client = get_supabase()

    client.table("watchlists") \
        .delete() \
        .eq("user_id", user["sub"]) \
        .eq("tmdb_id", tmdb_id) \
        .eq("media_type", media_type) \
        .execute()

    return {"status": "removed", "tmdb_id": tmdb_id, "media_type": media_type}


@router.delete(
    "/watchlist",
    summary="Clear the authenticated user's entire watchlist",
    tags=["watchlist"],
)
def clear_watchlist(user: dict = Depends(get_current_user)):
    from core.supabase_client import get_supabase
    client = get_supabase()

    client.table("watchlists") \
        .delete() \
        .eq("user_id", user["sub"]) \
        .execute()

    return {"status": "cleared"}


# ── Watchlist Recommendations ──────────────────────────────────────────────────

def _resolve_watchlist_ids(
    tmdb_ids: Optional[list[int]],
    user: Optional[dict],
) -> list[int]:
    """Get watchlist IDs from body or from DB if user is authenticated + empty body."""
    if tmdb_ids:
        return tmdb_ids
    if not user:
        raise HTTPException(status_code=400, detail="Watchlist cannot be empty.")

    from core.supabase_client import get_supabase
    client = get_supabase()
    resp = client.table("watchlists") \
        .select("tmdb_id") \
        .eq("user_id", user["sub"]) \
        .execute()

    ids = [row["tmdb_id"] for row in resp.data]
    if not ids:
        raise HTTPException(status_code=400, detail="Your watchlist is empty.")
    return ids


@router.post(
    "/recommend/watchlist",
    summary="Top-K recommendations for a watchlist — direct aggregation (backwards compat)",
    tags=["recommendations"],
)
def recommend_watchlist(
    tmdb_ids: list[int],
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
):
    if not tmdb_ids:
        raise HTTPException(status_code=400, detail="Watchlist cannot be empty.")

    ranked = recommend_direct(graph.adjacency_list, [str(i) for i in tmdb_ids], top_k=k)

    results = []
    for neighbor_id, agg_score in ranked:
        item = store.get_item(int(neighbor_id))
        if item:
            results.append({**item, "aggregated_score": round(agg_score, 4)})

    return {"watchlist_size": len(tmdb_ids), "recommendations": results}


@router.post(
    "/recommend/watchlist/direct",
    summary="Watchlist recommendations — direct aggregation",
    tags=["recommendations"],
)
def recommend_watchlist_direct(
    tmdb_ids: Optional[list[int]] = None,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
    user: Optional[dict] = Depends(get_optional_user),
):
    ids = _resolve_watchlist_ids(tmdb_ids, user)

    t0     = time.perf_counter()
    ranked = recommend_direct(graph.adjacency_list, [str(i) for i in ids], top_k=k)
    ms     = round((time.perf_counter() - t0) * 1000, 3)

    return {
        "algorithm":       "direct",
        "watchlist_size":  len(ids),
        "recommendations": _resolve_watchlist_neighbors(ranked),
        "query_time_ms":   ms,
    }


@router.post(
    "/recommend/watchlist/bfs",
    summary="Watchlist recommendations — BFS depth-2",
    tags=["recommendations"],
)
def recommend_watchlist_bfs(
    tmdb_ids: Optional[list[int]] = None,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
    user: Optional[dict] = Depends(get_optional_user),
):
    ids = _resolve_watchlist_ids(tmdb_ids, user)

    t0     = time.perf_counter()
    ranked = recommend_bfs(graph.adjacency_list, [str(i) for i in ids], top_k=k)
    ms     = round((time.perf_counter() - t0) * 1000, 3)

    return {
        "algorithm":       "bfs",
        "watchlist_size":  len(ids),
        "recommendations": _resolve_watchlist_neighbors(ranked),
        "query_time_ms":   ms,
    }


@router.post(
    "/recommend/watchlist/pagerank",
    summary="Watchlist recommendations — Personalized PageRank",
    tags=["recommendations"],
)
def recommend_watchlist_pagerank(
    tmdb_ids: Optional[list[int]] = None,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
    user: Optional[dict] = Depends(get_optional_user),
):
    ids = _resolve_watchlist_ids(tmdb_ids, user)

    t0     = time.perf_counter()
    ranked = recommend_pagerank(graph.adjacency_list, [str(i) for i in ids], top_k=k)
    ms     = round((time.perf_counter() - t0) * 1000, 3)

    return {
        "algorithm":       "pagerank",
        "watchlist_size":  len(ids),
        "recommendations": _resolve_watchlist_neighbors(ranked),
        "query_time_ms":   ms,
    }


@router.post(
    "/recommend/watchlist/compare",
    summary="Compare all three watchlist algorithms side by side",
    tags=["recommendations"],
)
def recommend_watchlist_compare(
    tmdb_ids: Optional[list[int]] = None,
    k: int = Query(DEFAULT_TOP_K, ge=1, le=50),
    user: Optional[dict] = Depends(get_optional_user),
):
    ids = _resolve_watchlist_ids(tmdb_ids, user)

    adj  = graph.adjacency_list
    id_strs = [str(i) for i in ids]

    t0         = time.perf_counter()
    direct_r   = recommend_direct(adj, id_strs, top_k=k)
    direct_ms  = round((time.perf_counter() - t0) * 1000, 3)

    t0         = time.perf_counter()
    bfs_r      = recommend_bfs(adj, id_strs, top_k=k)
    bfs_ms     = round((time.perf_counter() - t0) * 1000, 3)

    t0         = time.perf_counter()
    pr_r       = recommend_pagerank(adj, id_strs, top_k=k)
    pr_ms      = round((time.perf_counter() - t0) * 1000, 3)

    direct_ids  = {r[0] for r in direct_r}
    bfs_ids     = {r[0] for r in bfs_r}
    pr_ids      = {r[0] for r in pr_r}
    all_three   = direct_ids & bfs_ids & pr_ids

    return {
        "watchlist_size": len(ids),
        "direct": {
            "algorithm":       "direct",
            "query_time_ms":   direct_ms,
            "recommendations": _resolve_watchlist_neighbors(direct_r),
        },
        "bfs": {
            "algorithm":       "bfs",
            "query_time_ms":   bfs_ms,
            "recommendations": _resolve_watchlist_neighbors(bfs_r),
        },
        "pagerank": {
            "algorithm":       "pagerank",
            "query_time_ms":   pr_ms,
            "recommendations": _resolve_watchlist_neighbors(pr_r),
        },
        "overlap": {
            "all_three":       len(all_three),
            "direct_bfs":      len(direct_ids & bfs_ids),
            "direct_pagerank": len(direct_ids & pr_ids),
            "bfs_pagerank":    len(bfs_ids & pr_ids),
            "ids_all_three":   sorted(all_three),
        },
    }


# ── Cold Start ────────────────────────────────────────────────────────────────

class ColdStartRequest(BaseModel):
    q1_media_type: str
    q2_genres:     str
    q3_title:      str
    q4_dark:       str
    q5_familiar:   str
    k: int = DEFAULT_TOP_K


@router.post(
    "/recommend/coldstart",
    summary="Cold-start recommendations — LLM taste extraction + BFS",
    tags=["recommendations"],
)
def recommend_coldstart(
    body: ColdStartRequest,
    user: Optional[dict] = Depends(get_optional_user),
) -> dict:
    from core.coldstart import get_coldstart_recommendations, UserAnswers
    from core.supabase_client import get_supabase

    t0      = time.perf_counter()
    answers = UserAnswers(
        q1_media_type=body.q1_media_type,
        q2_genres=body.q2_genres,
        q3_title=body.q3_title,
        q4_dark=body.q4_dark,
        q5_familiar=body.q5_familiar,
    )

    # Create job row if user is authenticated
    job_id = None
    if user:
        client = get_supabase()
        job_resp = client.table("cold_start_jobs").insert({
            "user_id": user["sub"],
            "status": "running",
            "answers": {
                "q1_media_type": body.q1_media_type,
                "q2_genres": body.q2_genres,
                "q3_title": body.q3_title,
                "q4_dark": body.q4_dark,
                "q5_familiar": body.q5_familiar,
            },
            "started_at": "now()",
        }).execute()
        job_id = job_resp.data[0]["id"] if job_resp.data else None

    try:
        result   = get_coldstart_recommendations(answers, top_k=body.k)
        query_ms = round((time.perf_counter() - t0) * 1000, 3)

        seed_items = [
            store.get_item(int(sid))
            for sid in result.seed_ids
            if store.get_item(int(sid))
        ]

        response = {
            "algorithm":     "coldstart_bfs",
            "query_time_ms": query_ms,
            "llm_time_ms":   result.llm_time_ms,
            "signals": {
                "genres":           result.signals.genres,
                "keywords":         result.signals.keywords,
                "reference_titles": result.signals.reference_titles,
                "mood":             result.signals.mood,
            },
            "seeds":       seed_items,
            "token_cost": {
                "input_tokens":  result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            "recommendations": _resolve_watchlist_neighbors(result.recommendations),
        }

        # Update job to completed
        if job_id:
            client.table("cold_start_jobs").update({
                "status": "completed",
                "signals": response["signals"],
                "seed_ids": result.seed_ids,
                "recommendations": [
                    {"tmdb_id": r["id"], "score": r["score"]}
                    for r in response["recommendations"]
                ],
                "token_cost": response["token_cost"],
                "llm_time_ms": result.llm_time_ms,
                "total_time_ms": query_ms,
                "completed_at": "now()",
            }).eq("id", job_id).execute()

        return response

    except Exception as e:
        # Update job to failed
        if job_id:
            client.table("cold_start_jobs").update({
                "status": "failed",
                "error_message": str(e),
                "completed_at": "now()",
            }).eq("id", job_id).execute()
        raise


# ── Graph / index stats ────────────────────────────────────────────────────────

@router.get("/graph/stats", summary="Build statistics for both indexes", tags=["graph"])
def graph_stats():
    return {
        "jaccard": graph.stats(),
        "tfidf":   tfidf_index.stats(),
    }


# ── Dataset stats ──────────────────────────────────────────────────────────────

@router.get("/stats", summary="Dataset statistics", tags=["meta"])
def stats():
    return store.stats()
