<#
  tests/load/replica_monitor.ps1
  ------------------------------
  Worker-replica sidecar for the Cycle 6 KEDA autoscaling demo. The sibling of
  queue_monitor.py: that one samples the QUEUE depth, this one samples how many
  worker pods KEDA is running in response. Plot the two together and you get the
  headline graph of the cycle (backlog rises -> replicas rise -> backlog drains ->
  replicas fall back to the warm minimum).

  Samples once per second and writes a CSV row:
      timestamp_iso, ready_replicas, hpa_current, hpa_desired

  - ready_replicas : worker Deployment .status.readyReplicas (empty -> 0)
  - hpa_current    : currentReplicas on the KEDA-managed HPA
  - hpa_desired    : desiredReplicas on the KEDA-managed HPA (what KEDA is asking for)

  KEDA names its managed HPA `keda-hpa-<scaledobject-name>` -> `keda-hpa-worker-scaler`.
  Confirm with:  kubectl -n rec-engine get hpa

  Run alongside k6 + queue_monitor.py (needs kubectl pointed at the cluster):
      ./tests/load/replica_monitor.ps1 tests/load/results/keda/replicas.csv

  Stop with Ctrl+C.
#>
param(
    [Parameter(Mandatory = $true)] [string]$Output,
    [string]$Namespace = "rec-engine",
    [string]$Hpa = "keda-hpa-worker-scaler",
    [double]$IntervalSeconds = 1.0
)

$ErrorActionPreference = "Continue"  # a single failed kubectl read must not kill the loop

$dir = Split-Path -Parent $Output
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

"timestamp_iso,ready_replicas,hpa_current,hpa_desired" | Out-File -FilePath $Output -Encoding utf8

Write-Host "[replicas] sampling deploy/worker + hpa/$Hpa every $IntervalSeconds s -> $Output"
Write-Host "[replicas] press Ctrl+C to stop"

$samples = 0
while ($true) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    # readyReplicas is ABSENT (not 0) before any pod is ready -> coerce empty to 0.
    $ready = kubectl -n $Namespace get deploy worker -o jsonpath='{.status.readyReplicas}' 2>$null
    if ([string]::IsNullOrWhiteSpace($ready)) { $ready = 0 }

    # The KEDA-managed HPA may not exist until the ScaledObject activates -> coerce to 0.
    $cur = kubectl -n $Namespace get hpa $Hpa -o jsonpath='{.status.currentReplicas}' 2>$null
    $des = kubectl -n $Namespace get hpa $Hpa -o jsonpath='{.status.desiredReplicas}' 2>$null
    if ([string]::IsNullOrWhiteSpace($cur)) { $cur = 0 }
    if ([string]::IsNullOrWhiteSpace($des)) { $des = 0 }

    "$ts,$ready,$cur,$des" | Add-Content -Path $Output
    $samples++
    if ($samples % 10 -eq 0) {
        Write-Host "[replicas] $ts ready=$ready hpa_current=$cur hpa_desired=$des"
    }

    Start-Sleep -Seconds $IntervalSeconds
}
