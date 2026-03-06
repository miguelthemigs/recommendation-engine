"""
scripts/fetch_tmdb.py
─────────────────────
Run this ONCE to populate your local data/ cache.
After this, the API never calls TMDB again — it serves from JSON files.

    python scripts/fetch_tmdb.py

Output:
    data/genres.json   ← genre maps for movies and TV (used to decode IDs)
    data/movies.json   ← { "<tmdb_id>": { ...item }, ... }
    data/shows.json    ← { "<tmdb_id>": { ...item }, ... }
"""

import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config import (
    TMDB_PAGES_TO_FETCH, TOP_CAST_COUNT,
    MOVIES_CACHE, SHOWS_CACHE, GENRES_CACHE,
)
from scripts.tmdb_client import (
    get_movie_genres, get_tv_genres,
    discover_movies, discover_shows,
    get_movie_keywords, get_tv_keywords,
    get_movie_cast, get_tv_cast,
)


# ── Data model ─────────────────────────────────────────────────────────────────

def normalize_movie(raw: dict, genres_map: dict[int, str]) -> dict:
    """
    Converts a raw TMDB movie result into our clean schema.
    Fields are chosen specifically for similarity scoring later.
    """
    date_str = raw.get("release_date", "") or ""
    genres   = [genres_map.get(gid, "Unknown") for gid in raw.get("genre_ids", [])]

    return {
        "id":           raw["id"],
        "type":         "movie",
        "title":        raw.get("title", "Unknown"),
        "year":         int(date_str[:4]) if date_str else None,
        "overview":     raw.get("overview", ""),
        "genres":       genres,
        "keywords":     [],        # populated in enrichment pass
        "cast":         [],        # populated in enrichment pass
        "vote_average": raw.get("vote_average", 0.0),
        "popularity":   raw.get("popularity", 0.0),
        "poster_path":  raw.get("poster_path"),
    }


def normalize_show(raw: dict, genres_map: dict[int, str]) -> dict:
    """
    Converts a raw TMDB TV show result into our clean schema.
    Same shape as movies so they can live in the same graph later.
    """
    date_str = raw.get("first_air_date", "") or ""
    genres   = [genres_map.get(gid, "Unknown") for gid in raw.get("genre_ids", [])]

    return {
        "id":           raw["id"],
        "type":         "show",
        "title":        raw.get("name", "Unknown"),
        "year":         int(date_str[:4]) if date_str else None,
        "overview":     raw.get("overview", ""),
        "genres":       genres,
        "keywords":     [],
        "cast":         [],
        "vote_average": raw.get("vote_average", 0.0),
        "popularity":   raw.get("popularity", 0.0),
        "poster_path":  raw.get("poster_path"),
    }


# ── Fetch helpers ──────────────────────────────────────────────────────────────

def fetch_all_movies(genres_map: dict[int, str]) -> dict[str, dict]:
    """Pages through discover/movie and returns a dict keyed by string TMDB ID."""
    results: dict[str, dict] = {}

    print(f"\n{'='*50}")
    print(f"  Fetching movies — {TMDB_PAGES_TO_FETCH} pages")
    print(f"{'='*50}")

    for page in range(1, TMDB_PAGES_TO_FETCH + 1):
        raw_list = discover_movies(page)
        if not raw_list:
            print(f"  [WARN] Empty page {page}, stopping.")
            break
        for raw in raw_list:
            item = normalize_movie(raw, genres_map)
            results[str(item["id"])] = item
        print(f"  Page {page:>2}/{TMDB_PAGES_TO_FETCH} — {len(results)} movies so far")

    return results


def fetch_all_shows(genres_map: dict[int, str]) -> dict[str, dict]:
    """Pages through discover/tv and returns a dict keyed by string TMDB ID."""
    results: dict[str, dict] = {}

    print(f"\n{'='*50}")
    print(f"  Fetching TV shows — {TMDB_PAGES_TO_FETCH} pages")
    print(f"{'='*50}")

    for page in range(1, TMDB_PAGES_TO_FETCH + 1):
        raw_list = discover_shows(page)
        if not raw_list:
            print(f"  [WARN] Empty page {page}, stopping.")
            break
        for raw in raw_list:
            item = normalize_show(raw, genres_map)
            results[str(item["id"])] = item
        print(f"  Page {page:>2}/{TMDB_PAGES_TO_FETCH} — {len(results)} shows so far")

    return results


def enrich_movies(movies: dict[str, dict]) -> None:
    """
    Second pass: adds keywords and cast to each movie in-place.
    Separate from discover so we can checkpoint easily.
    """
    total = len(movies)
    print(f"\n  Enriching {total} movies with keywords & cast...")

    for i, item in enumerate(movies.values(), 1):
        tmdb_id          = item["id"]
        item["keywords"] = get_movie_keywords(tmdb_id)
        item["cast"]     = get_movie_cast(tmdb_id, TOP_CAST_COUNT)

        if i % 25 == 0 or i == total:
            print(f"    {i}/{total}")


def enrich_shows(shows: dict[str, dict]) -> None:
    """
    Second pass: adds keywords and cast to each show in-place.
    """
    total = len(shows)
    print(f"\n  Enriching {total} shows with keywords & cast...")

    for i, item in enumerate(shows.values(), 1):
        tmdb_id          = item["id"]
        item["keywords"] = get_tv_keywords(tmdb_id)
        item["cast"]     = get_tv_cast(tmdb_id, TOP_CAST_COUNT)

        if i % 25 == 0 or i == total:
            print(f"    {i}/{total}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    print("TMDB Data Fetcher")
    print(f"Pages : {TMDB_PAGES_TO_FETCH} per type (~{TMDB_PAGES_TO_FETCH * 20} items each)")
    print(f"Cast  : top {TOP_CAST_COUNT} per item\n")

    # 1. Fetch and save genre maps
    print("Fetching genre maps...")
    movie_genres = get_movie_genres()
    tv_genres    = get_tv_genres()
    genres_data  = {"movie": movie_genres, "tv": tv_genres}

    with open(GENRES_CACHE, "w", encoding="utf-8") as f:
        json.dump(genres_data, f, indent=2)
    print(f"✓ Saved genre maps → {GENRES_CACHE}")
    print(f"  Movie genres : {len(movie_genres)} ({', '.join(list(movie_genres.values())[:5])}...)")
    print(f"  TV genres    : {len(tv_genres)} ({', '.join(list(tv_genres.values())[:5])}...)")

    # 2. Fetch movies
    movies = fetch_all_movies(movie_genres)
    enrich_movies(movies)
    with open(MOVIES_CACHE, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Saved {len(movies)} movies → {MOVIES_CACHE}")

    # 3. Fetch TV shows
    shows = fetch_all_shows(tv_genres)
    enrich_shows(shows)
    with open(SHOWS_CACHE, "w", encoding="utf-8") as f:
        json.dump(shows, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {len(shows)} shows → {SHOWS_CACHE}")

    print("\n✓ All done. Run: uvicorn main:app --reload")


if __name__ == "__main__":
    main()
