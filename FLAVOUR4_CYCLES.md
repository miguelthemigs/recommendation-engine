# Flavour 4 — Cycle Implementation Log

Claude-facing execution log for Flavour 4 (Deployment & DevOps). The **PDP** lives in
`FLAVOUR4.md`; **this** file is the running implementation plan.

**Convention:** completed cycles are summarised, the *active* cycle is fully specified
ready to execute, future cycles are outlined. When a cycle is finished, its detailed plan
is replaced by a short summary and the next cycle's full plan is written in.

Stack (decided in Cycle 1): **Vercel** (frontend) · **minikube + Cloudflare Tunnel**
(stateful backend) · **GHCR** (images) · **Supabase** (managed). All free tier.

## Status

| Cycle | Focus | Status |
|---|---|---|
| 1 | Deployment Research | ✅ Complete |
| 2 | Containerisation | ✅ Complete |
| 3 | CI/CD Pipeline | 🟡 Built — pending first green run on GitHub |
| 4 | Kubernetes (minikube) | 🔲 Next |
| 5 | Public Deployment | 🔲 Not started |
| 6 (optional) | Autoscaling | 🔲 Not started |

---

## Cycle 1 — Deployment Research ✅

Justified the full free-tier deployment path *before* writing any deployment code, dating
every "free" claim to 2026.

- **Frontend → Vercel.** Ideal for a static SPA; structurally cannot host the stateful backend.
- **Backend → local minikube + Cloudflare Tunnel.** The only free option that can hold the
  engine in RAM, run an always-on worker, and host a broker while still being shown on a
  public HTTPS URL. Honest limitation: public only while the laptop + tunnel are running.
- **Images → GHCR**, built/pushed by GitHub Actions.
- **RabbitMQ in-cluster** (self-contained backend); **Supabase** stays managed.
- **Rejected:** Render (worker is paid, spins down after 15 min), Railway, Fly.io (no real
  permanent free always-on tier).
- **Key finding:** a system's *shape* (stateful + always-on worker) rules out the entire
  serverless category before cost is even considered.

---

## Cycle 2 — Containerisation ✅

Turned the laptop-only backend into a one-command containerised stack and removed the two
hardcoded deployment blockers. **No application behaviour changed** — only packaging + config.

**What was built**

| Artifact | Purpose |
|---|---|
| `Dockerfile` | One shared `python:3.13-slim` image, non-root, layer-cached deps. Default CMD = API (uvicorn). |
| `requirements.lock` | Pinned dependency versions → reproducible image builds. `requirements.txt` stays the readable source. |
| `.dockerignore` | Small, secret-free build context (excludes `.env`, `frontend/`, `data/`, `.git`, tests). |
| `docker-compose.yml` | `rabbitmq` + `api` + `worker`, healthcheck-gated startup, one image run two ways. |
| `.env.example` / `frontend/.env.example` | Tracked env templates (real `.env` stays gitignored). |

**One image, two ways:** API and worker share the same heavy bootstrap (`store.load` +
`graph.build` + `tfidf.build`), so they ship as one image. Compose runs it as `uvicorn …`
for the API and overrides the command to `python worker.py` for the worker.

**Blockers removed (the only source changes):**
- **CORS** — `main.py` no longer hardcodes origins; reads `ALLOWED_ORIGINS` (comma-separated)
  from `config.py` (`config.py` is the single place constants live).
- **Frontend API URL** — `frontend/src/api/client.ts` reads `import.meta.env.VITE_API_URL`
  (falls back to `http://localhost:8000`).

