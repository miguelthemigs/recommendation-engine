"""
scripts/tmdb_client.py
──────────────────────
All raw TMDB HTTP calls live here — nothing else imports requests directly.
Every function returns plain Python dicts/lists or None on failure.

If you ever swap TMDB for another API, only this file changes.
"""

import time
import requests
from config import TMDB_API_KEY, TMDB_BASE_URL, TMDB_LANGUAGE


# ── Base request ───────────────────────────────────────────────────────────────

def _get(path: str, extra_params: dict = {}) -> dict | None:
    """
    Makes a single GET request to TMDB.
    Returns parsed JSON or None on any failure.
    Adds a small sleep to stay within the 40 req/s free-tier limit.
    """
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY is not set. Check your .env file.")

    url    = f"{TMDB_BASE_URL}{path}"
    params = {
        "api_key":  TMDB_API_KEY,
        "language": TMDB_LANGUAGE,
        **extra_params,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        time.sleep(0.05)   # ~20 req/s — well within free tier
        return response.json()
    except requests.HTTPError as e:
        print(f"  [HTTP {response.status_code}] {path}: {e}")
        return None
    except requests.RequestException as e:
        print(f"  [ERROR] {path}: {e}")
        return None


# ── Genre maps ─────────────────────────────────────────────────────────────────

def get_movie_genres() -> dict[int, str]:
    """
    Returns {genre_id: genre_name} for movies in English.
    Example: {28: "Action", 18: "Drama", ...}
    """
    data = _get("/genre/movie/list")
    if not data:
        return {}
    return {g["id"]: g["name"] for g in data.get("genres", [])}


def get_tv_genres() -> dict[int, str]:
    """
    Returns {genre_id: genre_name} for TV shows in English.
    Note: TV genre IDs differ from movie genre IDs (e.g. no "Action" — it's "Action & Adventure").
    Example: {10759: "Action & Adventure", 18: "Drama", ...}
    """
    data = _get("/genre/tv/list")
    if not data:
        return {}
    return {g["id"]: g["name"] for g in data.get("genres", [])}


# ── Discover (paginated lists) ─────────────────────────────────────────────────

def discover_movies(page: int = 1) -> list[dict]:
    """
    Returns one page of popular movies (20 items).
    Filters out obscure titles with < 100 votes.
    """
    data = _get("/discover/movie", {
        "sort_by":        "popularity.desc",
        "page":           page,
        "vote_count.gte": 100,
        "include_adult":  False,
    })
    return data.get("results", []) if data else []


def discover_shows(page: int = 1) -> list[dict]:
    """
    Returns one page of popular TV shows (20 items).
    Filters out obscure titles with < 50 votes.
    """
    data = _get("/discover/tv", {
        "sort_by":        "popularity.desc",
        "page":           page,
        "vote_count.gte": 50,
        "include_adult":  False,
    })
    return data.get("results", []) if data else []


# ── Per-item detail endpoints ──────────────────────────────────────────────────

def get_movie_keywords(tmdb_id: int) -> list[str]:
    """
    Returns keyword strings for a movie.
    TMDB endpoint: /movie/{id}/keywords → { keywords: [{id, name}, ...] }
    """
    data = _get(f"/movie/{tmdb_id}/keywords")
    if not data:
        return []
    return [kw["name"] for kw in data.get("keywords", [])]


def get_tv_keywords(tmdb_id: int) -> list[str]:
    """
    Returns keyword strings for a TV show.
    TMDB endpoint: /tv/{id}/keywords → { results: [{id, name}, ...] }
    Note: TV uses "results" key, movies use "keywords" key — TMDB inconsistency.
    """
    data = _get(f"/tv/{tmdb_id}/keywords")
    if not data:
        return []
    return [kw["name"] for kw in data.get("results", [])]


def get_movie_cast(tmdb_id: int, top_n: int = 5) -> list[str]:
    """
    Returns the top-N cast member names for a movie, sorted by billing order.
    """
    data = _get(f"/movie/{tmdb_id}/credits")
    if not data:
        return []
    cast = sorted(data.get("cast", []), key=lambda x: x.get("order", 999))
    return [m["name"] for m in cast[:top_n]]


def get_tv_cast(tmdb_id: int, top_n: int = 5) -> list[str]:
    """
    Returns the top-N cast member names for a TV show, sorted by billing order.
    """
    data = _get(f"/tv/{tmdb_id}/credits")
    if not data:
        return []
    cast = sorted(data.get("cast", []), key=lambda x: x.get("order", 999))
    return [m["name"] for m in cast[:top_n]]
