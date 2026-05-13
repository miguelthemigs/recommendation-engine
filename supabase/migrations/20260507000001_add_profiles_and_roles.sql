-- ============================================================================
-- Rec Engine — Profiles & Roles (Cycle 4: LLM rate limiting + admin bypass)
-- ============================================================================

-- ── Custom types ─────────────────────────────────────────────────────────────

CREATE TYPE user_role AS ENUM ('user', 'admin');

-- ── Profiles (1:1 with auth.users) ───────────────────────────────────────────

CREATE TABLE profiles (
    id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role       user_role NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Auto-create a profile when a user signs up ───────────────────────────────

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.profiles (id) VALUES (NEW.id)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ── Backfill existing users ──────────────────────────────────────────────────

INSERT INTO profiles (id)
    SELECT id FROM auth.users
    ON CONFLICT (id) DO NOTHING;

-- ── Row Level Security ───────────────────────────────────────────────────────

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read their own profile"
    ON profiles FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- No INSERT/UPDATE/DELETE policies: roles are managed by service role only.
