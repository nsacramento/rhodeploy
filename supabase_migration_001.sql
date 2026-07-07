-- ============================================================
-- Rho — Migration 001
-- Run in Supabase SQL Editor AFTER supabase_setup.sql
-- Adds: aircraft selection, tail numbers, brief timestamps
-- ============================================================

-- ── profiles: aircraft + tail number ─────────────────────────────────────────
ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS aircraft_type TEXT,   -- key from AIRCRAFT_TYPES dict (e.g. 'c172s')
    ADD COLUMN IF NOT EXISTS tail_number   TEXT;   -- e.g. 'N12345'

-- ── flights: aircraft, tail number, brief timestamp ──────────────────────────
ALTER TABLE flights
    ADD COLUMN IF NOT EXISTS aircraft_type TEXT,   -- snapshot of type at brief time
    ADD COLUMN IF NOT EXISTS tail_number   TEXT,   -- tail number flown
    ADD COLUMN IF NOT EXISTS brief_at      TIMESTAMPTZ;  -- when brief was generated

-- ── instructor_skill_ratings: allow students to read their own ratings ────────
-- Students need to see instructor ratings on the ACS page.
-- Run only if this policy doesn't already exist in your project.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'instructor_skill_ratings'
      AND policyname = 'students_read_own_instructor_ratings'
  ) THEN
    EXECUTE $policy$
      CREATE POLICY "students_read_own_instructor_ratings"
      ON instructor_skill_ratings
      FOR SELECT
      USING (student_id = auth.uid() OR instructor_id = auth.uid())
    $policy$;
  END IF;
END $$;
