# Cycle 2 Report — Supabase Migration

**Project:** Recommendation Engine (Movies & TV Shows)
**Stack:** FastAPI · Python 3.11 · React 18 · TypeScript · Supabase · Tailwind CSS
**Date:** April 2026

---

## 1. Goal

Migrate the recommendation engine from a stateless single-user demo to a multi-user system with persistent data, authentication, and per-user watchlists — while keeping the high-performance in-memory graph engine untouched.

| Before (Cycle 1) | After (Cycle 2) |
|---|---|
| Data loaded from JSON files on disk | Data loaded from Supabase Postgres at startup |
| No user accounts | Email + password auth via Supabase Auth |
| Watchlists in browser localStorage only | Watchlists persisted per user in Postgres |
| No access control | Row Level Security (RLS) per user |
| Cold start results lost after response | Cold start jobs audited in a database table |

---

## 2. Architecture Overview

### 2.1 System Diagram (Post-Migration)

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite)                   │
│                                                         │
│  supabase-js ──► Supabase Auth (signup/login/JWT)       │
│  apiFetch()  ──► FastAPI (attaches JWT automatically)   │
└────────────────────────┬────────────────────────────────┘
                         │ Authorization: Bearer <JWT>
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                      │
│                                                         │
│  api/auth.py     ← JWT validation (local, no network)  │
│  api/routes.py   ← Watchlist CRUD + rec endpoints      │
│  core/store.py   ← In-memory store (loaded at startup) │
│  core/graph.py   ← Jaccard similarity graph (in RAM)   │
│  core/tfidf.py   ← TF-IDF cosine index (in RAM)       │
│  core/coldstart.py ← LLM taste extraction + BFS        │
└────────────────────────┬────────────────────────────────┘
                         │ startup: SELECT * FROM movies/shows
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Supabase (Postgres + Auth + RLS)                       │
│                                                         │
│  movies / shows   ← ~1,000 items, public read          │
│  genres           ← TMDB genre maps, public read       │
│  watchlists       ← per-user, RLS enforced             │
│  cold_start_jobs  ← audit trail, RLS enforced          │
│  auth.users       ← managed by Supabase Auth           │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Key Design Decision: Hybrid In-Memory + Postgres

The recommendation algorithms (Jaccard similarity, BFS, PageRank, TF-IDF) require O(1) neighbor lookups and operate on the full dataset. Moving these to SQL queries would introduce unacceptable latency. The solution: **load the dataset into RAM at startup from Supabase, then serve all recommendations from memory**. Postgres is the source of truth, but runtime performance is identical to the JSON-based system.

---

## 3. Database Schema Design

### 3.1 Tables

Five tables were designed, with clear separation between public catalog data and private user data:

**movies / shows** — Separate tables mirroring the existing in-memory dict structure. Each stores TMDB metadata with Postgres array columns for genres, keywords, and cast. Primary key is `tmdb_id` (integer).

**watchlists** — Stores only `(user_id, tmdb_id, media_type)` tuples, not full item data. This avoids denormalization — the backend resolves full items from the in-memory store. The `media_type` enum (`movie | show`) is critical because TMDB IDs are not globally unique across movies and shows.

**cold_start_jobs** — Stores the full lifecycle of a cold start recommendation request: input answers (JSONB), extracted taste signals, seed IDs, final recommendations, token costs, and timing. Status progresses through `pending → running → completed | failed`. This table is designed to support future async processing (Cycle 3).

### 3.2 Row Level Security

| Table | Policy |
|---|---|
| movies, shows, genres | `SELECT` open to all (public catalog) |
| watchlists | `SELECT / INSERT / DELETE` only where `auth.uid() = user_id` |
| cold_start_jobs | `SELECT / INSERT` only where `auth.uid() = user_id` |

RLS ensures that even if a bug in the application code omits a `WHERE user_id = ...` filter, the database layer prevents cross-user data access.

---

## 4. Authentication Flow

### 4.1 How It Works End-to-End

