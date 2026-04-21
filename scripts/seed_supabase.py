"""
scripts/seed_supabase.py
────────────────────────
One-time (idempotent) script to load movies.json, shows.json, and genres.json
into Supabase Postgres tables.

Usage:
    python scripts/seed_supabase.py

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import json
import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def seed_media(client: Client, table: str, json_path: Path) -> int:
    """Upsert movies or shows from a JSON file into the given table."""
    with open(json_path, encoding="utf-8") as f:
        raw: dict[str, dict] = json.load(f)

    rows = []
    for tmdb_id_str, item in raw.items():
        rows.append({
            "tmdb_id":      item["id"],
            "title":        item["title"],
            "year":         item.get("year"),
            "overview":     item.get("overview", ""),
            "genres":       item.get("genres", []),
            "keywords":     item.get("keywords", []),
            "cast":         item.get("cast", []),
            "vote_average": item.get("vote_average", 0.0),
            "popularity":   item.get("popularity", 0.0),
            "poster_path":  item.get("poster_path"),
        })

    if not rows:
        print(f"  [{table}] No data found in {json_path.name}")
        return 0

    # Upsert in batches of 500 (Supabase limit)
    batch_size = 500
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table(table).upsert(batch, on_conflict="tmdb_id").execute()
        total += len(batch)
        print(f"  [{table}] Upserted batch {i // batch_size + 1}: {len(batch)} rows")

    return total


def seed_genres(client: Client, json_path: Path) -> int:
    """Upsert genres from genres.json into the genres table."""
    with open(json_path, encoding="utf-8") as f:
        raw: dict[str, dict[str, str]] = json.load(f)

    rows = []
    for category, genres in raw.items():
        for tmdb_id_str, name in genres.items():
            rows.append({
                "category": category,
                "tmdb_id":  tmdb_id_str,
                "name":     name,
            })

    if not rows:
        print("  [genres] No data found")
        return 0

    client.table("genres").upsert(rows, on_conflict="category,tmdb_id").execute()
    print(f"  [genres] Upserted {len(rows)} rows")
    return len(rows)


def main() -> None:
    print("Connecting to Supabase...")
    client = get_client()

    movies_path = DATA_DIR / "movies.json"
    shows_path  = DATA_DIR / "shows.json"
    genres_path = DATA_DIR / "genres.json"

    for path in [movies_path, shows_path, genres_path]:
        if not path.exists():
            print(f"ERROR: {path} not found. Run scripts/fetch_tmdb.py first.")
            sys.exit(1)

    print("\nSeeding movies...")
    n_movies = seed_media(client, "movies", movies_path)

    print("\nSeeding shows...")
    n_shows = seed_media(client, "shows", shows_path)

    print("\nSeeding genres...")
    n_genres = seed_genres(client, genres_path)

    print(f"\nDone! {n_movies} movies, {n_shows} shows, {n_genres} genres seeded.")


if __name__ == "__main__":
    main()
