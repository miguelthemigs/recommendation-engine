# TV/Movie Recommendation Engine

A graph-based TV & movie recommendation engine with an LLM cold-start flow, built as a scalable
multi-user system. FastAPI backend, React frontend, Supabase for data + auth, RabbitMQ for async
job processing.

- **Backend:** FastAPI · Python 3.11+ · scikit-learn · OpenAI SDK · Supabase (Postgres + Auth) · RabbitMQ (pika) · TMDB API v3
- **Frontend:** React 18 · TypeScript · Vite · Tailwind · React Router · Supabase JS
- **Storage:** Supabase Postgres (primary), local JSON cache fallback. All reads served from RAM after startup.

> Runs end to end and is deployed **public over HTTPS** — the SPA on Vercel, the
> containerized backend on Kubernetes, exposed through a Cloudflare tunnel, with CI building
> and publishing images on every push. See `CLAUDE.md` for the full architecture reference.

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
| `VITE_API_URL` | Backend API base URL (defaults to `http://localhost:8000`) |

> All config is env-driven — the frontend API base URL reads `VITE_API_URL`
> (`frontend/src/api/client.ts`) and backend CORS reads `ALLOWED_ORIGINS` /
> `ALLOWED_ORIGIN_REGEX` (`config.py`). No hardcoded hosts.

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

> Or bring the whole local stack up with one command: `docker compose up`. For the
> Kubernetes deployment, see [Deployment](#deployment) below.

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
| meta | GET | `/ready` | Readiness/startup probe — `503` until graph + TF-IDF are built, `200` after |
| recommendations | GET | `/recommend/{id}` | Top-K for one item |
| recommendations | POST | `/recommend/watchlist` | Top-K for a watchlist |
| recommendations | POST | `/recommend/coldstart` | Enqueue an async cold-start job → returns `job_id` |
| recommendations | GET | `/recommend/coldstart/quota` | Remaining cold-start quota for the user |
| jobs | GET | `/jobs/{job_id}` | Poll a cold-start job result |
| compare | GET | `/recommend/compare/{id}` | Jaccard vs TF-IDF, with overlap |
| compare | POST | `/recommend/watchlist/compare` | direct vs BFS vs PageRank, with overlap |
| graph | GET | `/graph/stats` | Graph build stats (returns `200` even when unbuilt — use `/ready` for readiness) |

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

k6 load tests live in `tests/load/` with their own runbook (`tests/load/README.md`).
Measured characteristics: cold-start submit p95 stays under 250 ms across worker counts (the
API never blocks on the LLM), and end-to-end p95 drops from ~51 s to ~15 s scaling workers
from 1 to 3 (near-linear).

```powershell
./tests/load/run_load_test.ps1 -Workers 3
```

---

## Deployment

The app is deployed on a fully free-tier stack, public over HTTPS:

```
Vercel SPA  ──HTTPS──>  Cloudflare Tunnel  ──>  Kubernetes ingress (minikube)
   (frontend)                                      ├─ api (FastAPI)
                                                    ├─ worker
                                                    └─ rabbitmq
Supabase (managed Postgres + Auth)  <── api + worker
GHCR (ghcr.io)  ──images──>  pulled by the cluster ; GitHub Actions builds + pushes on main
```

- **Containers** — one shared `Dockerfile` run two ways (api / worker); `docker-compose.yml` for the local stack.
- **CI/CD** — `.github/workflows/ci.yml`: lint + test + build + push the shared image to GHCR on every push to `main`.
- **Kubernetes** — `k8s/` manifests (deployments, service, ingress, ConfigMap, Secret, `/health` liveness + `/ready` readiness/startup probes). One-command bring-up via `up.ps1`.
- **Public edge** — the SPA on Vercel (`VITE_API_URL` injected at build time); the cluster ingress exposed through an in-cluster Cloudflare tunnel. CORS allows the Vercel origin via `ALLOWED_ORIGIN_REGEX`.

### Run the backend on a local cluster
```powershell
# Admin PowerShell, from the repo root — starts the cluster, builds the image,
# deploys everything (incl. the public tunnel), and prints the public URL.
powershell -ExecutionPolicy Bypass -File .\up.ps1
```
Full setup/run/scaling/troubleshooting guide and the public-access runbook: `k8s/README.md`.

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
├── k8s/            # Kubernetes manifests (incl. cloudflared tunnel) + runbook (README.md)
├── up.ps1          # one-command cluster bring-up (build → deploy → public URL)
├── tunnel-url.ps1  # read the public tunnel URL; -UpdateVercel re-points VITE_API_URL
├── Dockerfile      # one shared image, run as api or worker
├── docker-compose.yml  # local api + worker + rabbitmq stack
├── main.py         # FastAPI app + lifespan (load + build); /health + /ready
├── worker.py       # RabbitMQ consumer for cold-start jobs
└── config.py       # all constants / env loading
```

See `CLAUDE.md` for the full architecture reference and engineering rules.
