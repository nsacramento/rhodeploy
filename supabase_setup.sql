-- ============================================================
-- Rho — Supabase SQL Setup
-- Run this ONCE in the Supabase SQL editor (Dashboard → SQL)
-- before using the Profile or Instructor features.
-- ============================================================

-- ── profiles ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT NOT NULL,
    full_name   TEXT,
    role        TEXT DEFAULT 'student' CHECK (role IN ('student', 'instructor')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "profiles_own" ON profiles FOR ALL
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());


-- ── instructor_students ───────────────────────────────────────────────────────
-- Must be created BEFORE the profiles_connections policy (which references it)
CREATE TABLE IF NOT EXISTS instructor_students (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    instructor_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    student_id    UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status        TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instructor_id, student_id)
);
ALTER TABLE instructor_students ENABLE ROW LEVEL SECURITY;

CREATE POLICY "instructor_students_access" ON instructor_students FOR ALL
    USING  (instructor_id = auth.uid() OR student_id = auth.uid())
    WITH CHECK (instructor_id = auth.uid() OR student_id = auth.uid());


-- ── profiles_connections policy (added AFTER instructor_students exists) ──────
CREATE POLICY "profiles_connections" ON profiles FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM instructor_students
            WHERE (
                (instructor_id = auth.uid() AND student_id = profiles.id)
                OR
                (student_id = auth.uid() AND instructor_id = profiles.id)
            )
            AND status = 'accepted'
        )
    );


-- ── instructor_invites ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instructor_invites (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    token            TEXT UNIQUE NOT NULL DEFAULT gen_random_uuid()::text,
    student_id       UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    instructor_email TEXT,
    status           TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'expired')),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    expires_at       TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days')
);
ALTER TABLE instructor_invites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "invites_student" ON instructor_invites FOR ALL
    USING  (student_id = auth.uid())
    WITH CHECK (student_id = auth.uid());

CREATE POLICY "invites_token_read" ON instructor_invites FOR SELECT
    USING (true);


-- ── instructor_skill_ratings ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instructor_skill_ratings (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    flight_id     UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    student_id    UUID NOT NULL REFERENCES profiles(id),
    instructor_id UUID NOT NULL REFERENCES profiles(id),
    task_id       TEXT NOT NULL,
    rating        INTEGER NOT NULL CHECK (rating IN (1, 2, 3)),
    note          TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(flight_id, instructor_id, task_id)
);
ALTER TABLE instructor_skill_ratings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "inst_ratings_instructor" ON instructor_skill_ratings FOR ALL
    USING  (instructor_id = auth.uid())
    WITH CHECK (instructor_id = auth.uid());

CREATE POLICY "inst_ratings_student" ON instructor_skill_ratings FOR SELECT
    USING (student_id = auth.uid());


-- ── Cross-user RLS on existing tables ────────────────────────────────────────
CREATE POLICY "flights_instructor_read" ON flights FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM instructor_students
            WHERE instructor_id = auth.uid()
              AND student_id    = flights.user_id
              AND status        = 'accepted'
        )
    );

CREATE POLICY "skill_log_instructor_read" ON skill_log FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM instructor_students
            WHERE instructor_id = auth.uid()
              AND student_id    = skill_log.user_id
              AND status        = 'accepted'
        )
    );
