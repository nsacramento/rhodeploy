-- ============================================================
-- Rho — Migration 002: Middle Seat (the boarding game)
-- Run once in Supabase → SQL Editor.
-- Adds:
--   middle_seat_games    async player-vs-player games (challenge codes)
--   middle_seat_results  your record vs the Rho bot
-- ============================================================

-- ── Player-vs-player games ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS middle_seat_games (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code          TEXT UNIQUE NOT NULL,              -- 6-char challenge code
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    rev           INTEGER NOT NULL DEFAULT 0,        -- optimistic lock, +1 per save
    player1       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    player1_name  TEXT,
    player2       UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    player2_name  TEXT,
    plane         TEXT,
    mode          TEXT,
    status        TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'active', 'finished')),
    turn_uid      UUID,                              -- whose move it is
    winner        TEXT,                              -- 'p1' | 'p2' | 'tie'
    state         JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS middle_seat_games_p1   ON middle_seat_games (player1);
CREATE INDEX IF NOT EXISTS middle_seat_games_p2   ON middle_seat_games (player2);

ALTER TABLE middle_seat_games ENABLE ROW LEVEL SECURITY;

-- Players see their own games; anyone signed in can see an OPEN challenge (to join by code)
DROP POLICY IF EXISTS "ms_games_select" ON middle_seat_games;
CREATE POLICY "ms_games_select" ON middle_seat_games FOR SELECT
    USING (auth.uid() = player1 OR auth.uid() = player2
           OR (status = 'open' AND player2 IS NULL));

DROP POLICY IF EXISTS "ms_games_insert" ON middle_seat_games;
CREATE POLICY "ms_games_insert" ON middle_seat_games FOR INSERT
    WITH CHECK (auth.uid() = player1);

-- Players update their own games; a newcomer may claim an open seat as player2
DROP POLICY IF EXISTS "ms_games_update" ON middle_seat_games;
CREATE POLICY "ms_games_update" ON middle_seat_games FOR UPDATE
    USING (auth.uid() = player1 OR auth.uid() = player2
           OR (status = 'open' AND player2 IS NULL))
    WITH CHECK (auth.uid() = player1 OR auth.uid() = player2);

DROP POLICY IF EXISTS "ms_games_delete" ON middle_seat_games;
CREATE POLICY "ms_games_delete" ON middle_seat_games FOR DELETE
    USING (auth.uid() = player1);

-- ── Results vs the Rho bot ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS middle_seat_results (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    opponent    TEXT NOT NULL DEFAULT 'bot',
    plane       TEXT,
    mode        TEXT,
    my_score    INTEGER,
    opp_score   INTEGER,
    result      TEXT CHECK (result IN ('win', 'loss', 'tie')),
    end_reason  TEXT
);

CREATE INDEX IF NOT EXISTS middle_seat_results_user ON middle_seat_results (user_id);

ALTER TABLE middle_seat_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "ms_results_own" ON middle_seat_results;
CREATE POLICY "ms_results_own" ON middle_seat_results FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
