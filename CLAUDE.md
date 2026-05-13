# CLAUDE.md — Rec Engine

## Stack
**Backend:** FastAPI · Python 3.11+ · scikit-learn · OpenAI SDK · Supabase (Postgres + Auth) · RabbitMQ (pika) · TMDB API v3
**Frontend:** React 18 · TypeScript · Vite · Tailwind · React Router · Supabase JS
**Storage:** Supabase Postgres (primary) → falls back to local JSON cache. All reads served from RAM after startup.

## Structure
```
rec-engine/
├── api/
│   ├── routes.py             ← thin HTTP layer, zero business logic ✅
│   └── auth.py               ← Supabase JWT verification (JWKS, ES256) ✅
├── core/
│   ├── store.py              ← in-memory MediaStore (Supabase or JSON) ✅
│   ├── similarity.py         ← Jaccard on genres/keywords/cast ✅
│   ├── graph.py              ← Jaccard adjacency list, O(N²) build ✅
│   ├── tfidf.py              ← TF-IDF cosine adjacency list ✅
│   ├── watchlist_direct.py   ← direct neighbor aggregation ✅
│   ├── watchlist_bfs.py      ← BFS depth-2 with decay ✅
│   ├── watchlist_pagerank.py ← Personalized PageRank ✅
│   ├── coldstart.py          ← LLM (OpenAI) → signals → BFS pipeline ✅
│   ├── publisher.py          ← RabbitMQ publisher for cold-start jobs ✅
│   ├── rate_limit.py         ← sliding-window quota for cold-start ✅
│   └── supabase_client.py    ← service-role singleton (bypasses RLS) ✅
├── scripts/
│   ├── tmdb_client.py        ← ALL TMDB http calls, nowhere else ✅
│   ├── fetch_tmdb.py         ← fetch + cache pipeline → data/*.json ✅
│   ├── seed_supabase.py      ← seed Postgres from data/*.json ✅
│   └── set_admin_role.py     ← promote/demote a user via email ✅
├── supabase/migrations/      ← schema + profiles/roles ✅
├── frontend/                 ← Vite + React + Tailwind SPA ✅
├── data/                     ← genres.json, movies.json, shows.json (cache)
├── main.py                   ← FastAPI app + lifespan (loads + builds) ✅
├── worker.py                 ← RabbitMQ consumer for cold-start jobs ✅
└── config.py                 ← ALL constants here, nowhere else ✅
```

## Architecture flow

**API startup** (`main.py` lifespan):
1. `store.load()` — fetches movies/shows/genres from Supabase (or JSON fallback)
2. `graph.build(...)` — pairwise Jaccard, prunes top-N neighbors per node
3. `tfidf_index.build(...)` — TF-IDF on overviews, cosine similarity matrix

**Worker startup** (`worker.py`): same bootstrap, then blocks on RabbitMQ queue.

**Cold-start flow** (async):
`POST /recommend/coldstart` → insert pending row in `cold_start_jobs` → publish to RabbitMQ → return `job_id` immediately. Worker consumes, calls OpenAI, grounds signals to seed IDs, runs BFS, writes result back. Client polls `GET /jobs/{job_id}`.

**Auth:** Supabase JWTs verified via JWKS (`api/auth.py`). `get_current_user` requires a token; `get_optional_user` allows anonymous. Watchlist routes need auth; recommendation routes accept either an explicit `tmdb_ids` body or fall back to the authenticated user's stored watchlist.

## Recommendation algorithms

| Algo                 | File                       | Build / Query                      | Notes                       |
|----------------------|----------------------------|------------------------------------|-----------------------------|
| Jaccard              | `similarity.py` + `graph.py` | O(N²) build / O(1) lookup       | genres + keywords + cast    |
| TF-IDF               | `tfidf.py`                 | O(N²) build / O(1) lookup          | overview text, sklearn      |
| Watchlist direct     | `watchlist_direct.py`      | O(W × K)                           | sum & normalize             |
| Watchlist BFS        | `watchlist_bfs.py`         | O(W × K²)                          | depth-2, decay factor       |
| Watchlist PageRank   | `watchlist_pagerank.py`    | O(iters × N × K)                   | Personalized PPR            |
| Cold-start           | `coldstart.py`             | LLM call + BFS                     | LLM → signals → seeds → BFS |

## Rules

**Code quality**
- Typed signatures on every function
- `NotImplementedError` for stubs — never silent/fake returns
- Unbuilt endpoints return `503` with a clear message

**Maintainability**
- New TMDB data source → only touch `tmdb_client.py`
- Tune weights / decays / quotas → only touch `config.py`
- New external HTTP dependency → wrap it behind a single module (mirror the `tmdb_client` pattern)
- No constants duplicated across files

**Performance**
- Build (graph + tfidf) happens once at startup, never per request
- Everything served from RAM after load
- Use `time.perf_counter()` for timing
- Log build time, node count, edge count on every build
- Each route logs `query_time_ms` so algorithms can be benchmarked side-by-side

**Cold-start / async**
- API never blocks on the LLM — always enqueue and return `job_id`
- Worker failures: `nack(requeue=False)`, mark job `failed`, user resubmits from UI
- Rate limit (5/hour, sliding) enforced in the route before publish; admins bypass

**Auth**
- Service-role Supabase client is server-only (`core/supabase_client.py`) — never expose
- Frontend uses anon key + user JWT; route handlers verify via `api/auth.py`

## Comparison endpoints
- `GET  /recommend/compare/{tmdb_id}` — Jaccard vs TF-IDF, with overlap
- `POST /recommend/watchlist/compare` — direct vs BFS vs PageRank, with pairwise + triple overlap
- `GET  /graph/stats` — build stats for both indexes
