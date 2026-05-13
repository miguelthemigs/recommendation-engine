# tests/load — Cycle 5 load testing

End-to-end load tests for the async cold-start pipeline.

## What this folder contains

| File | Purpose |
|---|---|
| `coldstart.js` | k6 main scaling test — ramped 10/50/100 VUs, submits + polls until completed |
| `ratelimit.js` | k6 rate-limit verification — 8 submits as a regular user, expects 5×200 then 3×429 |
| `queue_monitor.py` | Polls RabbitMQ `/api/queues` every 1 s → CSV |
| `run_load_test.ps1` | One-shot orchestrator: kills workers, starts N, runs k6, tears down |
| `results/` | Output artifacts (gitignored except sample) |

## Prerequisites

1. **Install k6** on Windows
   ```powershell
   winget install k6 --source winget
   # or: choco install k6
   ```

2. **Promote a test account to admin** (bypasses the 5/hour rate limit)
   ```powershell
   python scripts/set_admin_role.py loadtest-admin@example.com
   ```

3. **Create a regular test account** (no admin role) for the rate-limit test.

4. **Add to `.env`** (already gitignored):
   ```
   ADMIN_EMAIL=loadtest-admin@example.com
   ADMIN_PASSWORD=<password>
   USER_EMAIL=loadtest-user@example.com
   USER_PASSWORD=<password>
   ```

5. **Run RabbitMQ** locally with management plugin (default `localhost:5672` AMQP, `localhost:15672` management).

6. **Run the API** with mock disabled (or in a fresh shell where `MOCK_OPENAI` is not set):
   ```powershell
   uvicorn main:app --reload
   ```
   The API itself doesn't call OpenAI — only the worker does. The mock flag only needs to be set on the worker processes (the orchestrator handles that).

## Running the tests

### 1-worker scaling run
```powershell
./tests/load/run_load_test.ps1 -Workers 1
```
≈ 8 minutes. Results land in `tests/load/results/1worker/`.

### 2-worker and 3-worker runs
```powershell
./tests/load/run_load_test.ps1 -Workers 2
./tests/load/run_load_test.ps1 -Workers 3
```
Wait at least 60 s between runs for the queue to fully settle.

### Rate-limit verification (separate)
The rate-limit test does NOT use the orchestrator (no workers needed — every 6th submit returns 429 before the worker sees it).

```powershell
# Start one mock worker so the first 5 jobs can actually complete:
$env:MOCK_OPENAI="true"; python worker.py
# In a second shell:
k6 run `
  --out csv=tests/load/results/ratelimit/k6_raw.csv `
  -e API_BASE=http://localhost:8000 `
  -e SUPABASE_URL=$env:SUPABASE_URL `
  -e SUPABASE_ANON_KEY=$env:SUPABASE_ANON_KEY `
  -e USER_EMAIL=$env:USER_EMAIL `
  -e USER_PASSWORD=$env:USER_PASSWORD `
  tests/load/ratelimit.js
```

> **Important:** the regular test user must have < 5 non-failed jobs in the last hour. The setup() phase asserts this and fails fast.

## What gets measured

| Metric | Source | Meaning |
|---|---|---|
| `coldstart_submit_ms` | k6 Trend | Time for the POST to return — the architectural promise (target p95 < 500 ms) |
| `coldstart_e2e_ms` | k6 Trend | submit + queue + worker + poll — true user-perceived latency |
| `coldstart_completed` / `_failed` / `_timeout` | k6 Counter | Job outcome counts |
| `poll_success_rate` | k6 Rate | Fraction of `/jobs/{id}` polls that returned 200 |
| `messages_ready` | queue_monitor | RabbitMQ queue depth — visible saturation |
| `consumers` | queue_monitor | Active worker count seen by the broker |

## Cleanup

The orchestrator handles teardown automatically. If anything is left running:
```powershell
Get-Process python | Where-Object { $_.CommandLine -like '*worker.py*' } | Stop-Process -Force
Get-Job | Stop-Job; Get-Job | Remove-Job -Force
```

## Safety note

`MOCK_OPENAI=true` short-circuits the OpenAI call in `core/coldstart.py`. The worker logs a banner on startup whenever this flag is active so it can't silently ship.
