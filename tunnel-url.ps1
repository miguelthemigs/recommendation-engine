<#
  tunnel-url.ps1 - get (and optionally push) the current TryCloudflare quick-tunnel URL.

  The quick tunnel mints a fresh https://<x>.trycloudflare.com hostname every time the
  cloudflared pod (re)starts. This script reads that URL out of the pod logs.

  Usage (from repo root, normal - NOT admin - PowerShell is fine):

      .\tunnel-url.ps1                 # just print the current public URL
      .\tunnel-url.ps1 -UpdateVercel   # also re-point Vercel's VITE_API_URL + redeploy prod

  -UpdateVercel requires the Vercel CLI logged in and linked to the project
  (one-time: `npm i -g vercel; vercel login; cd frontend; vercel link`).
#>
param(
    [switch]$UpdateVercel
)

$ErrorActionPreference = "Stop"
$NS = "rec-engine"
$rx = 'https://[a-z0-9-]+\.trycloudflare\.com'

Write-Host "==> Waiting for the quick-tunnel URL in cloudflared logs (up to ~60s)..." -ForegroundColor Cyan

$url = $null
for ($i = 0; $i -lt 30; $i++) {
    # logs is captured for us; the banner appears ~5s after the pod is Running.
    $logs = kubectl -n $NS logs deploy/cloudflared --tail=200 2>$null
    if ($logs) {
        $m = [regex]::Match(($logs -join "`n"), $rx)
        if ($m.Success) { $url = $m.Value; break }
    }
    Start-Sleep -Seconds 2
}

if (-not $url) {
    throw "No trycloudflare.com URL found in cloudflared logs. Is the pod Running? `nCheck:  kubectl -n $NS logs deploy/cloudflared"
}

Write-Host "`n  Public tunnel URL:  $url" -ForegroundColor Green
Write-Host "  Sanity check:       Invoke-RestMethod $url/ready`n" -ForegroundColor DarkGray

if (-not $UpdateVercel) {
    Write-Host "  (run again with -UpdateVercel to push this to Vercel and redeploy)" -ForegroundColor DarkGray
    return
}

# -- Push to Vercel ----------------------------------------------------------
# VITE_ vars are baked at BUILD time, so changing the env requires a fresh prod build.
$frontend = Join-Path $PSScriptRoot "frontend"
Push-Location $frontend
try {
    Write-Host "==> Updating VITE_API_URL on Vercel (production)" -ForegroundColor Cyan
    # rm is idempotent-ish: ignore "not found" on the first run.
    try { vercel env rm VITE_API_URL production --yes 2>$null } catch {}
    # `vercel env add` reads the value from stdin.
    $url | vercel env add VITE_API_URL production
    Write-Host "==> Redeploying production (~60-90s)" -ForegroundColor Cyan
    vercel --prod
    Write-Host "`n  Done. Verify the app calls $url in the browser Network tab." -ForegroundColor Green
}
finally {
    Pop-Location
}
