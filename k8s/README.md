# Running the rec-engine backend on minikube

This deploys the backend (API + worker + RabbitMQ broker) into a local minikube
cluster. The frontend is **not** here — it runs locally (`cd frontend && npm run dev`)
or on Vercel (Cycle 5). Supabase is managed/external.

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
A crash usually means it can't reach Supabase — verify the secret keys.

### The IP changed after `minikube delete`
`rec-engine.local` points at the old IP. Update the hosts line (admin PowerShell):
```powershell
minikube ip      # note the new IP, edit C:\Windows\System32\drivers\etc\hosts
```

### `curl http://rec-engine.local/...` hangs or refuses
- All pods `1/1`? (`kubectl -n rec-engine get pods`)
- Ingress addon enabled? (`minikube addons list | findstr ingress`)
- Hosts entry present and matching `minikube ip`?
