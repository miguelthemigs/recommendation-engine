"""
core/store.py
─────────────
In-memory data store. Loads JSON caches once at startup.
All API requests are served from RAM — zero disk/network I/O per request.
"""

import json
from pathlib import Path
from typing import Optional
from config import MOVIES_CACHE, SHOWS_CACHE, GENRES_CACHE


class MediaStore:

    def __init__(self):
        self._movies:       dict[str, dict] = {}
        self._shows:        dict[str, dict] = {}
        self._movie_genres: dict[str, str]  = {}   # { "28": "Action", "18": "Drama", ... }
        self._tv_genres:    dict[str, str]  = {}   # { "10759": "Action & Adventure", ... }

    # ── Startup ────────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Called once at FastAPI startup. Reads all JSON caches into memory."""
        self._movies = self._read(MOVIES_CACHE, "movies")
        self._shows  = self._read(SHOWS_CACHE,  "shows")
        self._load_genres()
        print(f"[store] {len(self._movies)} movies | {len(self._shows)} shows loaded.")
        print(f"[store] {len(self._movie_genres)} movie genres | {len(self._tv_genres)} TV genres loaded.")

    def _load_genres(self) -> None:
        """
        Reads genres.json which has the shape:
            { "movie": { "28": "Action", ... }, "tv": { "10759": "Action & Adventure", ... } }

        JSON keys are always strings, so genre IDs are stored as strings — that's fine,
        it matches how we look them up everywhere else.
        """
        if not GENRES_CACHE.exists():
            print(f"[store] WARNING: {GENRES_CACHE} missing — run scripts/fetch_tmdb.py")
            return

        with open(GENRES_CACHE, encoding="utf-8") as f:
            raw = json.load(f)

        # genres.json stores them under "movie" and "tv" keys
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