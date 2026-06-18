# Flavour 4 — Cycle 5: Public Deployment (Vercel + Cloudflare Tunnel)

*Recommendation Engine · Deployment & DevOps · Semester 6 · 2026*
*Learning Outcomes: LO1 (Engineering Approach), LO3 (Software Maintenance), LO4 (Professional Standard), LO5 (Personal Leadership)*

---

## 1. Where this cycle fits

Cycle 2 packaged the backend into one container image. Cycle 3 built the pipeline that
lints, tests, and publishes that image. Cycle 4 ran the whole backend on Kubernetes
(minikube) — but only reachable from my own machine, through a local `port-forward`
bridge.

This cycle removes "from my own machine". The deliverable is the app **live on the public
internet over HTTPS**: the React frontend hosted on **Vercel**, the minikube backend
exposed through a **Cloudflare Tunnel**, and the full flow — register → log in → build a
watchlist → get cold-start recommendations — working end to end on a URL anyone can open.

The honest summary up front: the architecture decisions were small, but **the integration
was where the real work was**. Three separate systems (Vercel, Cloudflare, minikube) plus
Supabase all had to agree on URLs, framework detection, build steps, and CORS — and each
disagreed at least once. The debugging is the learning, so it's all in §7.

---

## 2. What "going public" actually requires (in plain terms)

Locally, the frontend and backend were both on `localhost`, so nothing had to be told
where anything was. Public deployment breaks every one of those assumptions, and each
break is a thing I had to configure:

- **The frontend needs a host.** Vercel serves the static React build. But Vercel can
  *only* host the static site — it cannot run my stateful backend (long-lived API,
  background worker, RabbitMQ broker). So the frontend and backend live in different
  places and must be wired together.
- **The backend needs a public address.** minikube runs on my laptop behind a home
  router — there's no public IP to point a browser at. A **Cloudflare Tunnel** solves this
  by making an *outbound* connection from inside the cluster to Cloudflare's edge, which
  then hands out a public HTTPS URL that forwards back down the tunnel. No port-forwarding
  on the router, no admin firewall changes.
- **The frontend must know the backend's URL at build time.** Vite bakes
  `VITE_*` variables into the JavaScript bundle when it builds — they are *not* read at
  runtime. So the backend URL has to be set on Vercel and the site **rebuilt** for a
  change to take effect.
- **The backend must trust the frontend's origin (CORS).** A browser on the Vercel domain
  calling the tunnel domain is a cross-origin request; the API has to explicitly allow
  that origin or the browser blocks every call.
- **Auth has to know the public URL.** Supabase sends confirmation emails and redirects
  after login; pointed at `localhost`, a public sign-up would dead-end.

So the cycle is really five small integrations, not one big feature.

---

## 3. The decisions I made before writing anything

As in every cycle, I settled the real choices first and wrote down why.

1. **Quick tunnel, not a named tunnel.** A Cloudflare *named* tunnel gives a stable URL
   but needs a Cloudflare account and a domain I own. I own neither, so I chose a
   **TryCloudflare quick tunnel**: completely free, anonymous, zero account. The tradeoff
   is real and I accepted it consciously — **the public URL changes every time the tunnel
   restarts**. I mitigated that with a script, not by pretending it's stable (see §5).

2. **Run cloudflared *inside* the cluster, not on the host.** I deployed cloudflared as a
   normal Kubernetes Deployment pointing at the nginx ingress, rather than running it as a
   process on my laptop. This keeps the PDP's "expose the *ingress*" shape, and because
   the tunnel only makes outbound connections, the public path needs no admin shell and no
   `minikube tunnel` — it works even though my home network is unroutable from outside.

3. **CORS by regex, not a hardcoded list.** This started as "append the Vercel domain to
   `ALLOWED_ORIGINS`" and changed once I saw the real domains. Vercel (hobby tier) gives no
   clean `recommendation-engine.vercel.app` alias — it mints long, **rotating** subdomains
   (`...-git-main-...`, `...-<hash>-...`) per branch and per deploy. Enumerating them is a
   losing game. So I added an optional `ALLOWED_ORIGIN_REGEX` that matches the whole
   project family (`https://recommendation-engine[a-z0-9-]*\.vercel\.app`) in addition to
   the exact local-dev origins. One config value, survives every redeploy. I verified it
   matches both real domains and *rejects* spoofs like `...vercel.app.evil.com`.

