# TV/Movie Recommendation Engine

A graph-based TV & movie recommendation engine with an LLM cold-start flow, built as a scalable
multi-user system. FastAPI backend, React frontend, Supabase for data + auth, RabbitMQ for async
job processing.

- **Backend:** FastAPI · Python 3.11+ · scikit-learn · OpenAI SDK · Supabase (Postgres + Auth) · RabbitMQ (pika) · TMDB API v3
- **Frontend:** React 18 · TypeScript · Vite · Tailwind · React Router · Supabase JS
- **Storage:** Supabase Postgres (primary), local JSON cache fallback. All reads served from RAM after startup.

> Built across "Flavours" for Semester 6. Flavour 3 (scalable architecture) is complete — see
> `CYCLE5.md`. Flavour 4 (deployment & DevOps) is the current focus — see `FLAVOUR4.md`.

---

## The system at a glance

The full system is **five processes**:

| Process | Entrypoint | Port | Role |
|---|---|---|---|
| API | `main.py` (uvicorn) | 8000 | HTTP API; builds the in-memory graph at startup |
| Worker | `worker.py` | — | Consumes cold-start jobs from RabbitMQ, calls OpenAI |
| Broker | RabbitMQ (Docker) | 5672 / 15672 | Job queue between API and worker |
| Frontend | `frontend/` (Vite) | 5173 | React SPA |
| Database | Supabase | — | Managed Postgres + Auth (external) |

The API and worker each run the same heavy bootstrap on startup: `store.load()` →
`graph.build()` (Jaccard) → `tfidf_index.build()` (TF-IDF). This takes ~6–10s and then everything
is served from RAM. Only the cold-start LLM call is async; single-item and watchlist
recommendations are synchronous.

---

## Prerequisites

- Python 3.11+
- Node 18+ (for the frontend)
- Docker (for RabbitMQ)
- A Supabase project (free tier) — for Postgres + Auth
- A TMDB API key — to fetch the catalog (one-time)
- An OpenAI API key — for the cold-start feature

---

## Environment variables

**Backend** — `.env` in the repo root (loaded by `config.py`):

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | yes | Public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Service-role key (server-only, bypasses RLS) |
| `SUPABASE_JWT_SECRET` | yes | JWT validation |
| `TMDB_API_KEY` | setup only | Fetching the catalog (`scripts/fetch_tmdb.py`) |
| `OPENAI_API_KEY` | yes (cold-start) | GPT calls in the worker |
| `RABBITMQ_URL` | yes | Default `amqp://guest:guest@localhost:5672/` |
| `MOCK_OPENAI` | optional | `true` returns canned signals (load testing); logs a startup banner |
| `MOCK_OPENAI_DELAY_MS` | optional | Simulated LLM delay when mocking (default 2000) |

**Frontend** — `frontend/.env` (Vite, must be prefixed `VITE_`):

| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Public anon key |

> Note (Flavour 4): the frontend API base URL is currently hardcoded to `http://localhost:8000`
> in `frontend/src/api/client.ts`, and backend CORS is hardcoded in `main.py`. Cycle 2 of
> Flavour 4 turns these into `VITE_API_URL` / `ALLOWED_ORIGINS`.

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in the values above
```

### 1. Fetch & cache the catalog (run once)

```bash
python scripts/fetch_tmdb.py
```

Produces `data/genres.json`, `data/movies.json`, `data/shows.json` (git-ignored). The backend
loads from Supabase first and falls back to these JSON files if Supabase is not configured.

### 2. Set up the database

Apply the migrations in `supabase/migrations/` to your Supabase project, then seed it from the
cached JSON:

```bash
python scripts/seed_supabase.py
```

---

## Running locally

You need four things running: the broker, the API, the worker, and the frontend.

```bash
# 1. RabbitMQ broker (management UI at http://localhost:15672, guest/guest)
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=guest -e RABBITMQ_DEFAULT_PASS=guest \
  rabbitmq:3-management

# 2. API
uvicorn main:app --reload          # http://localhost:8000/docs

# 3. Worker (separate terminal)
python worker.py

# 4. Frontend (separate terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

