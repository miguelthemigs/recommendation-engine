# Cycle 4 — Running the Backend in Kubernetes (minikube): Setup Tutorial

A practical, start-to-finish guide to getting the recommendation-engine backend running
in a local Kubernetes cluster. It follows the Cycle 4 plan exactly (namespace `rec-engine`,
public GHCR image, `/ready` gate, end-to-end verification against live Supabase).

---

## 0. What you're about to build

Three Deployments (API, worker, RabbitMQ broker) running inside a local Kubernetes
cluster on your own machine, with config in a ConfigMap, secrets in a Secret, health
probes wiring it all together, and an Ingress so you can reach it at `rec-engine.local`.
By the end, `register → watchlist → cold-start` works end-to-end against your live Supabase.

---

## 1. Install the tools (one time)

You need three things: Docker (to run the cluster), `minikube`, and `kubectl`.

- **Docker Desktop** is the simplest driver on Windows/Mac. Install it and make sure it's running.
- **minikube**: Windows `winget install minikube`, Mac `brew install minikube`, Linux grab the binary from the minikube site.
- **kubectl**: Windows `winget install kubectl`, Mac `brew install kubectl`. (minikube can also provide it via `minikube kubectl --`.)

Verify:

```bash
minikube version
kubectl version --client
```

---

## 2. Start the cluster

```bash
minikube start --driver=docker --memory=4096 --cpus=2
```

The extra memory matters: your in-RAM graph plus TF-IDF index is memory-heavy, and the
default 2GB gets tight once both the API and worker build their indexes.

Enable the ingress controller (your `ingress.yaml` needs it):

```bash
minikube addons enable ingress
```

Confirm the cluster is alive:

```bash
kubectl get nodes        # one node, status Ready
```

---

## 3. Make sure the image is pullable

Per the plan, make the GHCR package **public** so minikube pulls it with no credentials
(no `imagePullSecret` needed). In GitHub: open the `recommendation-engine` package →
**Package settings → Change visibility → Public**.

---

## 4. Add the one code change first (the `/ready` gate)

Before deploying, make sure the `/ready` endpoint is in `main.py` and pushed, so CI builds
an image that actually has it. The readiness probe depends on this endpoint existing in the
image you pull. Quick local check:

```bash
curl -i localhost:8000/ready    # 503 while building, 200 once graph + tfidf are ready
```

---

## 5. Apply the manifests in order

Order matters: the namespace must exist first, and config/secret must exist before the pods
that read them. From your repo root:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
```

Now the **Secret** — never committed, created imperatively from your `.env` values:

```bash
kubectl -n rec-engine create secret generic rec-engine-secrets \
  --from-literal=SUPABASE_URL=... \
  --from-literal=SUPABASE_SERVICE_ROLE_KEY=... \
  --from-literal=SUPABASE_ANON_KEY=... \
  --from-literal=OPENAI_API_KEY=...
```

(Add `SUPABASE_JWT_SECRET` too if your `.env` has it.) Then the rest:

```bash
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/ingress.yaml
```

Once everything's correct, `kubectl apply -f k8s/` applies the whole folder at once. For the
first bring-up, doing it in order makes failures easier to read.

---

## 6. Watch it come up

```bash
kubectl -n rec-engine get pods -w
```

What you want to see, and what each state tells you:

- **RabbitMQ** goes `Running` and `Ready` first (it boots fast).
- **API** goes `Running` quickly but stays `0/1 Ready` for 30–60 seconds. That's the
  `startupProbe` giving the store load and index build time, and the `readinessProbe`
  correctly holding the pod out of the Service until `/ready` returns 200. **This is the
  proof your gate works.**
- **Worker** goes `Running`; it has no HTTP probe, so check it with logs.

Check the worker connected to the broker and isn't mocking:

```bash
kubectl -n rec-engine logs deploy/worker
```

Look for the broker connection line and the **absence** of the `MOCK_OPENAI` banner
(since `MOCK_OPENAI=false` for an honest end-to-end run).

---

## 7. Reach it from your machine

Ingress routes by hostname, so point `rec-engine.local` at the cluster IP:

```bash
minikube ip                 # e.g. 192.168.49.2
```

Add a line to your hosts file (`C:\Windows\System32\drivers\etc\hosts` on Windows,
`/etc/hosts` on Mac/Linux):

```
192.168.49.2   rec-engine.local
```

Test the two operational endpoints:

```bash
curl http://rec-engine.local/health        # 200 — liveness, only needs the store
curl -i http://rec-engine.local/ready       # 200 "ready": true (was 503 while building)
```

If `curl` hangs on the Docker driver, run `minikube tunnel` in a separate terminal.

---

## 8. The UIs — how to actually *see* it running

### Kubernetes Dashboard (the main visual view)

```bash
minikube dashboard
```

Opens a browser tab with a full web UI of the cluster. Select the `rec-engine` namespace
and you'll see every pod, deployment, and service with live status, resource usage, and
clickable logs and events. You can literally watch the API pod sit at `0/1` until `/ready`
flips, then go green. **Best thing to have open during a demo.**

### RabbitMQ management UI (watch the queue)

```bash
kubectl -n rec-engine port-forward svc/rabbitmq 15672:15672
```

Open `http://localhost:15672` (guest/guest). Watch messages get queued and acked during the
cold-start step.

