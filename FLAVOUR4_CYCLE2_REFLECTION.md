# Flavour 4 · Cycle 2 — Containerisation: Process & Reflection

> A process-focused write-up: how the work was approached, what I learned, and where it
> landed. The *what-was-built* checklist lives in `FLAVOUR4_CYCLES.md`; this document is
> about the **journey**, not the artifact list.

---

## 1. The starting point

The recommendation engine worked but had never left the laptop. Three processes
(FastAPI API, RabbitMQ worker, RabbitMQ broker) were started by hand in three terminals,
and two values were hardcoded to localhost: the frontend's API URL and the backend's CORS
allowlist. The goal of this cycle was narrow and deliberate: **change the packaging, not
the application.** Make the whole backend come up with one command, and turn the two
hardcoded values into injected configuration.

## 2. How I approached it

I worked in the order a deployment engineer actually reasons, not the order the files
happen to sit in:

1. **Understand the runtime before writing any Dockerfile.** Before a single line of
   config, I traced *how each process starts* and *what it needs*: the API runs via
   `uvicorn main:app` (no `__main__`, so it needs an explicit host/port), the worker runs
   via `python worker.py` (has `__main__`), and crucially **both run the same heavy
   bootstrap** — `store.load` + `graph.build` + `tfidf.build`. That single observation
   decided the whole image strategy.

2. **One image, run two ways.** Because the API and worker share that expensive bootstrap
   and the same dependency set, building two separate images would duplicate everything
   and invite drift. So I built **one** image with a sensible default command (the API)
   and let `docker-compose` *override* the command to `python worker.py` for the worker.
   This matched the Cycle 1 research conclusion and is the same shape Kubernetes will use
   in Cycle 4 (two Deployments, one image).

3. **Layer caching as a first-class design choice.** The Dockerfile copies
   `requirements.lock` and installs *before* copying the source. That means editing a
   `.py` file doesn't re-trigger a multi-minute reinstall of scikit-learn and numpy —
   only a dependency change does. Small ordering decision, large day-to-day payoff.

4. **Pin for reproducibility.** I captured the resolved dependency versions into
   `requirements.lock` so "same input → same image" actually holds. `requirements.txt`
   stays the human-readable list of *what* we depend on; the lock is *exactly what gets
   installed*.

5. **Fix the two blockers as proper config, in the right place.** Per the project's own
   rule that constants live in `config.py`, I added `ALLOWED_ORIGINS` there (parsed from a
   comma-separated env var, defaulting to the dev origins) and had `main.py` consume it.
   The frontend's `BASE_URL` now reads `import.meta.env.VITE_API_URL` with a localhost
   fallback. I also added tracked `.env.example` templates for both backend and frontend
   so the *contract* is documented while the real secrets stay gitignored.

6. **One command, ordered correctly.** `docker compose up --build` builds the image once
   and starts broker → api → worker. The api and worker are gated on the broker's
   **healthcheck** (`rabbitmq-diagnostics ping`), so they don't race a broker that isn't
   ready yet. The broker hostname is resolved by compose's service name, which is why the
   `RABBITMQ_URL` localhost default is *overridden* inside the compose network.

## 3. The part that taught me the most: debugging the failed boot

The build succeeded and all three containers started — then the API exited during startup.
This is where the real learning happened, because the *first* explanation I reached for was
wrong, and the discipline of verifying it is the actual lesson.

- **The error** was `httpx.ConnectError: Name or service not known` while the app loaded
  data from Supabase.
- **My first hypothesis** was the classic Windows one: the `.env` file has CRLF line
  endings, so a trailing `\r` corrupts the Supabase hostname. I checked — the file *did*
  have CRLF. Tempting to "fix" it and move on.
- **But I tested the hypothesis instead of assuming it.** I printed the exact value the
  container receives (`repr()`), and the string was clean — Docker strips the `\r`. The
  CRLF was a red herring.
- **I narrowed it systematically.** From inside the container, `google.com` and
  `supabase.co` resolved fine, but the *project* subdomain `…supabase.co` returned
  NXDOMAIN. So it wasn't "Docker has no DNS."
- **I checked the layer below Docker.** The **host itself** couldn't resolve the project
  subdomain either (`nslookup` → "Non-existent domain"), and running the app *bare-metal*
  on the host failed with the identical `getaddrinfo failed`.