4. **Env-driven config stays env-driven.** No URL is baked into code. The frontend reads
   `VITE_API_URL`; the backend reads `ALLOWED_ORIGINS` / `ALLOWED_ORIGIN_REGEX`. The only
   thing that changes per session is one Vercel environment variable.

5. **Split the work by who owns the surface.** Anything in the repo or a CLI — me.
   Anything behind a browser dashboard (Vercel project settings, Supabase auth config) —
   done by hand with explicit steps, because those aren't in version control.

---

## 4. What I built

| File | What it does | Why |
|---|---|---|
| `frontend/vercel.json` | SPA rewrites — every path serves `index.html` | Without it, hard-refreshing a React Router deep link (`/watchlist`) 404s on Vercel |
| `k8s/cloudflared.yaml` | cloudflared Deployment → the nginx ingress | The public tunnel, in-cluster, outbound-only, `replicas: 1` (each replica would mint its own URL) |
| `tunnel-url.ps1` | Reads the current tunnel URL from the pod logs; `-UpdateVercel` pushes it to Vercel | Automates the per-session "rotating URL" step |
| `up.ps1` (extended) | Applies cloudflared with the other workloads, prints the public URL, Docker preflight | One command brings the whole public stack up |
| `config.py` / `main.py` | `ALLOWED_ORIGIN_REGEX` → CORS middleware | The regex CORS decision from §3 |
| `k8s/configmap.yaml` | Sets the regex value | Non-secret config, where it belongs |

Two code changes only, both config-shaped (a CORS regex and an unused-variable fix); the
rest is infrastructure and scripting. That "only change how it ships, not what it does"
boundary held again.

---

## 5. The rotating-URL problem (and the per-session dance)

The quick-tunnel tradeoff needed a concrete answer, not a shrug. Every cluster (re)start
mints a fresh `https://<random-words>.trycloudflare.com`. Three things depend on that URL,
and I sorted them by how often they change:

- **CORS** — keyed to the *Vercel* origin (the regex), which is stable. **Set once.**
- **Supabase auth URLs** — keyed to the Vercel origin too. **Set once.**
- **`VITE_API_URL` on Vercel** — the *only* thing tied to the tunnel URL. **Changes every
  session.**

So the per-session cost is a single environment variable plus a rebuild. `tunnel-url.ps1`
reads the new URL out of the cloudflared logs and (with `-UpdateVercel`) pushes it. The
friction is "one script + a ~90s Vercel rebuild", which is honest and acceptable for a
free, account-less tunnel.

---

## 6. Step by step — what I actually did

1. **Wrote the repo changes** (§4) and committed them; pushed so Vercel could build from
   git.
2. **Brought the backend up** with `up.ps1` — now including the cloudflared pod — and
   confirmed it printed a public `*.trycloudflare.com` URL.
3. **Imported the project on Vercel**, set Root Directory to `frontend`, and added the
   three `VITE_*` environment variables.
4. **Wired CORS** via the regex and re-applied the ConfigMap.
5. **Configured Supabase** auth Site URL + redirect URLs to the Vercel domain.
6. **Fought the integration** until the build was green and the flow worked (§7).
7. **Verified end to end** on the public URL: `/ready` 200 through the tunnel, a CORS
   preflight that echoes the allow-origin header, and a real browser run of
   register → login → watchlist → cold-start with zero CORS errors and every call going to
   the tunnel host over HTTPS.

---

## 7. Honest problems I ran into (and fixed)

This is the meat of the cycle. Every one of these cost time, and every fix taught me
something about how these systems actually behave.

- **Vercel auto-detected my backend as the project.** The first deploy pointed at the repo
  root (`./`), where Vercel saw `main.py` + `pyproject.toml` and decided the project was
  **FastAPI** — trying to build my Python backend instead of the React frontend. **Fix:**
  set the project's **Root Directory to `frontend`**, so Vercel only ever looks at the
  frontend folder. *Lesson: in a mixed repo, Vercel's zero-config detection keys off
  whatever is at the directory it's pointed at — point it precisely.*

