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
│   ├── tmdb_client.py            ← ALL TMDB http calls, nowhere else ✅
│   ├── fetch_tmdb.py             ← fetch + cache pipeline → data/*.json ✅
│   ├── seed_supabase.py          ← seed Postgres from data/*.json ✅
│   ├── set_admin_role.py         ← promote/demote a user via email ✅
│   ├── create_loadtest_accounts.py ← single admin+user for early load tests ✅
│   ├── create_admin_pool.py      ← provision N admin accounts for load tests ✅
│   └── create_one_user.py        ← create/reset single regular user (clean quota) ✅
├── tests/load/                  ← Cycle 5 load tests
│   ├── coldstart.js              ← k6 main scaling test (ramped 10/50/100 VUs) ✅
│   ├── ratelimit.js              ← k6 rate-limit verification (5×200 + 3×429) ✅
│   ├── queue_monitor.py          ← RabbitMQ /api/queues → CSV sidecar ✅
│   ├── summarize_results.py      ← k6 summary JSON → markdown tables ✅
│   ├── run_load_test.ps1         ← PowerShell orchestrator (-Workers N) ✅
│   ├── admin_pool.json           ← 20 admin accounts (gitignored, plain text local) ✅
│   ├── README.md                 ← test runbook ✅
│   └── results/                  ← k6 HTML dashboards + CSVs (gitignored)
├── supabase/migrations/         ← schema + profiles/roles ✅
├── frontend/                    ← Vite + React + Tailwind SPA ✅
├── data/                        ← genres.json, movies.json, shows.json (cache)
├── main.py                      ← FastAPI app + lifespan (loads + builds) ✅
├── worker.py                    ← RabbitMQ consumer for cold-start jobs ✅
├── config.py                    ← ALL constants here, nowhere else ✅
├── CYCLE5.md                    ← Cycle 5 report (load testing + evaluation) ✅
├── FLAVOUR4.md                  ← Flavour 4 PDP (deployment & DevOps) ✅
├── Dockerfile                   ← (Flavour 4 C2) one shared image, run as api or worker ✅
├── requirements.lock            ← (Flavour 4 C2) pinned deps for reproducible builds ✅
├── .dockerignore                ← (Flavour 4 C2) small, secret-free build context ✅
├── docker-compose.yml           ← (Flavour 4 C2) api + worker + rabbitmq local stack ✅
├── .env.example / frontend/.env.example ← (Flavour 4 C2) tracked env templates ✅
├── .github/workflows/ci.yml     ← (Flavour 4 C3) CI: ruff lint + pytest + build/push GHCR 🟡
├── tests/unit/                  ← (Flavour 4 C3) hermetic pytest suite (21 tests, no I/O) ✅
├── pyproject.toml               ← (Flavour 4 C3) ruff + pytest config (tooling only) ✅
├── requirements-dev.txt         ← (Flavour 4 C3) CI-only pytest + ruff (not in runtime image) ✅
├── k8s/                         ← (Flavour 4 C4) minikube manifests 🔲
└── .env                         ← SUPABASE/RABBITMQ/OPENAI + load-test creds
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
- **Dedup behavior**: the route re-attaches to an existing pending/running job *before* the rate-limit check (`api/routes.py:551-562`). One consequence: a user spamming submit only registers some attempts toward quota. Documented as a known quirk in `CYCLE5.md` §7.

**Auth**
- Service-role Supabase client is server-only (`core/supabase_client.py`) — never expose
- Frontend uses anon key + user JWT; route handlers verify via `api/auth.py`

**Load testing**
- `MOCK_OPENAI=true` env flag short-circuits `core/coldstart.py` to return canned signals after `MOCK_OPENAI_DELAY_MS` (default 2000ms). Worker logs a banner on startup whenever active so it cannot silently ship.
- All load tests use a 20-account admin pool (`tests/load/admin_pool.json`) — a single shared admin would be artificially serialized by the dedup behavior above.
- k6 binary is portable at `C:\tools\k6\k6-v0.50.0-windows-amd64\k6.exe`.
- Re-running the sweep: `./tests/load/run_load_test.ps1 -Workers N` (or run the steps inline; see `tests/load/README.md`).

**Deployment (Flavour 4 — target shape, mostly not built yet)**
- Two runtime images, one codebase: API (`main.py`) and worker (`worker.py`) ship as separate images but share the same heavy bootstrap (`store.load` + `graph.build` + `tfidf.build`). Build once, run as two deployments.
- Config is env-driven, never baked in. The two C2 blockers are now fixed: frontend API URL reads `VITE_API_URL` (`frontend/src/api/client.ts`); backend CORS reads `ALLOWED_ORIGINS` (`config.py` → `main.py`). No new hardcoded hosts.
- Secrets (Supabase keys, OpenAI key) live in a k8s `Secret`, never in an image or committed manifest. Non-secret config in a `ConfigMap`.
- Probes already exist — reuse them: `/health` = liveness, `/graph/stats` = readiness (readiness must wait out the ~6–10s graph build, so set a generous `initialDelaySeconds`).
- Images are built and pushed by CI to **GHCR** (`ghcr.io`); minikube pulls from there. CI cannot deploy into a laptop minikube — `kubectl apply` stays manual unless a self-hosted runner is added.
- Public edge: **Vercel** hosts the SPA (it cannot host the stateful backend/worker/broker — wrong runtime model); the minikube ingress is exposed via a **Cloudflare Tunnel**. Supabase stays managed/external.
- See `FLAVOUR4.md` for the full PDP and cycle plan.

## Comparison endpoints
- `GET  /recommend/compare/{tmdb_id}` — Jaccard vs TF-IDF, with overlap
- `POST /recommend/watchlist/compare` — direct vs BFS vs PageRank, with pairwise + triple overlap
- `GET  /graph/stats` — build stats for both indexes

## Cycle history (Flavour 3)

| Cycle | Focus | Status |
|---|---|---|
| 1 | Research — RabbitMQ vs Kafka, Supabase eval | Complete |
| 2 | Supabase Migration — dataset + auth + per-user watchlists | Complete |
| 3 | Async Message Bus — RabbitMQ publisher + worker, Realtime delivery | Complete |
| 4 | LLM Rate Limiting — 5/hr/user sliding window, admin bypass, structured 429 | Complete |
| 5 | Load Testing + Evaluation — k6 ramped 10/50/100 VUs × 1/2/3 workers, 20-account pool | Complete (see `CYCLE5.md`) |

**Headline Cycle 5 results:** submit p95 stayed under 250 ms across all worker counts (architectural promise ✓), e2e p95 dropped 51 s → 15 s going 1 → 3 workers (near-linear scaling). Next bottleneck identified: single uvicorn process — fix is `--workers 4` flag.

## Cycle history (Flavour 4 — Deployment & DevOps)

Deployment was the optional tail of Flavour 3; it is now its own flavour, broken into smaller cycles. Full PDP in `FLAVOUR4.md`. Stack: Vercel (frontend) + minikube + Cloudflare Tunnel (backend) + GHCR (images) + Supabase (managed). All free tier.

| Cycle | Focus | Status |
|---|---|---|
| 1 | Deployment Research — free-tier hosting decision (frontend / stateful k8s backend / registry) | Not started |
| 2 | Containerization — one shared image (api+worker) + docker-compose; `VITE_API_URL` / `ALLOWED_ORIGINS` env config | Complete (see `FLAVOUR4_CYCLES.md`) |
| 3 | CI/CD — GitHub Actions: ruff lint + pytest + build/push shared image to GHCR | Built — pending first green run on GitHub |
| 4 | Kubernetes — minikube: deployments/service/ingress, ConfigMap+Secret, `/health` + `/graph/stats` probes | Not started |
| 5 | Public Deployment — Vercel frontend + Cloudflare Tunnel to minikube ingress, end-to-end public smoke test | Not started |
| 6 (optional) | Autoscaling — KEDA/HPA worker scaling on RabbitMQ queue depth | Not started |