**The root cause was not containerisation at all.** The Supabase project referenced in
`.env` no longer exists (free-tier projects pause/are removed after inactivity), so its
hostname returns NXDOMAIN. The app is currently broken *with or without Docker* — my
containers just surfaced a pre-existing environment problem faithfully.

To prove the container plumbing itself was sound and not the suspect, I ran the image
against the **JSON fallback** path (Supabase disabled, `data/` mounted). It got further:
`store.load` and `graph.build` both ran *inside the container* — failing only at the
TF-IDF step because the local fallback JSON has no `overview` text. That's a second,
separate data-quality issue, again not a packaging fault.

## 4. What I learned

- **A system's shape, and its environment, decide more than the tooling does.** Just as
  Cycle 1 found that "stateful + always-on worker" rules out serverless before cost
  matters, Cycle 2 found that a dead external dependency breaks the app regardless of how
  cleanly it's packaged. Containers don't fix your environment — they reproduce it
  honestly.
- **Verify the hypothesis, don't fix the first plausible cause.** The CRLF theory was
  plausible, common, and *wrong here*. Two minutes of `repr()` saved me from "fixing"
  something that wasn't broken and still being stuck.
- **Debug top-down through the layers.** App error → env value → container DNS → host DNS →
  bare-metal. Each step *eliminated* a layer until only the real cause remained. That
  ladder is reusable for any "works on my machine" mystery.
- **One image / two commands** is a genuinely elegant pattern when processes share a
  bootstrap — and it pays forward directly into the Kubernetes cycle.
- **Build-order is a design decision.** Dependencies before source isn't a detail; it's
  the difference between a 4-second rebuild and a 4-minute one, every single edit.
- **Make the contract explicit.** `.env.example` files turn "you have to know which env
  vars exist" into a checked-in, reviewable contract — the same discipline that makes the
  k8s ConfigMap/Secret split in Cycle 4 straightforward.

## 5. Final result

**Containerisation is complete and verified end-to-end against the live database.**
After the Supabase project was unpaused, the whole stack came up clean from one command
(`docker compose up --build`). Concretely, observed running:

- `docker compose build` produces one shared `rec-engine:latest` image (deps install,
  non-root user, layer cache working).
- `docker compose up` brings the broker to **healthy**, then starts api and worker; the
  healthcheck-gated ordering works; container networking and DNS work.
- The shared image runs **both ways** (uvicorn for api, `python worker.py` for worker).
- **API live:** `GET /health` → `{"status":"ok","movies_loaded":491,"shows_loaded":494}`
  — `store.load` pulled the full dataset from Supabase **inside the container**.
- **Indexes built in-container:** `GET /graph/stats` → Jaccard (976 nodes, 9730 edges,
  ~2.3s) and TF-IDF (976 nodes, 9760 edges, ~0.3s), both `ready`.
- **Worker wired to the broker:** logs show it bootstrapped, connected via the compose
  service name (`host=rabbitmq port=5672`), and is `ready — waiting for jobs on
  'coldstart_jobs'`.
- Both hardcoded blockers are removed: CORS is driven by `ALLOWED_ORIGINS`, the frontend
  API URL by `VITE_API_URL`; `.env.example` templates are tracked.

**The one wrinkle along the way — and it was never a container defect.** Before the
database was unpaused, the project's Supabase hostname returned NXDOMAIN (gone), and the
app failed to boot *identically on bare metal* — the containers just surfaced a dead
external dependency honestly (see §3). Right after unpausing, the host briefly returned a
Cloudflare **521** (DNS resolves at the edge, but the Postgres origin takes a couple of
minutes to wake) — another environment-timing reality, not a packaging issue. Once the
origin was up (`/rest/v1/` → `401`, i.e. reachable), the stack booted on the first try.
The lesson held the whole way through: **containers reproduce your environment faithfully;
they don't paper over it.**

## 6. What's next

Cycle 3 — CI/CD: a GitHub Actions pipeline (lint → test → build → push to GHCR). The first
decision there is already flagged: there are currently no pytest unit tests, only k6 load
tests, so the "test" stage needs a deliberate choice (smoke test vs. add minimal pytest).
