# Flavour 4 — Cycle 5 Plan: Public Deployment (Vercel + TryCloudflare quick tunnel)

> **Status: PLAN — not executed yet.** This is the agreed implementation plan. Delete or fold into
> `FLAVOUR4_CYCLE5.md` once the cycle is done.

## Context

Flavour 4 Cycles 2–4 are done: containerized, CI green on GHCR, backend healthy in minikube.
Cycle 5 makes it **public**: SPA on Vercel, minikube ingress exposed through a Cloudflare tunnel,
full flow verified on a public HTTPS URL.

**Decided constraints:**
- No domain is owned → use a **TryCloudflare quick tunnel**: 100% free, no Cloudflare account
  needed, but the public URL **rotates on every cloudflared restart**. Mitigation = a per-session
  script, not code.
- cloudflared runs **in-cluster** as a k8s Deployment pointing at the nginx ingress (keeps
  "expose the ingress" from the PDP; no `minikube tunnel`/admin shell needed for public access,
  since cloudflared only makes *outbound* connections).
- CORS is keyed to the **stable** Vercel origin, so it's a one-time configmap change — only
  `VITE_API_URL` rotates per session.
- Execution split: Claude does all repo changes + CLI; Miguel does browser dashboards
  (Vercel import, Supabase auth settings) with click-by-click instructions.

## Ordering (dependencies)

1. Repo changes → commit/push (Vercel deploys from GitHub)
2. Apply cloudflared → **tunnel URL exists**
3. **User: Vercel import** (uses the real tunnel URL) → Vercel domain fixed
4. configmap `ALLOWED_ORIGINS` + api rollout restart (needs the Vercel domain)
5. **User: Supabase auth URL config** (needs the Vercel domain)
6. End-to-end smoke test
7. Vercel CLI link + dry-run of the per-session script
8. Docs (`FLAVOUR4_CYCLE5.md`, `CLAUDE.md`, `k8s/README.md`), final commit

## Step 1 — Repo changes (Claude)

**`frontend/vercel.json`** (new) — React Router deep links 404 on Vercel without it:
```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```
(Root Directory will be `frontend`, so Vercel reads `vercel.json` from there. Real asset files
are served before rewrites apply, so this only catches client routes.)

**`k8s/cloudflared.yaml`** (new) — Deployment, namespace `rec-engine`, `replicas: 1`
(each replica would mint its own quick-tunnel URL), image
`cloudflare/cloudflared:<pin latest stable at execution>`, args:
```
tunnel --no-autoupdate
  --url http://ingress-nginx-controller.ingress-nginx.svc.cluster.local:80
  --http-host-header rec-engine.local
  --metrics 0.0.0.0:2000
```
No Secret — quick tunnels are anonymous. readinessProbe on `:2000/ready`; small resource
requests/limits. Note: `:2000/quicktunnel` returns the assigned hostname as JSON — an
alternative to log-grepping.

**`tunnel-url.ps1`** (new, repo root) — extracts `https://<x>.trycloudflare.com` from
`kubectl -n rec-engine logs deploy/cloudflared` (poll up to ~60s; the URL banner appears ~5s
after start). Default: print the URL. `-UpdateVercel` switch: `vercel env rm/add VITE_API_URL
production` + `vercel --prod` from `frontend/`.

**`up.ps1`** — apply `k8s/cloudflared.yaml` with the other workloads; after pods are ready,
print the tunnel URL prominently + a reminder to run `tunnel-url.ps1 -UpdateVercel`. The final
port-forward stays (local-only access), with a comment that it is **not** needed for the
public path.

Commit + push (must happen before the Vercel import).

## Step 2 — Get the tunnel URL (Claude)

`kubectl apply -f k8s/cloudflared.yaml` → extract URL from logs → sanity check
`Invoke-RestMethod <tunnel>/ready`.

## Step 3 — Vercel import (USER — click-by-click)

1. vercel.com → **Add New… → Project** → import `miguelthemigs/recommendation-engine`
   (if not listed: **Adjust GitHub App Permissions** and grant access to the repo).
2. Project name: `rec-engine` (this fixes the production domain `rec-engine.vercel.app` — note it,
   CORS and Supabase need it).
3. **Root Directory → Edit → `frontend`**. Framework preset should auto-detect **Vite**;
   keep default Build Command (`npm run build`) / Output Directory (`dist`) / Install (`npm install`).
4. Environment Variables (Production):
   - `VITE_API_URL` = tunnel URL from Step 2 (no trailing slash)
   - `VITE_SUPABASE_URL` = value from local `frontend/.env`
   - `VITE_SUPABASE_ANON_KEY` = value from local `frontend/.env`
5. **Deploy** (~1 min) → note the production URL `https://<project>.vercel.app`.

## Step 4 — CORS (Claude)

