# TV/Movie Recommendation Engine

Graph-based recommendation engine built with FastAPI + TMDB.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env → add your TMDB_API_KEY
```

## Step 1 — Fetch & cache data (run once)

```bash
python scripts/fetch_tmdb.py
```

This produces:
- `data/genres.json` — genre ID → name maps for movies and TV
- `data/movies.json` — ~200 movies with genres, keywords, cast
- `data/shows.json`  — ~200 TV shows with genres, keywords, cast

## Run the API

```bash
uvicorn main:app --reload
```

Visit: http://localhost:8000/docs

## Endpoints

| Tag | Method | Path | Description |
|-----|--------|------|-------------|
| movies | GET | `/movies` | List all cached movies |
| movies | GET | `/movies/genres` | Movie genre map |
| movies | GET | `/movies/{id}` | Single movie |
| shows | GET | `/shows` | List all cached shows |
| shows | GET | `/shows/genres` | TV genre map |
| shows | GET | `/shows/{id}` | Single show |
| search | GET | `/search?q=...&type=movie\|show\|all` | Title search |
| meta | GET | `/stats` | Dataset stats |
| meta | GET | `/health` | Health check |
| recommendations | GET | `/recommend/{id}` | Top-K for one item *(Step 3)* |
| recommendations | POST | `/recommend/watchlist` | Top-K for watchlist *(Step 4)* |
| graph | GET | `/graph/stats` | Graph build stats *(Step 3)* |

## Project Structure

```
rec-engine/
├── data/                        # JSON cache (git-ignored)
│   ├── genres.json
│   ├── movies.json
│   └── shows.json
├── api/
│   └── routes.py                # HTTP handlers (thin layer, no logic)
├── core/
│   ├── store.py                 # In-memory data store ✅
│   ├── similarity.py            # Jaccard scoring       🔲 Step 2
│   └── graph.py                 # Adjacency list        🔲 Step 3
├── scripts/
│   ├── tmdb_client.py           # All TMDB HTTP calls   ✅
│   └── fetch_tmdb.py            # Fetch + cache script  ✅
├── main.py                      # FastAPI app           ✅
├── config.py                    # All config/constants  ✅
└── requirements.txt
```

## Roadmap

- **Step 2** — Implement `core/similarity.py` (Jaccard on genres, keywords, cast)
- **Step 3** — Implement `core/graph.py` (O(N²) build, adjacency list, top-K query)
- **Step 4** — Watchlist aggregation (sum neighbor scores, exclude seen items)
- **Step 5** — Performance analysis (build time, score distribution, weight tuning)
