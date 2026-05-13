<#
tests/load/run_load_test.ps1
─────────────────────────────
Orchestrate a full load-test run:
  1. Stop any existing worker.py processes
  2. Start N copies of `MOCK_OPENAI=true python worker.py` as background jobs
  3. Start queue_monitor.py writing queue_depth.csv
  4. Run k6 with CSV + HTML dashboard export
  5. Tear everything down

Usage:
  ./tests/load/run_load_test.ps1 -Workers 1
  ./tests/load/run_load_test.ps1 -Workers 2
  ./tests/load/run_load_test.ps1 -Workers 3

Prerequisites:
  - .env file with SUPABASE_URL, SUPABASE_ANON_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
  - API running (uvicorn main:app) on $API_BASE
  - RabbitMQ running on localhost:5672 with management plugin on :15672
  - k6 installed and on PATH
  - Python venv active
#>

param(
  [int]$Workers = 1,
  [string]$ApiBase = "http://localhost:8000",
  [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

# ── Load env vars from .env so k6 sees them ────────────────────────────────
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)\s*$') {
      $name = $Matches[1]
      $value = $Matches[2].Trim('"').Trim("'")
      [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
  }
} else {
  Write-Warning "$EnvFile not found — make sure env vars are set in the shell"
}

foreach ($v in @("SUPABASE_URL", "SUPABASE_ANON_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD")) {
  if (-not [Environment]::GetEnvironmentVariable($v, "Process")) {
    throw "Missing required env var: $v"
  }
}

# ── Output paths ───────────────────────────────────────────────────────────
$RunDir = "tests/load/results/${Workers}worker$(if ($Workers -gt 1) { 's' })"
$null = New-Item -ItemType Directory -Force -Path $RunDir
$K6Csv      = Join-Path $RunDir "k6_raw.csv"
$K6Html     = Join-Path $RunDir "k6_report.html"
$QueueCsv   = Join-Path $RunDir "queue_depth.csv"
$Summary    = Join-Path $RunDir "k6_summary.json"

Write-Host "──────────────────────────────────────────────────────────────"
Write-Host " Cycle 5 load test — $Workers worker(s)"
Write-Host " Results → $RunDir"
Write-Host "──────────────────────────────────────────────────────────────"

# ── 1. Kill any existing worker.py processes ───────────────────────────────
Write-Host "`n[1/5] Stopping existing worker.py processes..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -and $_.CommandLine -match 'worker\.py' } |
  ForEach-Object {
    Write-Host "  killing PID $($_.ProcessId)"
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
  }
Start-Sleep -Seconds 2

# ── 2. Start N workers with MOCK_OPENAI=true ───────────────────────────────
Write-Host "`n[2/5] Starting $Workers worker(s) with MOCK_OPENAI=true..."
$workerJobs = @()
for ($i = 1; $i -le $Workers; $i++) {
  $logPath = Join-Path $RunDir "worker_${i}.log"
  $job = Start-Job -ScriptBlock {
    param($logPath, $workdir)
    Set-Location $workdir
    $env:MOCK_OPENAI = "true"
    $env:MOCK_OPENAI_DELAY_MS = "2000"
    python worker.py *>&1 | Tee-Object -FilePath $logPath
  } -ArgumentList $logPath, (Get-Location).Path
  $workerJobs += $job
  Write-Host "  worker $i → JobId=$($job.Id), log=$logPath"
}
Write-Host "  Waiting 8s for workers to bootstrap..."
Start-Sleep -Seconds 8

# ── 3. Start queue monitor sidecar ─────────────────────────────────────────
Write-Host "`n[3/5] Starting queue monitor → $QueueCsv"
$monitorJob = Start-Job -ScriptBlock {
  param($csv, $workdir)
  Set-Location $workdir
  python tests/load/queue_monitor.py $csv
} -ArgumentList $QueueCsv, (Get-Location).Path
Start-Sleep -Seconds 2

# ── 4. Run k6 ──────────────────────────────────────────────────────────────
Write-Host "`n[4/5] Running k6..."
$env:K6_WEB_DASHBOARD = "true"
$env:K6_WEB_DASHBOARD_EXPORT = $K6Html
$env:K6_WEB_DASHBOARD_PERIOD = "1s"

$k6Args = @(
  "run",
  "--out", "csv=$K6Csv",
  "--summary-export", $Summary,
  "-e", "API_BASE=$ApiBase",
  "-e", "SUPABASE_URL=$($env:SUPABASE_URL)",
  "-e", "SUPABASE_ANON_KEY=$($env:SUPABASE_ANON_KEY)",
  "-e", "ADMIN_EMAIL=$($env:ADMIN_EMAIL)",
  "-e", "ADMIN_PASSWORD=$($env:ADMIN_PASSWORD)",
  "tests/load/coldstart.js"
)

try {
  & k6 $k6Args
} catch {
  Write-Warning "k6 exited with error: $_"
}

# ── 5. Tear down ───────────────────────────────────────────────────────────
Write-Host "`n[5/5] Stopping monitor and workers..."
Stop-Job -Job $monitorJob -ErrorAction SilentlyContinue
Receive-Job -Job $monitorJob | Out-Null
Remove-Job -Job $monitorJob -Force -ErrorAction SilentlyContinue

# Give workers up to 30s to drain remaining jobs before kill
Write-Host "  Waiting up to 30s for queue to drain..."
$drainStart = Get-Date
while (((Get-Date) - $drainStart).TotalSeconds -lt 30) {
  try {
    $cred = "$($env:RABBITMQ_USER -or 'guest'):$($env:RABBITMQ_PASS -or 'guest')"
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($cred)
    $b64 = [System.Convert]::ToBase64String($bytes)
    $resp = Invoke-RestMethod -Uri "http://localhost:15672/api/queues/%2F/coldstart_jobs" `
                              -Headers @{ Authorization = "Basic $b64" } -ErrorAction Stop
    if ($resp.messages -eq 0 -and $resp.messages_unacknowledged -eq 0) {
      Write-Host "  queue drained ✓"
      break
    }
  } catch { }
  Start-Sleep -Seconds 2
}

foreach ($job in $workerJobs) {
  Stop-Job -Job $job -ErrorAction SilentlyContinue
  Receive-Job -Job $job | Out-Null
  Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -and $_.CommandLine -match 'worker\.py' } |
  ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }

Write-Host "`n──────────────────────────────────────────────────────────────"
Write-Host " Done. Artifacts:"
Write-Host "   k6 HTML dashboard → $K6Html"
Write-Host "   k6 raw CSV        → $K6Csv"
Write-Host "   k6 summary JSON   → $Summary"
Write-Host "   queue depth CSV   → $QueueCsv"
Write-Host "──────────────────────────────────────────────────────────────"