`k8s/configmap.yaml`: append `https://<project>.vercel.app` to `ALLOWED_ORIGINS`; update the
stale "Cycle 5 adds…" comment. Then `kubectl apply -f k8s/configmap.yaml` +
`kubectl -n rec-engine rollout restart deployment/api` (api re-gates ~60s on the `/ready`
startupProbe). One-time — the Vercel production origin is stable.

## Step 5 — Supabase auth config (USER)

Supabase Dashboard → project → **Authentication → URL Configuration**:
- **Site URL** → `https://<project>.vercel.app` (signUp passes no `emailRedirectTo`, so
  confirmation emails link to the Site URL — pointing at localhost would strand public sign-ups)
- **Additional Redirect URLs** → add `https://<project>.vercel.app/**`, keep
  `http://localhost:5173/**` for local dev
- Check **Authentication → Sign In / Providers → Email** → whether "Confirm email" is enabled
  (determines an inbox step in the smoke test; disabling it for demo friction is an option, not a default).

## Step 6 — Vercel CLI one-time setup (recommended)

`npm i -g vercel` → `vercel login` (browser confirm) → `vercel link` in `frontend/`
(select the existing project). Makes the per-session env update one command.

Dashboard fallback: Project → Settings → Environment Variables → edit `VITE_API_URL` → Save →
Deployments → "⋯" on latest production deploy → **Redeploy** (uncheck "Use existing Build Cache").

## Step 7 — End-to-end smoke test

CLI (Claude):
- `<tunnel>/health` + `/ready` → 200
- CORS preflight: `OPTIONS <tunnel>/watchlist` with `Origin: https://<project>.vercel.app` +
  `Access-Control-Request-Method: GET` → response must echo `access-control-allow-origin`
- `kubectl -n rec-engine logs -l app=worker -f` during the browser test — real OpenAI,
  **no mock banner**

Browser (user, on the Vercel URL):
1. Hard-refresh a deep link (e.g. `/watchlist`) → no 404 (proves the rewrites)
2. Register (+ email confirm if enabled — the link must land on the Vercel domain, proving the
   Supabase Site URL) → login
3. Watchlist add + recommendations (proves JWT through tunnel + ingress + CORS on auth routes)
4. Cold-start submit → completes (Realtime is browser↔Supabase and bypasses the tunnel; the
   polling fallback only kicks in after 30s — either completion path is acceptable, note which)
5. DevTools Network tab: zero CORS errors, all API calls https → the trycloudflare host
   (both ends https, so no mixed content possible)

## Step 8 — Docs + wrap-up (Claude)

- `FLAVOUR4_CYCLE5.md` — follow the Cycle 4 report template; **LO1 first**, then LO3/LO4/LO5
  (per the PDP table). Cover: decisions (quick vs named tunnel, in-cluster vs host cloudflared,
  ingress-in-path), what was built, verification evidence, limitations (no SLA, rotating URL,
  preview deploys fail CORS), reflection.
- `k8s/README.md` — new "Public access (Cycle 5)" section + per-session runbook + troubleshooting
  (no URL in logs; nginx 404 = host-header problem; Cloudflare error 1033 = origin unreachable).
- `CLAUDE.md` — Cycle 5 → Complete; also flip Cycle 3 to Complete (CI has been green on main
  since 2026-06-09); refresh the stale "mostly not built yet" deployment header.
- Final commit + push.

## Per-session runbook (the rotating-URL dance)

1. Admin PowerShell: `.\up.ps1` (deploys cloudflared, prints the fresh URL — any pod restart,
   including `minikube stop`/`start`, mints a new one)
2. `.\tunnel-url.ps1 -UpdateVercel` (~60–90s Vercel rebuild)
3. `Invoke-RestMethod https://<x>.trycloudflare.com/ready` → `{"ready": true}`

Target friction: one admin script + one normal-shell script + ~2 min wait.

## Known risks (verify at execution time)

- **TryCloudflare is best-effort**: no SLA, undocumented rate limits, occasionally blocked on
  school/corporate networks. If the tunnel won't establish, pin `--protocol http2`
  (QUIC/UDP 7844 may be filtered).
- Pin the current `cloudflare/cloudflared` image tag; confirm `--http-host-header` and the
  `/quicktunnel` metrics endpoint on that version.
- Vercel Vite preset auto-detection with a subdirectory Root Directory; exact `vercel env add`
  non-interactive syntax in the current CLI version.
- Vercel **preview** deployments (`*-git-*.vercel.app`) are NOT in `ALLOWED_ORIGINS` → previews
  fail CORS. Accepted limitation (demo uses production only); a future fix is
  `allow_origin_regex` in `main.py`.
- `cloudflare/cloudflared` image pulls from Docker Hub on first apply — cached in minikube
  afterwards, wiped by `minikube delete`.
- Cold-start rate limit (5/hr/user) applies to demo accounts — don't burn it rehearsing.
