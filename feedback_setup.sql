-- Rho — Feedback table
-- Run once in Supabase dashboard → SQL Editor

CREATE TABLE IF NOT EXISTS feedback (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT now(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    feature     TEXT NOT NULL,
    rating      INTEGER CHECK (rating BETWEEN 1 AND 5),
    message     TEXT NOT NULL
);

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- Any authenticated user can submit feedback
CREATE POLICY "Users can submit feedback"
    ON feedback FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

-- Users can read their own feedback
CREATE POLICY "Users can read own feedback"
    ON feedback FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Admin (nsacramento2@gmail.com) can read ALL feedback
CREATE POLICY "Admin can read all feedback"
    ON feedback FOR SELECT
    TO authenticated
    USING (auth.jwt() ->> 'email' = 'nsacramento2@gmail.com');