- **The Vercel CLI re-flipped the framework to FastAPI.** I scripted the per-session
  redeploy with `vercel --prod`. It set the environment variable fine, but the deploy
  itself uploaded from the git root, re-ran framework detection, found `pyproject.toml`,
  and **persisted "FastAPI" back onto the project** — undoing my Root Directory fix.
  **Fix:** deploy through the **git integration** (push to `main`) or a dashboard redeploy,
  which respect the Root Directory; don't use `vercel --prod` from a mixed repo. *Lesson:
  CLI deploys and git deploys are not equivalent — the CLI can mutate project settings as a
  side effect.*

- **The production build failed on a dead variable.** `npm run build` is
  `tsc && vite build`. An unused `const allGenres` in `StatsPage.tsx` tripped TypeScript's
  `noUnusedLocals` (`TS6133`) and failed the build — on **every** Vercel deploy. It never
  showed locally because `vite dev` skips `tsc`. **Fix:** delete the dead line; build goes
  green. *Lesson: dev mode and the production build are different gates — a clean
  `npm run build` locally is the real check, not "it runs in dev".*

- **PowerShell 5.1 choked on my scripts.** `up.ps1` failed to parse with "Unexpected
  token" errors. The cause was non-ASCII characters (em-dashes, arrows, box-drawing) in
  the file: Windows PowerShell 5.1 reads a `.ps1` with no byte-order mark as the legacy
  ANSI codepage, which mangles UTF-8 multibyte characters and corrupts the string literals
  around them. **Fix:** rewrite both scripts in **pure ASCII**. *Lesson: scripts that must
  run on stock Windows PowerShell should stay ASCII unless explicitly saved UTF-8-with-BOM.*

- **The Docker preflight tripped on its own warning.** I added a `docker info` check so the
  script fails fast when Docker Desktop is down. But Docker prints a harmless seccomp
  warning to *stderr*, and under `$ErrorActionPreference = "Stop"` PowerShell 5.1 turns a
  *redirected* native-command stderr line into a terminating error — so the check killed
  the script even though Docker was fine. **Fix:** judge Docker purely by exit code, with
  `ErrorActionPreference` dropped to `Continue` just for that probe. A sibling case:
  `minikube docker-env --unset` emits a `Remove-Item Env:\SSH_AUTH_SOCK` for a variable
  that doesn't exist on my machine, which also threw under `Stop` — softened the same way.
  *Lesson: PowerShell's native-command stderr handling is a real trap; check exit codes,
  don't redirect-and-pray.*

- **Supabase was paused.** Free-tier Supabase projects sleep after inactivity; while
  paused, the backend can't load data or verify logins. **Fix:** resume it in the
  dashboard before bringing the stack up. *Lesson: "free tier" has operational behaviour
  (sleeping, rotating URLs) that becomes part of your runbook.*

None of these were the *architecture* being wrong — they were the seams between tools.
That's exactly what "deployment" is.

---

## 8. Setup & run guide