> Flavour 4 replaces this multi-terminal dance with `docker compose up` (Cycle 2) and then a
> Kubernetes deployment (Cycle 4). See `FLAVOUR4.md`.

---

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
| meta | GET | `/health` | Health check (liveness probe) |
| recommendations | GET | `/recommend/{id}` | Top-K for one item |
| recommendations | POST | `/recommend/watchlist` | Top-K for a watchlist |
| recommendations | POST | `/recommend/coldstart` | Enqueue an async cold-start job → returns `job_id` |
| recommendations | GET | `/recommend/coldstart/quota` | Remaining cold-start quota for the user |
| jobs | GET | `/jobs/{job_id}` | Poll a cold-start job result |
| compare | GET | `/recommend/compare/{id}` | Jaccard vs TF-IDF, with overlap |
| compare | POST | `/recommend/watchlist/compare` | direct vs BFS vs PageRank, with overlap |
| graph | GET | `/graph/stats` | Graph build stats (readiness probe) |

Auth: watchlist and cold-start routes require a Supabase JWT (`Authorization: Bearer …`).
Recommendation routes accept an explicit `tmdb_ids` body or fall back to the user's stored watchlist.

---

## Recommendation algorithms

| Algorithm | File | Build / Query | Notes |
|---|---|---|---|
| Jaccard | `core/similarity.py` + `core/graph.py` | O(N²) build / O(1) lookup | genres + keywords + cast |
| TF-IDF | `core/tfidf.py` | O(N²) build / O(1) lookup | overview text, sklearn |
| Watchlist direct | `core/watchlist_direct.py` | O(W × K) | sum & normalize |
| Watchlist BFS | `core/watchlist_bfs.py` | O(W × K²) | depth-2, decay |
| Watchlist PageRank | `core/watchlist_pagerank.py` | O(iters × N × K) | Personalized PPR |
| Cold-start | `core/coldstart.py` | LLM call + BFS | OpenAI → signals → seeds → BFS |

---

## Load testing

k6 load tests live in `tests/load/` with their own runbook (`tests/load/README.md`). Headline
Cycle 5 result: submit p95 stayed under 250 ms across all worker counts; end-to-end p95 dropped
51 s → 15 s going from 1 to 3 workers (near-linear). Full report in `CYCLE5.md`.

```powershell
./tests/load/run_load_test.ps1 -Workers 3
```

---

## Deployment (Flavour 4 — in progress)

The deployment target is fully free-tier:

```
Vercel SPA  ──HTTPS──>  Cloudflare Tunnel  ──>  minikube ingress (local)
   (frontend)                                      ├─ api (FastAPI)
                                                    ├─ worker
                                                    └─ rabbitmq
Supabase (managed Postgres + Auth)  <── api + worker
GHCR (ghcr.io)  ──images──>  pulled by minikube ; GitHub Actions builds + pushes on main
```

- **C2 Containerization** — `Dockerfile` (api) + `Dockerfile.worker`, `docker-compose.yml` for the local stack
- **C3 CI/CD** — `.github/workflows/ci.yml`: lint + test + build + push images to GHCR
- **C4 Kubernetes** — `k8s/` manifests for minikube (deployments, service, ingress, ConfigMap, Secret, probes)
- **C5 Public** — Vercel frontend + Cloudflare Tunnel to the minikube ingress

See `FLAVOUR4.md` for the full plan.

---

## Project structure

```
rec-engine/
├── api/            # routes.py (HTTP layer), auth.py (Supabase JWT)
├── core/           # store, similarity, graph, tfidf, watchlist_*, coldstart, publisher, rate_limit
├── scripts/        # fetch_tmdb, seed_supabase, set_admin_role, account provisioning
├── tests/load/     # k6 load tests + runbook
├── supabase/       # schema + profiles/roles migrations
├── frontend/       # Vite + React + Tailwind SPA
├── data/           # JSON cache (git-ignored)
├── main.py         # FastAPI app + lifespan (load + build)
├── worker.py       # RabbitMQ consumer for cold-start jobs
├── config.py       # all constants / env loading
├── CYCLE5.md       # Flavour 3 load-testing report
└── FLAVOUR4.md     # Flavour 4 deployment PDP
```

See `CLAUDE.md` for the full architecture reference and engineering rules.
