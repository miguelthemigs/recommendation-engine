-- ============================================================================
-- Rec Engine — Supabase Schema Migration
-- ============================================================================

-- ── Custom types ─────────────────────────────────────────────────────────────

CREATE TYPE media_type AS ENUM ('movie', 'show');
CREATE TYPE cold_start_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- ── Movies ───────────────────────────────────────────────────────────────────

CREATE TABLE movies (
    tmdb_id      INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    year         INTEGER,
    overview     TEXT NOT NULL DEFAULT '',
    genres       TEXT[] NOT NULL DEFAULT '{}',
    keywords     TEXT[] NOT NULL DEFAULT '{}',
    "cast"       TEXT[] NOT NULL DEFAULT '{}',
    vote_average DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    popularity   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    poster_path  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_movies_popularity ON movies (popularity DESC);

-- ── Shows ────────────────────────────────────────────────────────────────────

CREATE TABLE shows (
    tmdb_id      INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    year         INTEGER,
    overview     TEXT NOT NULL DEFAULT '',
    genres       TEXT[] NOT NULL DEFAULT '{}',
    keywords     TEXT[] NOT NULL DEFAULT '{}',
    "cast"       TEXT[] NOT NULL DEFAULT '{}',
    vote_average DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    popularity   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    poster_path  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_shows_popularity ON shows (popularity DESC);

-- ── Genres ───────────────────────────────────────────────────────────────────

CREATE TABLE genres (
    id       SERIAL PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN ('movie', 'tv')),
    tmdb_id  TEXT NOT NULL,
    name     TEXT NOT NULL,
    UNIQUE (category, tmdb_id)
);

-- ── Watchlists ───────────────────────────────────────────────────────────────

CREATE TABLE watchlists (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tmdb_id    INTEGER NOT NULL,
    media_type media_type NOT NULL,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, tmdb_id, media_type)
);

CREATE INDEX idx_watchlists_user ON watchlists (user_id);

-- ── Cold Start Jobs ──────────────────────────────────────────────────────────

CREATE TABLE cold_start_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status          cold_start_status NOT NULL DEFAULT 'pending',
    -- Input
    answers         JSONB NOT NULL,
    -- Output (populated on completion)
    signals         JSONB,
    seed_ids        TEXT[],
    recommendations JSONB,
    token_cost      JSONB,
    llm_time_ms     DOUBLE PRECISION,
    total_time_ms   DOUBLE PRECISION,
    error_message   TEXT,
    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_cold_start_jobs_user ON cold_start_jobs (user_id, created_at DESC);

-- ── Row Level Security ───────────────────────────────────────────────────────

-- Movies & Shows: public read, no write via API
ALTER TABLE movies ENABLE ROW LEVEL SECURITY;
ALTER TABLE shows ENABLE ROW LEVEL SECURITY;
ALTER TABLE genres ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Movies are publicly readable"
    ON movies FOR SELECT USING (true);

CREATE POLICY "Shows are publicly readable"
    ON shows FOR SELECT USING (true);

CREATE POLICY "Genres are publicly readable"
    ON genres FOR SELECT USING (true);

-- Watchlists: users see only their own
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own watchlist"
    ON watchlists FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own watchlist items"
    ON watchlists FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own watchlist items"
    ON watchlists FOR DELETE
    USING (auth.uid() = user_id);

-- Cold start jobs: users see only their own
ALTER TABLE cold_start_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own cold start jobs"
    ON cold_start_jobs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create own cold start jobs"
    ON cold_start_jobs FOR INSERT
    WITH CHECK (auth.uid() = user_id);
