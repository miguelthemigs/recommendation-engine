# Running the rec-engine backend on minikube

This deploys the backend (API + worker + RabbitMQ broker) into a local minikube
cluster. The frontend is **not** here — it runs locally (`cd frontend && npm run dev`)
or on Vercel (see [Public access](#public-access--vercel--cloudflare-quick-tunnel) below).
Supabase is managed/external.

There are two phases:

- **[Initial setup](#initial-setup-one-time)** — done **once** per machine.
- **[To run](#to-run-every-session)** — done **every time** you bring the stack up.

---

## Initial setup (one-time)

You only do these once. They survive cluster restarts.

### 1. Tools installed
- **Docker Desktop** (running — minikube uses it as the driver)
- **minikube**, **kubectl**, **k9s**
- Verify:
  ```powershell
  docker version
  minikube version
  kubectl version --client
  k9s version
  ```

### 2. Get a working image into the cluster
The deployments use `imagePullPolicy: IfNotPresent`, so they prefer an image already
present in minikube and fall back to pulling `ghcr.io/.../recommendation-engine:latest`
from GHCR. There are two ways to supply the image — pick one:

**Option A — build it into minikube (local, no push, recommended for dev).**
This is the workflow in use. The image must be built inside **minikube's own docker
daemon** — `minikube image load` does *not* reliably overwrite an existing `:latest`
tag, so build directly into it. See [To run §2](#to-run-every-session). Do this after
every fresh `minikube start` following a `minikube delete` (the in-cluster image is
wiped then).

**Option B — pull from GHCR.** Make the package public (GitHub → your profile →
**Packages** → `recommendation-engine` → **Package settings** → **Change visibility**
→ **Public**) and let CI build & push `:latest`. Only works once CI has pushed an image
that contains the `/ready` endpoint.

> Symptoms if this is wrong: `ImagePullBackOff` (image missing/private), or pods that
> build fine but never go Ready with `GET /ready ... 404` in the logs (stale image
> without `/ready`).

### 3. `.env` at the repo root
The secret is built from `.env` at apply time. It must contain these 5 keys:
```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...
OPENAI_API_KEY=...
SUPABASE_JWT_SECRET=...
```
`.env` is gitignored — it never gets committed. Confirm it's there:
```powershell
Test-Path .env    # must be True
```

### 4. Hosts entry for the ingress (needs admin)
On **Windows with the docker driver**, `minikube ip` (e.g. `192.168.49.2`) is inside
Docker's network and **not routable from the host** — so map `rec-engine.local` to
**`127.0.0.1`** and reach the ingress via `minikube tunnel` (see
[To run §7](#to-run-every-session)). This entry persists, so it's one-time.

Run **PowerShell as Administrator**:
```powershell
$hosts = "$env:windir\System32\drivers\etc\hosts"
if (-not (Select-String -Path $hosts -Pattern "rec-engine.local" -Quiet)) {
    Add-Content $hosts "`n127.0.0.1   rec-engine.local" -Encoding ASCII
}
```
> If you already added it pointing at `192.168.49.2`, edit that line to `127.0.0.1`.

---

## To run (every session)

### The easy way — one script
From the repo root, in **PowerShell as Administrator** (it touches the hosts file):
```powershell
powershell -ExecutionPolicy Bypass -File .\up.ps1
```
That does every step below in order and smoke-tests `/ready` at the end.

### The manual way — step by step
Run from the repo root.

**1. Start the cluster + ingress**
```powershell
minikube start --driver=docker --memory=4096 --cpus=2
minikube addons enable ingress
```

**2. Build the image into minikube** (Option A from initial setup — skip if pulling
from GHCR). Point your docker CLI at minikube's daemon, then build:
```powershell
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t ghcr.io/miguelthemigs/recommendation-engine:latest .
```
> `minikube image load` is unreliable for an existing `:latest` tag — building inside
> minikube's daemon (via `docker-env`) is the dependable way. The `docker-env` vars
> only affect the current shell; open a new window to talk to your normal docker again.

**3. Namespace + ConfigMap** — these MUST exist before the workloads, or the
api/worker pods fail with `CreateContainerConfigError`:
```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
```

**4. Secret from `.env`** (recreated each run so `.env` edits propagate):
```powershell
$keys = @("SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","SUPABASE_ANON_KEY","OPENAI_API_KEY","SUPABASE_JWT_SECRET")
$envvars = @{}
Get-Content ".env" | ForEach-Object {
    $l = $_.Trim()
    if ($l -and -not $l.StartsWith("#") -and $l.Contains("=")) {
        $i = $l.IndexOf("="); $envvars[$l.Substring(0,$i).Trim()] = $l.Substring($i+1).Trim().Trim('"').Trim("'")
    }
}
$secretArgs = @("-n","rec-engine","create","secret","generic","rec-engine-secrets")
foreach ($k in $keys) { if ($envvars[$k]) { $secretArgs += "--from-literal=$k=$($envvars[$k])" } }
kubectl -n rec-engine delete secret rec-engine-secrets --ignore-not-found
kubectl @secretArgs
```

**5. Apply the workloads**
```powershell
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/ingress.yaml
```

**6. Watch them come up** — the **api sits at `0/1` for ~30–60s** while it builds the
graph + TF-IDF index. That's the `/ready` startupProbe gating it, not a failure.
```powershell
kubectl -n rec-engine get pods -w        # Ctrl-C when all three are 1/1
# or:  k9s -n rec-engine
```

**7. Reach the API from the host.** On Windows + docker driver the ingress IP isn't
routable, so use **`minikube tunnel`** — run it in a **separate admin terminal** and
leave it running (it binds the ingress to `127.0.0.1:80`):
```powershell
minikube tunnel
```
Then (hosts already maps `rec-engine.local` → `127.0.0.1`):
```powershell
curl http://rec-engine.local/health      # 200 once the process is up
curl http://rec-engine.local/ready       # 503 while building → 200 {"ready": true}
# browse the API docs: http://rec-engine.local/docs
```
No tunnel handy? Either talk to the API directly:
```powershell
kubectl -n rec-engine port-forward svc/api 8000:8000      # → http://localhost:8000
```
…or verify the ingress path itself without admin:
```powershell
kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 18080:80
curl -H "Host: rec-engine.local" http://localhost:18080/ready
```

---

## Everyday commands

```powershell
# Worker logs (should show broker connection, NO mock banner)
kubectl -n rec-engine logs -l app=worker -f

# RabbitMQ management UI → http://localhost:15672  (guest/guest)
kubectl -n rec-engine port-forward svc/rabbitmq 15672:15672

# Live cluster view
k9s -n rec-engine

# Restart a deployment after a new image push
kubectl -n rec-engine rollout restart deployment/api deployment/worker
```

## Updating to a new image (after a code change)

Rebuild the image into minikube's daemon, then roll the deployments onto it. Easiest:
just re-run `up.ps1` (it does both). Manually:
```powershell
# 1. Build the new code into minikube's docker
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t ghcr.io/miguelthemigs/recommendation-engine:latest .
& minikube -p minikube docker-env --unset --shell powershell | Invoke-Expression

# 2. Roll api + worker onto the fresh image (graceful: new pod up, then old terminates)
kubectl -n rec-engine rollout restart deployment/api deployment/worker
kubectl -n rec-engine rollout status deployment/api

# Roll back if the new build misbehaves
kubectl -n rec-engine rollout undo deployment/api
```
Works because `imagePullPolicy: IfNotPresent` + the `:latest` tag uses whatever that tag
points to *inside minikube* — now your fresh build. Only `api`/`worker` run code;
RabbitMQ is untouched.

## Scaling (load balancing + worker throughput)

Two independent dials, both at `replicas: 1` by default:
```powershell
# More API pods — the Service + ingress load-balance requests across them
kubectl -n rec-engine scale deployment/api --replicas=3

# More workers — RabbitMQ splits queued cold-start jobs across them (competing consumers)
kubectl -n rec-engine scale deployment/worker --replicas=3
```
The `api` Service load-balances across however many API pods exist (with 1 replica there's
nothing to balance). Workers don't use the Service — RabbitMQ itself distributes jobs, one
per available worker. Scale `api` for incoming traffic, `worker` for background throughput.

> **Cycle 6 note:** once KEDA is installed (below), the **worker** dial above is owned by
> KEDA — a manual `kubectl scale deployment/worker` is reverted within one polling interval.
> See [Autoscaling the worker](#autoscaling-the-worker-keda--cycle-6) for how to reclaim
> manual control. The `api` dial is unaffected.

---

## Autoscaling the worker (KEDA — Cycle 6)

The worker pool scales **automatically on the depth of the `coldstart_jobs` queue**: a
backlog spins up more workers (up to 5), and when it drains they step back to a single warm
worker. This replaces the manual `kubectl scale` measured in Flavour 3 Cycle 5. Full
rationale (the min=1-vs-0 tradeoff, why no metrics-server) is in `FLAVOUR4_CYCLE6.md`.

### Enabling it
Autoscaling is **opt-in and separate from the everyday bring-up** — `up.ps1` does *not*
touch KEDA. After the cluster + workloads are up (`up.ps1`), run once:
```powershell
powershell -ExecutionPolicy Bypass -File .\k8s\keda-up.ps1
```
That installs a pinned KEDA (`v2.17.1`) into the `keda` namespace, waits for its operator,
and applies the `worker-scaler` ScaledObject. Tear it back down (worker returns to manual
scaling) with `.\k8s\keda-up.ps1 -Down`.

### What's involved
- **KEDA** — an event-driven autoscaler installed in the `keda` namespace by `keda-up.ps1`.
  metrics-server is **not** needed — the `rabbitmq` queue-length trigger is an external
  metric served by KEDA itself.
- **`k8s/keda-scaledobject.yaml`** — a `ScaledObject` (plus a Secret + `TriggerAuthentication`
  holding the broker URL) targeting `deployment/worker`. Reads the queue over **AMQP** with the
  same `guest:guest` creds the worker uses, but at the **fully-qualified**
  `rabbitmq.rec-engine.svc.cluster.local:5672` (the KEDA operator runs in the `keda` namespace,
  so the bare `rabbitmq` name doesn't resolve cross-namespace). Envelope: `minReplicaCount: 1`
  (warm — kept for no-regression vs the old `replicas: 1` and to guarantee the durable queue is
  declared; bootstrap was measured at ~9s, so scale-to-zero would only cost ~15–20s on the first
  job), `maxReplicaCount: 5`, trigger `value: 3` (≈ `ceil(messages_ready / 3)` workers),
  `pollingInterval: 10`, `cooldownPeriod: 120`.

### Verify it's live
```powershell
kubectl -n keda get pods                              # keda-operator etc. all Running
kubectl -n rec-engine get scaledobject                # worker-scaler, READY=True
kubectl -n rec-engine get hpa                          # keda-hpa-worker-scaler (KEDA-managed)
```

### Reclaiming manual control
KEDA owns the worker replica count while the ScaledObject exists. To scale by hand again:
```powershell
# Pin to a fixed count without deleting the ScaledObject:
kubectl -n rec-engine annotate scaledobject worker-scaler autoscaling.keda.sh/paused-replicas="3" --overwrite
# Resume autoscaling:
kubectl -n rec-engine annotate scaledobject worker-scaler autoscaling.keda.sh/paused-replicas- 
# …or remove autoscaling entirely:
kubectl -n rec-engine delete -f k8s/keda-scaledobject.yaml
```

### Demonstrating the autoscale (the Cycle 6 load-test runbook)
Goal: one time-series showing **queue depth rising → worker replicas rising → queue
draining → replicas falling back to 1**. Reuses the Cycle 5 k6 harness, but the workers must
be the **k8s deployment** (not the local-Python workers `run_load_test.ps1` starts), so we
only reuse `coldstart.js` + `queue_monitor.py` and drive them against the cluster.

1. **Flip the worker to mock-LLM mode** so jobs are ~2s and the queue actually backs up
   without burning OpenAI quota (matches the Cycle 5 convention). **Revert after the demo.**
   ```powershell
   # set MOCK_OPENAI: "true" in k8s/configmap.yaml, then:
   kubectl apply -f k8s/configmap.yaml
   kubectl -n rec-engine rollout restart deployment/worker
   ```
2. **Two port-forwards** (separate stable windows — a drop leaves gaps in the CSVs):
   ```powershell
   kubectl -n rec-engine port-forward svc/rabbitmq 15672:15672   # queue_monitor.py
   kubectl -n rec-engine port-forward svc/api 8000:8000          # k6 API_BASE
   ```
3. **Start the two recorders** (each in its own window):
   ```powershell
   python tests/load/queue_monitor.py tests/load/results/keda/queue_depth.csv
   ./tests/load/replica_monitor.ps1 tests/load/results/keda/replicas.csv
   ```
   Optional live watch for screenshots: `kubectl -n rec-engine get hpa -w` and
   `kubectl -n rec-engine get deploy worker -w`.
4. **Flood the queue with k6** (reuses `admin_pool.json`, ramps 10→50→100 VUs):
   ```powershell
   C:\tools\k6\k6-v0.50.0-windows-amd64\k6.exe run `
     --summary-export tests/load/results/keda/k6_summary.json `
     -e API_BASE=http://localhost:8000 `
     -e SUPABASE_URL=$env:SUPABASE_URL -e SUPABASE_ANON_KEY=$env:SUPABASE_ANON_KEY `
     tests/load/coldstart.js
   ```
5. **Keep the recorders running ~3 min past k6 end** so the scale-down (after the 120s
   cooldown) lands in the CSVs. Capture the evidence at peak and after drain:
   ```powershell
   kubectl -n rec-engine describe hpa keda-hpa-worker-scaler   # external metric + decision
   kubectl -n rec-engine get events --sort-by=.lastTimestamp   # SuccessfulRescale events
   ```
6. **Revert mock mode**: set `MOCK_OPENAI: "false"` in `k8s/configmap.yaml`,
   `kubectl apply` it, `rollout restart deployment/worker`, and confirm the worker log shows
   **no mock banner**.

> **Observed shape:** a new worker is ready in ~9s (measured pod-create-to-ready, image cached),
> so the scale-up is paced by KEDA's 10s poll + the HPA's ~15s step cadence, not the bootstrap.
> In the demo the pool stepped `1 → 4` tracking `ceil(messages_ready / 3)`, held, then stepped
> back to `1` after the cooldown once the queue drained — driven by KEDA's `SuccessfulRescale`
> events, not a human.

## Stopping / tearing down

```powershell
# Pause — keeps all state, fast to resume with `minikube start`
minikube stop

# Remove just the app (keeps the cluster)
kubectl delete namespace rec-engine

# Nuke everything (cluster + state) — IP may change afterwards
minikube delete
```

---

## Troubleshooting

### `CreateContainerConfigError` on api / worker
A referenced ConfigMap or Secret is missing. Check both exist:
```powershell
kubectl -n rec-engine get configmap,secret
```
You want `configmap/rec-engine-config` (4 keys) and `secret/rec-engine-secrets` (5 keys).
Re-apply whichever is missing (step 2 / step 3). The kubelet retries automatically —
no need to delete the pods.

### `ImagePullBackOff`
The GHCR package isn't public, or the image name is wrong. Fix visibility
([initial setup §2](#2-make-the-ghcr-image-public)), then:
```powershell
kubectl -n rec-engine rollout restart deployment/api deployment/worker
```

### api stuck at `0/1` for more than ~2 minutes
Check the logs and the readiness probe:
```powershell
kubectl -n rec-engine logs -l app=api
kubectl -n rec-engine describe pod -l app=api
```
A crash usually means it can't reach Supabase — verify the secret keys (and that the
Supabase project isn't **paused** — free-tier projects sleep after inactivity).

### `scaledobject/worker-scaler` shows `READY=False`
- KEDA operator up? (`kubectl -n keda get pods` — all Running). If the ScaledObject was
  applied before the operator/webhook was ready it can be rejected — re-apply
  `kubectl apply -f k8s/keda-scaledobject.yaml`.
- Bad trigger metric usually means the broker is unreachable or the queue name is wrong.
  Check the operator logs: `kubectl -n keda logs deploy/keda-operator | findstr rabbitmq`.
  The `queueName` MUST be exactly `coldstart_jobs` (matches `config.COLDSTART_QUEUE`).

### The IP changed after `minikube delete`
`rec-engine.local` points at the old IP. Update the hosts line (admin PowerShell):
```powershell
minikube ip      # note the new IP, edit C:\Windows\System32\drivers\etc\hosts
```

### `curl http://rec-engine.local/...` hangs or refuses
- All pods `1/1`? (`kubectl -n rec-engine get pods`)
- Ingress addon enabled? (`minikube addons list | findstr ingress`)
- Hosts entry present and matching `minikube ip`?

---

## Public access — Vercel + Cloudflare quick tunnel

The frontend runs on **Vercel**; the minikube ingress is exposed publicly by an
**in-cluster cloudflared quick tunnel** (`k8s/cloudflared.yaml`). The tunnel is
**outbound-only** — no router/firewall changes, and the local `port-forward` bridge above
is *not* needed for the public path. The tradeoff: a quick tunnel is anonymous and free
but its `https://<random>.trycloudflare.com` URL **rotates on every cloudflared (re)start**
(including `minikube stop`/`start`).

### One-time setup
- **Vercel project** importing this repo: **Root Directory = `frontend`**, **Framework
  Preset = Vite**. Production env vars: `VITE_API_URL` (set per session, below),
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (from `frontend/.env`).
- **CORS** — already handled: `k8s/configmap.yaml` sets `ALLOWED_ORIGIN_REGEX` to match the
  project's `*.vercel.app` domains. No per-session edit.
- **Supabase → Authentication → URL Configuration** — Site URL + an Additional Redirect URL
  (`https://<your-project>.vercel.app/**`) pointing at the Vercel domain; keep
  `http://localhost:5173/**` for local dev.
- *(Optional)* **Vercel CLI** for scripted env updates: `npm i -g vercel; vercel login;
  cd frontend; vercel link`.

### Per-session runbook (the rotating-URL dance)
1. **Admin PowerShell**, repo root — `up.ps1` brings up the tunnel and prints the URL:
   ```powershell
   .\up.ps1
   ```
   Look for `PUBLIC URL: https://<...>.trycloudflare.com`.
2. Point Vercel at it and **rebuild** (`VITE_*` is baked at build time):
   - **Recommended:** set `VITE_API_URL` in the Vercel dashboard, then **Deployments →
     ⋯ → Redeploy** (uncheck build cache) — or push to `main` to trigger a git deploy.
   - The script's `.\tunnel-url.ps1 -UpdateVercel` sets the env var but its `vercel --prod`
     step currently flips the Vercel framework preset to FastAPI (see troubleshooting) —
     prefer the git/dashboard redeploy until that's fixed.
3. Verify:
   ```powershell
   Invoke-RestMethod https://<...>.trycloudflare.com/ready   # -> ready : True
   ```
4. Open the Vercel URL and use the app.

### Public-path troubleshooting
- **No URL in the cloudflared logs** — the banner appears ~5s after the pod is Running;
  `kubectl -n rec-engine logs deploy/cloudflared`. The metrics endpoint
  `:2000/quicktunnel` also returns the assigned hostname.
- **nginx 404 through the tunnel** — host-header mismatch. cloudflared rewrites the host to
  `rec-engine.local` (`--http-host-header`) to match the ingress rule; confirm that arg.
- **Cloudflare error 1033 / tunnel won't establish** — origin unreachable, or QUIC (UDP
  7844) blocked on the network. The manifest already pins `--protocol http2`; if it still
  fails, the cluster/ingress may be down.
- **Vercel build detects "FastAPI" / `No FastAPI entrypoint found`** — the project's
  Framework Preset got set to FastAPI (Vercel sees `main.py`/`pyproject.toml` at the repo
  root). Fix: **Settings → Build and Deployment → Framework Preset → Vite**, Root Directory
  `frontend`. Deploy via git/dashboard, not `vercel --prod`, which re-triggers this.
- **Vercel build fails `npm run build exited with 2`** — a TypeScript error
  (`tsc && vite build`); reproduce locally with `cd frontend && npm run build` (it won't
  show in `vite dev`).
- **No Supabase confirmation email on public sign-up** — Supabase's built-in email is
  rate-limited/best-effort. For demos, disable "Confirm email" (Authentication → Sign In /
  Providers → Email) or wire a custom SMTP provider.
