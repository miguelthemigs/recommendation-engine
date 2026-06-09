# Flavour 4 — Cycle 4: Running the Backend on Kubernetes (minikube)

*Recommendation Engine · Deployment & DevOps · Semester 6 · 2026*
*Learning Outcomes: LO1 (Engineering Approach), LO3 (Software Maintenance)*

---

## 1. Where this cycle fits

Cycle 2 packaged the backend into one container image. Cycle 3 built a pipeline that
checks that image and publishes it. Both answered *how the software is built and
shipped* — neither actually **runs** it as a real, orchestrated system.

This cycle does that. I take the published image and run the full backend on
**Kubernetes** (using **minikube**, a local single-node Kubernetes cluster), as three
independent pieces — the API, the worker, and the RabbitMQ broker — that start
themselves, restart on failure, and only receive traffic once they're actually ready.
The deliverable is concrete: **all pods healthy and the API reachable, talking to the
live Supabase database.**

---

## 2. What Kubernetes is doing here (in plain terms)

Up to now, "running the app" meant me starting processes and hoping they stayed up.
Kubernetes replaces that with a **manager** I describe my desired state to, in writing.
I don't tell it *how* to start things step by step — I tell it *what I want to be true*
("one API running, one worker, one broker, here's their config, here's how to tell if
they're healthy"), and it makes reality match that, continuously. If something crashes,
it restarts it. If something isn't ready, it keeps traffic away from it.

The vocabulary I actually used:

- **Pod** — one running instance of a container. My app runs as pods.
- **Deployment** — the rule that says "keep N copies of this pod alive". I have three:
  `api`, `worker`, `rabbitmq`.
- **Service** — a stable internal address for a deployment, so the API can always find
  RabbitMQ by the name `rabbitmq` even when the pod behind it is replaced.
- **Ingress** — the front door that lets traffic from outside reach the API by hostname
  (`rec-engine.local`).
- **ConfigMap / Secret** — configuration injected into the pods. Non-secret settings go
  in the ConfigMap; passwords and keys go in the Secret. They are kept separate on
  purpose (see §4).
- **Probes** — health checks Kubernetes runs against my pods to decide if they're alive
  and ready (see §5 — this was the most interesting part).

---

## 3. The decisions I made before writing anything

As in every cycle, I settled the real choices first and wrote down why.

1. **Run against the live database, not a fake.** Supabase is live, so I deployed for a
   genuine end-to-end test rather than the local-JSON fallback. A deployment that only
   works against mocks isn't really verified.

2. **Pull the image without credentials.** Rather than wire up registry passwords inside
   the cluster, I planned for the published image to be **public**, so minikube can pull
   it with no secret. Simpler, and nothing sensitive is in the image anyway.

3. **Add a real readiness signal.** My app needs ~30–60s at startup to build its
   similarity graph and TF-IDF index. I needed Kubernetes to *wait out that build*
   before sending traffic. I checked my existing `/graph/stats` endpoint and found it
   returns "OK" even before the build finishes — so it's useless as a readiness gate. I
   decided to add a small new endpoint, **`/ready`**, that returns "not ready" (HTTP 503)
   until *both* indexes are built, and "ready" (200) after. This is the one code change
   in the cycle, and it only reports status — it doesn't change what the app does.

4. **Broker as a simple, throwaway deployment.** RabbitMQ runs as an ordinary deployment
   with non-persistent storage. Cold-start jobs are transient and the real source of
   truth is the database, so losing the queue on a restart is acceptable for this stage.

---

## 4. What I built (the manifests)

Everything lives in a new `k8s/` folder, one file per concern:

| File | What it creates | Why |
|---|---|---|
| `namespace.yaml` | A `rec-engine` namespace | Keeps all my objects together; one command deletes everything cleanly |
| `configmap.yaml` | Non-secret config | Broker address, allowed origins, mock flag — safe to commit |
| `secret.example.yaml` | A placeholder template | Shows which secret keys are needed, without ever committing real keys |
| `rabbitmq.yaml` | Broker deployment + service | The message queue, reachable in-cluster as `rabbitmq` |
| `api.yaml` | API deployment + service | The FastAPI app; the only piece exposed to the outside |
| `worker.yaml` | Worker deployment | Same image, started as the queue consumer instead of the web server |
| `ingress.yaml` | The front door | Maps `rec-engine.local` to the API service |

**Two settings I want to call out:**

- **Config split.** Non-secret values sit in the ConfigMap (committed to git). The
  Supabase and OpenAI keys go into a Secret that is **built from my local `.env` at
  deploy time** and never committed. Only a placeholder template is in the repo. This
  mirrors the `.env.example` / `.env` pattern I already use.

- **One image, two roles.** The `api` and `worker` deployments use the *exact same
  image*. The worker just overrides the start command to run the queue consumer instead
  of the web server. Building one image and running it two ways avoids drift between
  them.

---

## 5. The part I had to actually think about: probes

Kubernetes offers three health checks, and using the right one for the right job is the
whole point:

- **Liveness** (`/health`) — "is the process alive?" If this fails, restart the pod.
- **Readiness** (`/ready`) — "should this pod receive traffic *yet*?" If this fails, keep
  it in the deployment but route nothing to it.
- **Startup** (`/ready`, generous budget) — "has the slow boot finished?" This runs
  *first* and holds off the other two, so my 30–60s graph build doesn't get
  misread as a crash and restarted in a loop.

This is exactly why I added `/ready`. Without it, Kubernetes would either send requests
to an API that isn't built yet (errors), or kill the pod mid-build thinking it had hung.
The startup probe gives the build ~150 seconds to finish; only then do liveness and
readiness take over. Getting this right is what makes the pod come up `0/1` for a minute
and *then* flip to `1/1` — which is the system working as designed, not a fault.

---

## 6. Step by step — what I actually did

1. **Added the `/ready` endpoint** to the API and confirmed it reports 503 → 200 across
   the build.
2. **Wrote the seven manifests** above and validated they parse.
3. **Started the cluster** (`minikube start`) and **enabled the ingress** front door.
4. **Built the image into the cluster.** This is where I hit my main snag (§7) and
   learned to build the image *directly inside minikube's own Docker* so the cluster
   actually runs my latest code.
5. **Applied the config, secret, and workloads** in order. I hit a real ordering bug
   here: the API and worker pods failed with `CreateContainerConfigError` because I'd
   applied them before the ConfigMap existed. Applying the ConfigMap fixed it
   immediately — Kubernetes retried on its own, no pod deletion needed.
6. **Watched the pods come up.** RabbitMQ and worker went healthy fast; the API sat at
   `0/1` for ~30s building its graph, then flipped to `1/1` — proof the readiness gate
   works.
7. **Verified end to end.** `/ready` returned `{"ready": true}` with 976 graph nodes and
   the TF-IDF index built, served *through* the cluster against live Supabase.
8. **Reached it from the browser** (§7 — the Windows networking wrinkle).
9. **Wrapped the whole thing in one script**, `up.ps1`, so a fresh bring-up is a single
   command.

---

## 7. Honest problems I ran into (and fixed)

These are worth recording because the fixes *are* the learning.

- **Stale image.** My first run had healthy pods but every readiness check returned
  `404` — because the published image predated my new `/ready` endpoint, and that's what
  the cluster pulled. **Fix:** build the image into minikube's own Docker daemon.
  I learned the hard way that `minikube image load` does *not* reliably overwrite an
  existing `:latest` tag; building directly inside minikube's Docker does.

- **Wrong apply order.** Pods can't start before the config they depend on exists.
  **Fix:** apply namespace → ConfigMap → Secret → workloads, in that order (the script
  now enforces it).

- **Can't reach the hostname from Windows.** The cluster runs inside Docker on a private
  network (`192.168.49.2`) that Windows can't route to directly, so `rec-engine.local`
  timed out. **Fix:** point the hostname at `127.0.0.1` and run a small **bridge** —
  `kubectl port-forward` onto the ingress — while using the app. This is a local-dev
  quirk of Docker-on-Windows, not a flaw in the deployment; in real hosting the cluster
  has a routable address.

---

## 8. The `up.ps1` script — what it does

One script brings everything up from nothing, in order:

1. **Start minikube** and enable the ingress front door.
2. **Build the image into minikube's Docker** so the cluster runs my current code.
3. **Apply the namespace and ConfigMap.**
4. **Create the Secret from `.env`** (rebuilt each run, so config edits always take).
5. **Apply the api, worker, broker, and ingress**, and restart them onto the fresh image.
6. **Wait** until all three are healthy (tolerating the API's slow first build).
7. **Fix the hosts entry** so `rec-engine.local` points at `127.0.0.1`.
8. **Open the bridge** (`port-forward`) and leave it running, so the browser can reach
   `http://rec-engine.local/docs` immediately.

It's deliberately idempotent: re-running it on an existing cluster just re-syncs
everything and reopens the bridge.

---

## 9. Setup & run guide

### One-time setup
- Have **Docker Desktop, minikube, kubectl** (and optionally **k9s**) installed.
- Have a `.env` in the repo root with the five keys: `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `OPENAI_API_KEY`,
  `SUPABASE_JWT_SECRET`.

### Every time you want it running
Open **PowerShell as Administrator** (it edits the hosts file and binds port 80), from
the repo root:
```powershell
powershell -ExecutionPolicy Bypass -File .\up.ps1
```
Leave the window open. Then browse to **http://rec-engine.local/docs**.
> Use `/docs`, `/health`, or `/ready` — bare `rec-engine.local` returns 404 by design.

### Coming back later

| You did | To get back |
|---|---|
| Closed only the bridge window | Re-run just the `port-forward` command |
| Turned the PC off / `minikube stop` | `minikube start`, then the bridge — or just run `up.ps1` |
| `minikube delete` (full wipe) | Run `up.ps1` (it rebuilds the image too) |

Turning the computer off is safe — it pauses the cluster, it doesn't delete it. Full
command reference is in `k8s/README.md`.

---

## 10. What I learned

- **Kubernetes is declarative, and that's the whole shift.** I stopped writing "start
  this, then that" and started describing the end state I want. The manager keeps
  reality matching it. That's what makes it self-healing.
- **Readiness is a real design problem, not a checkbox.** My app's slow startup forced me
  to think about the difference between "alive", "ready", and "still booting" — three
  distinct questions that need three distinct probes. Reusing the wrong endpoint as a
  readiness gate would have silently sent traffic to a half-built app.
- **Most of the work was config and ordering, not code.** The only code change was a
  tiny status endpoint. Everything else was describing infrastructure correctly — and
  the bugs I hit (apply order, stale image, host networking) were all about the
  environment, not the application logic.
- **A clean bring-up script is part of maintainability.** After fighting three separate
  gotchas by hand, folding the correct sequence into one script means I — or anyone —
  can reproduce a working system without re-learning those traps.

---

## 11. What's next

- **Cycle 5 — Public deployment.** Put the frontend on Vercel and expose the cluster to
  the public internet through a Cloudflare Tunnel, so the app is reachable without the
  local bridge. The hostname/networking work here feeds directly into that.
- **Cycle 6 (optional) — Autoscaling.** Scale the worker automatically based on how many
  cold-start jobs are waiting in the queue.
- **Carryover:** the published image needs to be rebuilt with `/ready` (via the Cycle 3
  pipeline) so the "pull from the registry" path works as cleanly as the local build does
  today.

---

## 12. How this maps to the Learning Outcomes

- **LO1 — Engineering Approach.** I settled the real decisions before building (live DB
  vs mock, credential-free image pull, adding a true readiness gate, throwaway broker),
  each with a written reason. I chose the right Kubernetes object for each job and the
  right probe for each health question, and I diagnosed three concrete failures
  (stale image, apply order, host networking) down to their root cause rather than
  guessing.
- **LO3 — Software Maintenance.** The result is reproducible and self-documenting: seven
  small single-purpose manifests, a clean config/secret split that keeps keys out of
  git, one image run two ways to avoid drift, and a single idempotent script plus a
  runbook so the system can be brought up the same way every time. The one code change
  was minimal and behaviour-preserving, keeping the "only change how it ships" boundary
  intact.
