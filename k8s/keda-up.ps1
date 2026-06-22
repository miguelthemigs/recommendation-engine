<#
  k8s/keda-up.ps1 - install KEDA and enable worker autoscaling (Flavour 4 Cycle 6).

  This is SEPARATE from up.ps1 on purpose: autoscaling is the optional Cycle 6 demo,
  not part of the everyday backend bring-up. Run up.ps1 first to get the cluster +
  workloads, then run this once to layer KEDA on top.

      powershell -ExecutionPolicy Bypass -File .\k8s\keda-up.ps1

  What it does:
    1. Installs a PINNED KEDA into the `keda` namespace (reproducible; never floats).
    2. Waits for the KEDA operator + metrics-apiserver to be ready.
    3. Applies k8s/keda-scaledobject.yaml -> KEDA now autoscales `deployment/worker`
       on the depth of the `coldstart_jobs` queue (min 1 warm / max 5).

  Tear it back down (return the worker to manual `kubectl scale`):
      powershell -ExecutionPolicy Bypass -File .\k8s\keda-up.ps1 -Down

  Note: the worker can burst to 5 replicas (5 x 256Mi requested). On a 4GB minikube
  that is schedulable but tight alongside the other workloads + KEDA's ~300-400MB.
  If pods sit Pending under load, recreate the cluster larger:
  `minikube delete; minikube start --driver=docker --memory=6144 --cpus=2` then re-run up.ps1.

  Run from the repo root (the folder with k8s/).
#>
param(
    [switch]$Down
)

$ErrorActionPreference = "Stop"
$NS = "rec-engine"
# Pinned for reproducibility -- bump deliberately, never float to `latest`.
$KEDA_VERSION = "v2.17.1"
$KEDA_MANIFEST = "https://github.com/kedacore/keda/releases/download/$KEDA_VERSION/keda-$($KEDA_VERSION.TrimStart('v')).yaml"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

if ($Down) {
    Step "Removing the worker ScaledObject (worker returns to manual scaling)"
    kubectl delete -f k8s/keda-scaledobject.yaml --ignore-not-found
    Step "Uninstalling KEDA ($KEDA_VERSION)"
    # --server-side delete mirrors the apply; ignore-not-found makes it idempotent.
    kubectl delete -f $KEDA_MANIFEST --ignore-not-found
    Write-Host "`nKEDA removed. The worker is back to `replicas: 1` under manual control." -ForegroundColor Green
    return
}

# -- 1. Install KEDA ---------------------------------------------------------
# --server-side avoids the "metadata.annotations too long" error on KEDA's large CRDs.
# Idempotent: re-applying an existing install is a no-op.
Step "Installing KEDA ($KEDA_VERSION)"
kubectl apply --server-side -f $KEDA_MANIFEST

# -- 2. Wait for the operator ------------------------------------------------
# A ScaledObject applied before the admission webhook is ready gets rejected, so gate on this.
Step "Waiting for KEDA operator (first run pulls images - can take a minute)"
kubectl -n keda rollout status deployment/keda-operator --timeout=240s
kubectl -n keda rollout status deployment/keda-operator-metrics-apiserver --timeout=240s

# -- 3. Enable worker autoscaling --------------------------------------------
# Requires the `worker` Deployment to exist already (run up.ps1 first).
Step "Applying the worker ScaledObject"
kubectl apply -f k8s/keda-scaledobject.yaml

Write-Host "`n------------------------------------------------------------" -ForegroundColor Green
Write-Host " KEDA is autoscaling the worker on `coldstart_jobs` queue depth." -ForegroundColor Green
Write-Host " Verify:  kubectl -n $NS get scaledobject,hpa" -ForegroundColor White
Write-Host " Demo runbook: k8s/README.md -> Autoscaling the worker (KEDA)" -ForegroundColor White
Write-Host "------------------------------------------------------------`n" -ForegroundColor Green