### Your frontend (the end-user view)

Point a local frontend's `VITE_API_URL` at `http://rec-engine.local` and use the app normally.

### k9s (optional, terminal UI)

If you prefer a terminal dashboard, install `k9s` for a fast keyboard-driven view of pods,
logs, and events. Not required — `minikube dashboard` covers the visual need.

---

## 9. The full end-to-end flow

Point the frontend at `http://rec-engine.local` (or curl directly): register a user, add to
the watchlist, trigger a cold-start, then poll `GET /jobs/{job_id}` until `completed`. A
completed job proves the whole loop ran **inside the cluster**:
API → RabbitMQ → worker → OpenAI → Supabase write → poll round-trip.

---

## 10. Capture evidence for the cycle doc

```bash
kubectl -n rec-engine get pods                 # all Running, api 1/1 Ready
kubectl -n rec-engine describe pod <api-pod>   # shows probe transitions
```

The money shots: `/ready` going 503 → 200, the API pod flipping to Ready only after the
build, the RabbitMQ UI with a processed message, and one completed cold-start job. The
Dashboard view of the healthy namespace is a strong screenshot too.

---

## Troubleshooting the usual first-run snags

- **API pod stuck `0/1` forever** → the build is failing or `/ready` never returns 200.
  Check `kubectl -n rec-engine logs deploy/api`. Usually a bad Supabase secret or an index
  build error.
- **`ImagePullBackOff`** → the GHCR package isn't public yet (step 3), or the image tag
  doesn't exist. Use `:latest` for first bring-up, then the immutable `:sha-<commit>` tag
  for reproducibility.
- **`CreateContainerConfigError`** → a key referenced via `envFrom` is missing from the
  ConfigMap or Secret. `kubectl -n rec-engine describe pod <pod>` names the missing key.
- **Pod `OOMKilled` or restarting** → bump the memory limit in `api.yaml`/`worker.yaml`; the
  in-RAM graph needs headroom. Watch usage with `kubectl -n rec-engine top pod`
  (needs `minikube addons enable metrics-server`).
- **Ingress 404 or hang** → ingress addon not enabled, hosts file not pointing at
  `minikube ip`, or `minikube tunnel` not running.

---

## Resetting when you want a clean slate

```bash
kubectl delete namespace rec-engine     # removes everything you applied
# or nuke the whole cluster:
minikube delete && minikube start --driver=docker --memory=4096 --cpus=2
```

---

## Two things to expect (from the plan, not bugs)

- The broker uses an ephemeral `emptyDir`, so **restarting the RabbitMQ pod loses its queue
  state** — an accepted Cycle 4 decision.
- The CI pipeline can't reach your laptop's minikube, so **`kubectl apply` stays a manual
  step** — the honest limitation flagged for the cycle doc.

## SCRIPT

<#
  up.ps1 — bring the whole rec-engine backend up in minikube.
  Run from your repo root (folder with the k8s/ directory and .env).
      powershell -ExecutionPolicy Bypass -File .\up.ps1
#>

$ErrorActionPreference = "Stop"
$NS = "rec-engine"

# start cluster + ingress
minikube start --driver=docker --memory=4096 --cpus=2
minikube addons enable ingress

# namespace + config
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml

# secret from .env (recreated each run)
$keys = @("SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","SUPABASE_ANON_KEY","OPENAI_API_KEY","SUPABASE_JWT_SECRET")
$envvars = @{}
Get-Content ".env" | ForEach-Object {
    $l = $_.Trim()
    if ($l -and -not $l.StartsWith("#") -and $l.Contains("=")) {
        $i = $l.IndexOf("="); $envvars[$l.Substring(0,$i).Trim()] = $l.Substring($i+1).Trim().Trim('"').Trim("'")
    }
}
$args = @("-n",$NS,"create","secret","generic","rec-engine-secrets")
foreach ($k in $keys) { if ($envvars[$k]) { $args += "--from-literal=$k=$($envvars[$k])" } }
kubectl -n $NS delete secret rec-engine-secrets --ignore-not-found | Out-Null
kubectl @args

# workloads
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/ingress.yaml

# wait for ready (api sits at 0/1 ~30-60s while it builds — that's /ready working)
kubectl -n $NS wait --for=condition=ready pod -l app=rabbitmq --timeout=120s
kubectl -n $NS wait --for=condition=ready pod -l app=api --timeout=240s

# hosts entry for the ingress
$ip = (minikube ip).Trim()
$hosts = "$env:windir\System32\drivers\etc\hosts"
if (-not (Select-String -Path $hosts -Pattern "rec-engine.local" -Quiet)) {
    Add-Content $hosts "`n$ip   rec-engine.local" -Encoding ASCII
}

kubectl -n $NS get pods
Write-Host "`nUp. Try:  curl http://rec-engine.local/ready   |   minikube dashboard" -ForegroundColor Green