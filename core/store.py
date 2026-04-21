"""
core/store.py
─────────────
In-memory data store. Loads from Supabase at startup (falls back to JSON).
All API requests are served from RAM — zero disk/network I/O per request.
"""

import json
from pathlib import Path
from typing import Optional
from config import MOVIES_CACHE, SHOWS_CACHE, GENRES_CACHE, SUPABASE_URL


class MediaStore:

    def __init__(self) -> None:
        self._movies:       dict[str, dict] = {}
        self._shows:        dict[str, dict] = {}
        self._movie_genres: dict[str, str]  = {}   # { "28": "Action", "18": "Drama", ... }
        self._tv_genres:    dict[str, str]  = {}   # { "10759": "Action & Adventure", ... }

    # ── Startup ────────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Called once at FastAPI startup. Loads from Supabase if configured, else JSON."""
        if SUPABASE_URL:
            self._load_from_supabase()
        else:
            self._load_from_json()
        print(f"[store] {len(self._movies)} movies | {len(self._shows)} shows loaded.")
        print(f"[store] {len(self._movie_genres)} movie genres | {len(self._tv_genres)} TV genres loaded.")

    def _load_from_supabase(self) -> None:
        """Fetch all movies, shows, and genres from Supabase Postgres."""
        from core.supabase_client import get_supabase

        client = get_supabase()
        print("[store] Loading from Supabase...")

        # Movies
        resp = client.table("movies").select("*").execute()
        for row in resp.data:
            item = self._row_to_item(row, "movie")
            self._movies[str(item["id"])] = item

        # Shows
        resp = client.table("shows").select("*").execute()
        for row in resp.data:
            item = self._row_to_item(row, "show")
            self._shows[str(item["id"])] = item

        # Genres
        resp = client.table("genres").select("*").execute()
        for row in resp.data:
            if row["category"] == "movie":
                self._movie_genres[row["tmdb_id"]] = row["name"]
            elif row["category"] == "tv":
                self._tv_genres[row["tmdb_id"]] = row["name"]

    @staticmethod
    def _row_to_item(row: dict, media_type: str) -> dict:
        """Convert a Supabase row back to the in-memory dict shape."""
        return {
            "id":           row["tmdb_id"],
            "type":         media_type,
            "title":        row["title"],
            "year":         row["year"],
            "overview":     row["overview"],
            "genres":       row["genres"],
            "keywords":     row["keywords"],
            "cast":         row["cast"],
            "vote_average": row["vote_average"],
            "popularity":   row["popularity"],
            "poster_path":  row["poster_path"],
        }

    def _load_from_json(self) -> None:
        """Fallback: read JSON caches from disk (local dev without Supabase)."""
        print("[store] SUPABASE_URL not set — falling back to JSON files.")
        self._movies = self._read(MOVIES_CACHE, "movies")
        self._shows  = self._read(SHOWS_CACHE,  "shows")
        self._load_genres_json()

    def _load_genres_json(self) -> None:
        if not GENRES_CACHE.exists():
            print(f"[store] WARNING: {GENRES_CACHE} missing — run scripts/fetch_tmdb.py")
            return
        with open(GENRES_CACHE, encoding="utf-8") as f:
            raw = json.load(f)
        self._movie_genres = raw.get("movie", {})
        self._tv_genres    = raw.get("tv",    {})

    @staticmethod
    def _read(path: Path, label: str) -> dict:
        if not path.exists():
            print(f"[store] WARNING: {path} missing — run scripts/fetch_tmdb.py")
            return {}
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[store] Read {len(data)} {label} from {path.name}")
        return data

    # ── Accessors ──────────────────────────────────────────────────────────────

    def get_movie(self, tmdb_id: int) -> Optional[dict]:
        return self._movies.get(str(tmdb_id))

    def get_show(self, tmdb_id: int) -> Optional[dict]:
        return self._shows.get(str(tmdb_id))

    def get_item(self, tmdb_id: int) -> Optional[dict]:
        """Checks movies first, then shows."""
        return self.get_movie(tmdb_id) or self.get_show(tmdb_id)

    def all_movies(self) -> list[dict]:
        return list(self._movies.values())

    def all_shows(self) -> list[dict]:
        return list(self._shows.values())

    def all_items(self) -> list[dict]:
        return self.all_movies() + self.all_shows()

    def movie_genres(self) -> dict[str, str]:
        """Returns { genre_id_str: genre_name } for movies."""
        return self._movie_genres

    def tv_genres(self) -> dict[str, str]:
        """Returns { genre_id_str: genre_name } for TV shows."""
        return self._tv_genres

    # ── Search ─────────────────────────────────────────────────────────────────

    def search(self, query: str, item_type: str = "all", limit: int = 20) -> list[dict]:
        """Case-insensitive title search. Results sorted by popularity."""
        q = query.lower().strip()

        if item_type == "movie":
            pool = self.all_movies()
        elif item_type == "show":
            pool = self.all_shows()
        else:
            pool = self.all_items()

        matches = [i for i in pool if q in i["title"].lower()]
        matches.sort(key=lambda x: x.get("popularity", 0), reverse=True)
        return matches[:limit]

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        def genre_counts(items: list[dict]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for item in items:
                for g in item.get("genres", []):
                    counts[g] = counts.get(g, 0) + 1
            return dict(sorted(counts.items(), key=lambda x: -x[1]))

        movies = self.all_movies()
        shows  = self.all_shows()

        return {
            "total_movies":  len(movies),
            "total_shows":   len(shows),
            "total_items":   len(movies) + len(shows),
            "movie_genres":  genre_counts(movies),
            "show_genres":   genre_counts(shows),
        }


# Singleton — imported by main.py and api/routes.py
store = MediaStore()