1. **Frontend** — User submits email + password on the Login page
2. **Supabase Auth** — Validates credentials, returns a JWT (HS256) containing the user's UUID in the `sub` claim
3. **Frontend** — `AuthContext` stores the session; `apiFetch()` automatically attaches `Authorization: Bearer <token>` to every API call
4. **Backend** — `api/auth.py` extracts the token, verifies the HS256 signature using `SUPABASE_JWT_SECRET`, and returns the decoded payload. No network call to Supabase — validation is purely local and fast.
5. **Routes** — FastAPI dependency injection: `user = Depends(get_current_user)` extracts `user["sub"]` (UUID) for database queries

### 4.2 What I Learned

- **JWT local validation** is significantly faster than calling Supabase on every request. The shared JWT secret allows the backend to verify tokens independently.
- **FastAPI's `Depends()` system** makes auth middleware composable — `get_current_user` (required) vs `get_optional_user` (optional) dependencies can be mixed per endpoint.
- The `python-jose` library handles HS256 decoding with built-in expiry checks.

---

## 5. Dual-Mode Watchlist

The most complex frontend change. The watchlist supports two modes transparently:

### Guest Mode (not logged in)
- Stores full `MediaItem[]` in `localStorage['rec-engine-watchlist']`
- Identical behavior to Cycle 1
- No server calls

### Authenticated Mode (logged in)
- Fetches watchlist from `GET /watchlist` on login
- Mutations (`add/remove/clear`) update local state immediately (optimistic) and fire server calls in the background
- Server stores only IDs — full items resolved via the in-memory store

### First-Login Migration
When a user logs in and has items in localStorage:
1. Compare local items against the server watchlist
2. Show an `ImportBanner` component: "You have N items in your local watchlist. Import them?"
3. If accepted: POST each item to the server, merge into state, clear localStorage
4. If dismissed: clear localStorage silently

### What I Learned
- **Optimistic updates** (update UI before server confirms) provide a snappy UX but require error handling to roll back on failure
- **React context provider ordering matters** — `AuthProvider` must wrap `WatchlistProvider` because watchlist behavior depends on auth state
- The `useRef` for `prevUserId` prevents redundant fetches when the component re-renders without an actual auth state change

---

## 6. Backend Changes Summary

### New Files
| File | Purpose |
|---|---|
| `core/supabase_client.py` | Singleton Supabase client using the service role key (bypasses RLS for startup loading) |
| `api/auth.py` | JWT validation — `get_current_user()` and `get_optional_user()` FastAPI dependencies |
| `scripts/seed_supabase.py` | One-time idempotent script to populate Postgres from JSON files |

### Modified Files
| File | Change |
|---|---|
| `core/store.py` | `load()` now tries Supabase first, falls back to JSON if `SUPABASE_URL` is not set |
| `api/routes.py` | Added 4 watchlist CRUD endpoints (`GET/POST/DELETE /watchlist`), auth on coldstart, cold_start_jobs audit writes |
| `main.py` | CORS updated: `allow_credentials=True`, added `DELETE` method |
| `config.py` | Added Supabase env vars |
| `requirements.txt` | Added `supabase`, `python-jose[cryptography]` |

### What I Learned
- **Service role key vs anon key**: The service role key bypasses RLS (needed for bulk loading at startup), while the anon key respects RLS (used by the frontend). Never expose the service role key to the client.
- **Dual-mode loading** (Supabase with JSON fallback) keeps local development frictionless — developers without Supabase access can still run the full system.
- The watchlist recommendation endpoints now support two input methods: explicit IDs in the POST body (backward compatible) or automatic server-side watchlist fetch for authenticated users.

---

## 7. Frontend Changes Summary

### New Files
| File | Purpose |
|---|---|
| `lib/supabase.ts` | Supabase client singleton (anon key) |
| `context/AuthContext.tsx` | Auth state management — `useAuth()` hook |
| `pages/LoginPage.tsx` | Email + password sign-in form |
| `pages/RegisterPage.tsx` | Registration form with email confirmation |
| `components/auth/ProtectedRoute.tsx` | Route guard — redirects to `/login` if unauthenticated |
| `components/watchlist/ImportBanner.tsx` | localStorage migration prompt |