### One-time setup
- Cycle 4's prerequisites (Docker Desktop, minikube, kubectl, a repo-root `.env`).
- A **Vercel project** importing this repo, with **Root Directory = `frontend`**,
  **Framework Preset = Vite**, and three Production env vars: `VITE_API_URL` (set per
  session), `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
- **Supabase → Authentication → URL Configuration**: Site URL and an Additional Redirect
  URL (`/**`) pointing at the Vercel domain; keep `http://localhost:5173/**` for local dev.
- (Optional) **Vercel CLI** logged in + linked, for scripted env updates.

### Every session (the rotating-URL dance)
1. **Admin PowerShell**, repo root:
   ```powershell
   .\up.ps1
   ```
   It brings the cluster up (incl. the cloudflared tunnel) and prints
   `PUBLIC URL: https://<...>.trycloudflare.com`.
2. Put that URL into Vercel as `VITE_API_URL` and **redeploy** the production deployment
   (dashboard redeploy, or a git push). The URL is baked at build time, so a rebuild is
   required.
3. Verify:
   ```powershell
   Invoke-RestMethod https://<...>.trycloudflare.com/ready   # -> ready : True
   ```
4. Open the Vercel URL and use the app.

> CORS and Supabase auth are **not** touched per session — they're keyed to the stable
> Vercel origin. Full runbook and troubleshooting in `k8s/README.md`.

---

## 9. What I learned

- **Deployment is integration, not features.** The hard part wasn't any single component —
  it was getting four independently-opinionated systems (Vercel, Cloudflare, Kubernetes,
  Supabase) to agree on URLs, build steps, and trust. Most of my time went into the seams.
- **"Free" is a set of constraints you design around.** No owned domain → rotating tunnel
  URL → a per-session script. No clean Vercel alias → CORS by regex. Free Supabase →
  it sleeps. Each free-tier limit pushed a concrete engineering decision.
- **Build-time vs runtime config is a real distinction.** `VITE_*` baking at build time is
  why changing the backend URL means a *rebuild*, not a restart. Understanding when config
  is read changed how I designed the per-session flow.
- **Dev and prod gates differ — trust the prod build.** A bug invisible in `vite dev`
  (skips type-checking) broke every production build. The lesson generalises: verify
  against the same command the deploy runs.
- **Tooling friction deserves the same rigour as code.** The PowerShell encoding and
  stderr traps weren't "just scripts" — a broken bring-up script blocks everything. Making
  it ASCII-safe and exit-code-driven is part of making the system maintainable.

---

## 10. What's next

- **Cycle 6 (optional) — Autoscaling.** Scale the worker pool automatically on RabbitMQ
  queue depth (KEDA/HPA), closing the loop on the manual worker-count scaling measured back
  in Flavour 3, Cycle 5.
- **A stable URL.** The single biggest quality-of-life upgrade would be owning a domain and
  switching to a Cloudflare *named* tunnel — that removes the per-session `VITE_API_URL`
  step entirely. Out of scope here (no domain), but the obvious next step if this became
  more than a demo.
- **Fix the scripted Vercel deploy.** Make `-UpdateVercel` deploy via the git integration
  (or `vercel redeploy` of the last git deployment) so it stops re-flipping the framework
  preset — then the per-session dance really is one command.

---

## 11. How this maps to the Learning Outcomes

- **LO1 — Engineering Approach.** I settled the real decisions before building (quick vs
  named tunnel, cloudflared in-cluster vs on host, CORS by regex vs an unmaintainable
  list, env-driven config) and wrote down the tradeoff behind each. When the integration
  fought back, I diagnosed every failure to its root cause — Vercel's directory-based
  framework detection, the CLI mutating project settings, a dev-vs-prod build-gate gap, a
  PowerShell encoding/stderr quirk — rather than guessing, and I verified the CORS regex
  against both real and adversarial inputs.
- **LO3 — Software Maintenance.** The result is reproducible and self-documenting: one
  idempotent bring-up script (now Docker-preflighted and ASCII-safe), a helper that
  automates the only per-session step, env-driven config with no hardcoded hosts, a CORS
  rule that survives Vercel's rotating domains without edits, and a written runbook for the
  rotating-URL workflow. The only code changes were a CORS regex and a one-line build fix.
- **LO4 — Professional Standard.** The app is genuinely public over HTTPS with sane
  security hygiene: secrets stay in a Kubernetes Secret built from a gitignored `.env` and
  are never committed; the tunnel is outbound-only (no inbound ports opened on my network);
  CORS is locked to my project's origins and rejects look-alikes; auth redirect URLs are
  pinned to the real domain. The deliverable is verified end to end, not assumed.
- **LO5 — Personal Leadership.** This cycle was a long chain of cross-system failures with
  no single owner to escalate to. I kept it organised — splitting repo/CLI work from
  dashboard work, fixing one seam at a time, and not conflating two problems at once
  (e.g. confirming the build was green before touching the deploy mechanism) — and saw it
  through to a working public deployment instead of stopping at "it builds locally".
