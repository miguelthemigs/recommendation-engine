<#
  up.ps1 — bring the whole rec-engine backend up in minikube, end to end.

  Does EVERYTHING: start cluster → build the image into minikube → create secret from
  .env → deploy api/worker/rabbitmq → wait until healthy → fix the hosts entry → open
  the bridge so http://rec-engine.local works in your browser.

  Run from the repo root (the folder with k8s/ and .env), in an ADMIN PowerShell
  (it edits the hosts file and binds port 80):

      powershell -ExecutionPolicy Bypass -File .\up.ps1

  The last step (the bridge) stays running on purpose — leave the window open while you
  use the app. Press Ctrl-C to stop it; the cluster keeps running in the background.
#>

$ErrorActionPreference = "Stop"
$NS = "rec-engine"
$IMAGE = "ghcr.io/miguelthemigs/recommendation-engine:latest"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# ── 1. Cluster + ingress addon ──────────────────────────────────────────────
Step "Starting minikube (docker driver, 4GB / 2 CPU)"
minikube start --driver=docker --memory=4096 --cpus=2
Step "Enabling ingress addon"
minikube addons enable ingress

# ── 2. Build the image INTO minikube's docker daemon ────────────────────────
# This is the reliable way to get our code (incl. the /ready endpoint) into the
# cluster. `minikube image load` does NOT dependably overwrite an existing :latest
# tag, so we point docker at minikube's daemon and build there directly. Cached after
# the first run, so this is fast unless the cluster was deleted.
Step "Building image into minikube ($IMAGE)"
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t $IMAGE .
# Restore the normal docker context for the rest of the script / your shell.
& minikube -p minikube docker-env --unset --shell powershell | Invoke-Expression

# ── 3. Namespace + non-secret config ────────────────────────────────────────
Step "Applying namespace + ConfigMap"
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml

# ── 4. Secret, built fresh from .env each run ───────────────────────────────
# Mirrors the .env.example (tracked) / .env (gitignored) pattern — the real keys
# never touch a committed file. Recreated each run so .env edits propagate.
Step "Creating rec-engine-secrets from .env"
if (-not (Test-Path ".env")) { throw ".env not found in repo root — cannot build the Secret." }

$keys = @("SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","SUPABASE_ANON_KEY","OPENAI_API_KEY","SUPABASE_JWT_SECRET")
$envvars = @{}
Get-Content ".env" | ForEach-Object {
    $l = $_.Trim()
    if ($l -and -not $l.StartsWith("#") -and $l.Contains("=")) {
        $i = $l.IndexOf("=")
        $envvars[$l.Substring(0, $i).Trim()] = $l.Substring($i + 1).Trim().Trim('"').Trim("'")
    }
}

# NOTE: $args is a reserved automatic variable in PowerShell — use a private name.
$secretArgs = @("-n", $NS, "create", "secret", "generic", "rec-engine-secrets")
foreach ($k in $keys) {
    if ($envvars[$k]) { $secretArgs += "--from-literal=$k=$($envvars[$k])" }
    else { Write-Host "   (warning: $k missing from .env — skipping)" -ForegroundColor Yellow }
}
kubectl -n $NS delete secret rec-engine-secrets --ignore-not-found | Out-Null
kubectl @secretArgs

# ── 5. Workloads ────────────────────────────────────────────────────────────
Step "Applying workloads (rabbitmq → api → worker → ingress)"
kubectl apply -f k8s/rabbitmq.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/ingress.yaml
# cloudflared exposes the ingress on a public https://<x>.trycloudflare.com URL
# (Cycle 5). Outbound-only, so it needs no inbound port-forward — the bridge in
# step 8 below is for LOCAL access only.
kubectl apply -f k8s/cloudflared.yaml
# If pods already existed (re-run), force them onto the freshly built image.
kubectl -n $NS rollout restart deployment/api deployment/worker | Out-Null

# ── 6. Wait for ready ───────────────────────────────────────────────────────
# The API sits at 0/1 for ~30-60s while it builds the graph + TF-IDF — that's the
# /ready gate (startupProbe) doing its job, not a failure.
Step "Waiting for RabbitMQ"
kubectl -n $NS wait --for=condition=ready pod -l app=rabbitmq --timeout=120s
Step "Waiting for API (0/1 while it builds — expected)"
kubectl -n $NS rollout status deployment/api --timeout=240s
Step "Waiting for worker"
kubectl -n $NS rollout status deployment/worker --timeout=240s
Step "Waiting for cloudflared (public tunnel)"
kubectl -n $NS rollout status deployment/cloudflared --timeout=120s

# ── 7. Hosts entry → 127.0.0.1 ──────────────────────────────────────────────
# Windows + docker driver: `minikube ip` is NOT routable from the host, so the
# hostname must point at 127.0.0.1 and reach the cluster through the bridge (step 8).
$hosts = "$env:windir\System32\drivers\etc\hosts"
$line  = Select-String -Path $hosts -Pattern "rec-engine.local" -Quiet
if (-not $line) {
    Step "Adding hosts entry: 127.0.0.1 rec-engine.local"
    Add-Content $hosts "`n127.0.0.1   rec-engine.local" -Encoding ASCII
} else {
    Step "Ensuring rec-engine.local → 127.0.0.1 in hosts"
    (Get-Content $hosts) -replace '^\s*\d+\.\d+\.\d+\.\d+\s+rec-engine\.local\s*$', '127.0.0.1   rec-engine.local' |
        Set-Content $hosts -Encoding ASCII
}

kubectl -n $NS get pods

# ── 7b. Public tunnel URL (Cycle 5) ─────────────────────────────────────────
# Pull the fresh trycloudflare URL out of the cloudflared logs and remind the
# user to push it to Vercel. This is the per-session "rotating URL" dance.
Step "Fetching the public tunnel URL"
$tunnel = $null
for ($i = 0; $i -lt 30; $i++) {
    $logs = kubectl -n $NS logs deploy/cloudflared --tail=200 2>$null
    if ($logs) {
        $m = [regex]::Match(($logs -join "`n"), 'https://[a-z0-9-]+\.trycloudflare\.com')
        if ($m.Success) { $tunnel = $m.Value; break }
    }
    Start-Sleep -Seconds 2
}
Write-Host "`n────────────────────────────────────────────────────────────" -ForegroundColor Magenta
if ($tunnel) {
    Write-Host " PUBLIC URL:  $tunnel" -ForegroundColor Magenta
    Write-Host " Push it to Vercel:  .\tunnel-url.ps1 -UpdateVercel" -ForegroundColor White
} else {
    Write-Host " Tunnel URL not in logs yet. Check:  kubectl -n $NS logs deploy/cloudflared" -ForegroundColor Yellow
}
Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor Magenta

# ── 8. Open the bridge (stays running) ──────────────────────────────────────
Write-Host "`n────────────────────────────────────────────────────────────" -ForegroundColor Green
Write-Host " All pods healthy. Opening the bridge to http://rec-engine.local" -ForegroundColor Green
Write-Host " Open in your browser:  http://rec-engine.local/docs" -ForegroundColor White
Write-Host " (use /docs, /health or /ready — bare rec-engine.local 404s by design)" -ForegroundColor DarkGray
Write-Host " Leave THIS window open. Ctrl-C stops the bridge; the cluster keeps running." -ForegroundColor Green
Write-Host "────────────────────────────────────────────────────────────`n" -ForegroundColor Green
kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 80:80