### Modified Files
| File | Change |
|---|---|
| `api/client.ts` | Auto-attaches JWT to all API calls |
| `api/endpoints.ts` | Added watchlist CRUD fetch functions |
| `context/WatchlistContext.tsx` | Rewritten for dual-mode (server + localStorage) |
| `main.tsx` | Added `AuthProvider` wrapping all other providers |
| `App.tsx` | Added `/login`, `/register` routes; protected `/watchlist` and `/discover` |
| `components/layout/Navbar.tsx` | Shows user email + sign out (logged in) or sign in link (guest) |

### What I Learned
- **Supabase's `onAuthStateChange` listener** handles token refresh automatically — the frontend doesn't need to manage token expiry manually
- **React Router's `useLocation` + `state`** enables "redirect back after login" — the ProtectedRoute saves the original path, and LoginPage navigates there on success
- Keeping the `apiFetch` function as the single point for all API calls made JWT attachment trivial — one change, every endpoint covered

---

## 8. Security Model

Three layers of defense:

1. **JWT Signature Verification** (Backend) — Every authenticated request is validated by verifying the ES256 (ECDSA) signature using Supabase's public JWKS endpoint. Invalid or expired tokens get a 401.

2. **Row Level Security** (Database) — Postgres policies filter every query by `auth.uid()`. Even if the application code has a bug, users cannot access other users' data.

3. **Data Integrity** (Schema) — Unique constraints prevent duplicate watchlist entries. Foreign keys with `ON DELETE CASCADE` clean up user data when accounts are deleted. Enum types enforce valid values.

---

## 9. Bug Fix: JWT Authentication Failure (ES256 vs HS256)

### The Problem
After completing the full migration, every authenticated request returned `401 Unauthorized`. Watchlist items appeared in the UI (optimistic updates) but disappeared on page refresh because the server never persisted them.

### Debugging Process
1. **Browser console** showed `[watchlist] add failed: 401 Invalid or expired token` — the token was being sent, but the backend rejected it.
2. Added debug logging to `api/auth.py` to print the actual `JWTError`. The error was: `The specified alg value is not allowed`.
3. Decoded the token header manually and discovered it used **ES256 (ECDSA)**, not HS256 (HMAC) as expected.

### Root Cause
Supabase has moved to **asymmetric ES256 keys** for user access tokens on newer projects. The initial implementation assumed HS256 (symmetric shared secret), which is the older Supabase default. The JWT secret from the Supabase dashboard is still HS256, but it's only used for the anon/service role keys — actual user tokens are signed with a private EC key and must be verified with the **public JWKS**.

### The Fix
Replaced the HS256 shared-secret approach with **JWKS-based verification**:

```python
# Before (broken): shared secret, HS256
jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])

# After (working): fetch public key from JWKS endpoint, ES256
jwks = requests.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json").json()
jwt.decode(token, matching_jwks_key, algorithms=["ES256"])
```