**One-command run:** `docker compose up --build` builds the image once and starts
broker → api → worker in order (api/worker wait for RabbitMQ's healthcheck). The broker
service name resolves `RABBITMQ_URL` inside the compose network (overrides the localhost default).

**Verified end-to-end** (against the live Supabase): `docker compose up --build` →
broker healthy → api `/health` returns `movies_loaded: 491, shows_loaded: 494` (loaded
from Supabase in-container) → `/graph/stats` shows Jaccard + TF-IDF built (976 nodes) →
worker connected to the broker via the `rabbitmq` service name and `waiting for jobs`.

**How to run & test** — see the "Containerisation — runbook" section at the bottom.

---

## Cycle 3 — CI/CD Pipeline 🟡 (built, pending first green run)

GitHub Actions on push to `main`: **lint → test → build the shared image → push to GHCR.**
Decisions made up front: minimal **pytest** suite (not a container smoke test), **ruff**
for lint, **backend-only** (Vercel owns the frontend pipeline).

**What was built**

| Artifact | Purpose |
|---|---|
| `tests/unit/` | Hermetic pytest suite (21 tests, no network/Supabase/OpenAI): `similarity`, `graph`, `watchlist` (direct + BFS), `tfidf`, and `config` (locks the Cycle 2 env-driven CORS contract). |
| `pyproject.toml` | Tooling config only — `[tool.ruff]` (pyflakes + pycodestyle subset) and `[tool.pytest.ini_options]` (`pythonpath="."`, `testpaths="tests/unit"`). Not a package build file. |
| `requirements-dev.txt` | CI-only `pytest` + `ruff`, kept out of `requirements.lock` so they never ship in the runtime image. |
| `.github/workflows/ci.yml` | Three jobs: `lint` (ruff) and `test` (pytest) on every push + PR; `build-and-push` (shared image → GHCR) gated on push to `main`. |

**Pipeline shape**
- **Trigger:** `push` to `main` + all `pull_request`s. Lint/test always run; the build job
  has `if: push && ref == main` so PRs (incl. forks) never need registry write access.
- **Lint:** `ruff check .` (config in `pyproject.toml`; frontend/data/results excluded).
- **Test:** `pip install -r requirements.lock -r requirements-dev.txt` → `pytest`.
- **Build + push:** `docker/build-push-action@v6` → `ghcr.io/${{ github.repository }}`
  tagged `latest` + `sha-<commit>` (immutable pin for Cycle 4 k8s), GHA layer cache.
- **Auth:** `secrets.GITHUB_TOKEN` with job-scoped `packages: write` — no long-lived secrets.

**The "no source changes" rule held:** the only app-adjacent edits were 8 ruff auto-fixes
(unused imports, unused exception var, placeholder-less f-strings) — all behaviour-preserving.

**Verified locally:** `ruff check .` → clean; `pytest` → 21 passed. The build is unchanged
from the Cycle 2 image (already verified end-to-end). The one thing that can only be proven
on GitHub — the workflow running green and an image landing in GHCR — is **pending the first
push**. Cycle stays 🟡 until that run is green, per the "verified before done" rule.

**To verify (the remaining step):** push to `main` → watch the Actions run go green → confirm
the package appears at `ghcr.io/miguelthemigs/recommendation-engine` (`latest` + `sha-…`).
First run may need the GHCR package set to the right visibility/permissions in repo settings.

---

## Cycle 4 — Kubernetes (minikube) 🔲 (next)

Backend running in minikube, all pods healthy.

- Two **Deployments** from the one GHCR image: `api` (uvicorn cmd) and `worker` (worker cmd).
- **RabbitMQ** Deployment (in-cluster) + Service.
- **Service** + **Ingress** for the API.
- **ConfigMap** (non-secret: `ALLOWED_ORIGINS`, `RABBITMQ_URL`, queue name) + **Secret**
  (Supabase keys, OpenAI key) — never baked into the image.
- Probes: liveness `/health`, readiness `/graph/stats` with a generous
  `initialDelaySeconds` (graph+tfidf build is ~6–10s).
- Note: CI can't deploy into a laptop minikube — `kubectl apply` stays manual.

---

## Cycle 5 — Public Deployment 🔲

- Frontend on **Vercel** with `VITE_API_URL` injected at build time.
- minikube ingress exposed via **Cloudflare Tunnel** → public HTTPS.
- Add the Vercel domain to `ALLOWED_ORIGINS`.
- Smoke test the full public flow: register → watchlist → cold-start.

---

## Cycle 6 — Autoscaling 🔲 (optional)

- **KEDA/HPA** scaling the worker Deployment on RabbitMQ queue depth.
- Compare against the manual worker scaling measured in Flavour 3 Cycle 5.

---

## Containerisation — runbook

**Prereqs:** Docker Desktop running; a real `.env` at the repo root (copy `.env.example`
and fill Supabase + OpenAI keys). Stop any ad-hoc local `rabbitmq` container first so
ports 5672/15672 are free.

```bash
# Build image + start the whole backend (broker → api → worker)
docker compose up --build          # add -d to detach
docker compose logs -f worker      # watch the worker bootstrap + "waiting for jobs"
```

**Checks**
- `curl http://localhost:8000/health` → `{"status":"ok", ...}`
- `curl http://localhost:8000/graph/stats` → build stats (graph + tfidf built in-container)
- RabbitMQ UI: http://localhost:15672 (guest/guest)
- End-to-end: get a JWT (load-test admin token or the UI) → `POST /recommend/coldstart`
  → poll `GET /jobs/{id}` until `completed`. Proves api↔broker↔worker wiring over compose
  service names.
- Frontend against the container: `cd frontend && npm run dev` with
  `VITE_API_URL=http://localhost:8000`.

**Teardown:** `docker compose down` (`-v` also drops the RabbitMQ volume).