The JWKS is fetched once at startup from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` and cached. Each incoming token's `kid` (key ID) header is matched against the JWKS to find the correct public key.

### Secondary Fix: Token Timing Race
A second issue was discovered: the frontend's `apiFetch` function called `supabase.auth.getSession()` on every request, but right after login the session wasn't persisted in the Supabase JS client yet. This caused the first few requests after login to send no token at all.

**Fix:** Replaced the per-request `getSession()` call with a module-level token variable (`setAccessToken()`) that the `AuthContext` updates synchronously whenever the auth state changes.

### What I Learned
- **Never assume the JWT algorithm** — always check the token header. Supabase's migration from HS256 to ES256 is not well-documented for custom backend integrations.
- **Asymmetric keys (ES256) are more secure** — the private key never leaves Supabase, and the backend only needs the public key to verify. This eliminates the risk of the JWT secret leaking.
- **Debug logging is essential** — adding a single `print(f"JWT error: {e}")` line immediately revealed the root cause. Without it, "401 Unauthorized" gives zero information.
- **Token timing in SPAs matters** — `getSession()` being async means it can return stale data during rapid state transitions. Synchronous token management via module-level state is more reliable.

---

## 10. MCP (Model Context Protocol) for Database Setup

### What is MCP?
MCP (Model Context Protocol) is a standard that allows AI tools like Claude Code to connect directly to external services. Instead of manually running SQL in the Supabase dashboard, I used the **Supabase MCP server** to manage the database schema and data migration directly from the AI-assisted development environment.

### How It Was Used
The Supabase MCP was configured in the project's `.mcp.json` with the project reference:
```json
{
  "mcpServers": {
    "supabase": {
      "type": "http",
      "url": "https://mcp.supabase.com/mcp?project_ref=oixllldlgvblhgzdqrku"
    }
  }
}
```

After OAuth authentication, this gave Claude Code direct access to the Supabase project — enabling schema deployment, table inspection, and data seeding without leaving the development workflow.

### What I Learned
- **MCP bridges AI tools and cloud services** — instead of copy-pasting SQL into web dashboards, the entire database setup was done through the same interface used for coding.
- **Authentication flow for MCP servers** requires an initial OAuth handshake in the browser, after which the connection persists across sessions.
- **MCP is not yet universally supported** — the Supabase MCP required manual setup (CLI command + browser auth), and tool availability depends on the MCP server being properly loaded. Debugging connection issues required checking auth cache files and restarting sessions.
- This was my first time using MCP in a real project, and it significantly streamlined the database migration workflow compared to manual dashboard operations.

---

## 11. What's Deferred to Cycle 3

| Feature | Why Deferred |
|---|---|
| Async cold start (message bus) | Schema ready (`cold_start_jobs` table), but worker/queue infrastructure needed |
| Admin role + RLS bypass | `app_metadata.role` convention planned, no admin dashboard yet |
| Social auth (Google, GitHub) | Email/password sufficient for MVP |
| Realtime watchlist sync | Supabase Realtime supported, but polling/refetch works for now |
| Password reset flow | Low priority for the development phase |

---

## 12. Reflection

### Technical Growth
- Learned how **Supabase Auth integrates with a custom backend** — the frontend uses `supabase-js` for auth flows, while the backend validates JWTs independently using JWKS public keys.
- Understood the tradeoff between **RLS at the database level vs auth checks in application code** — RLS provides a safety net but the backend should still validate to fail fast with clear error messages.
- Gained experience designing a **migration path that doesn't break existing functionality** — the dual-mode store loading and dual-mode watchlist ensure the system works with or without Supabase configured.
- Learned about **JWT algorithms in practice** — the ES256 vs HS256 bug taught me to never hardcode assumptions about token formats and to always verify against the actual token header. This was the most valuable debugging experience of the cycle.
- Gained hands-on experience with **MCP (Model Context Protocol)** for connecting AI development tools directly to cloud services, streamlining the database setup workflow.

### Architecture Decisions
- Choosing **IDs-only storage for watchlists** (instead of denormalized item copies) was driven by the realization that TMDB data refreshes would cause staleness. Since the in-memory store already has all items loaded, resolving IDs is O(1).
- The **cold_start_jobs table** was designed forward-looking — it captures the full pipeline output even though the current flow is synchronous. This means Cycle 3's async migration only needs to add a worker, not change the schema.
- Switching from **shared-secret JWT validation to JWKS-based verification** was forced by Supabase's ES256 migration but turned out to be a better architecture — asymmetric keys mean the backend never holds a secret that could be used to forge tokens.

### Process
- Planning the migration before writing code (the plan document covered schema, backend, frontend, migration script, and scope) prevented scope creep and identified decisions upfront (e.g., ID collisions between movies and shows).
- Working backend-first, then frontend, reduced integration issues — by the time the frontend was built, all API contracts were stable.
- The JWT bug demonstrated the value of **systematic debugging** — adding a single log line to print the actual error and token header immediately revealed the root cause, turning a multi-hour problem into a 5-minute fix.
