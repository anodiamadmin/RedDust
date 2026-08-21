-- ============================================================================
-- RedDust / Syan PostgreSQL Schema — MIGRATION 002
-- Adds: user_music_preference, preference_extraction_log, transcript_segment
--
-- Run AFTER migration_001 (reddust_postgresql_schema_and_seed.sql).
-- Safe to re-run — all statements use IF NOT EXISTS or ON CONFLICT DO NOTHING.
--
-- Purpose:
--   These 3 tables form the memory layer that makes Syan smarter over time:
--   1. user_music_preference   — what Syan has learned about a user's taste
--   2. preference_extraction_log — evidence trail for every extracted preference
--   3. transcript_segment      — raw turn-by-turn transcript of every conversation
-- ============================================================================

BEGIN;

SET search_path TO reddust, public;

-- ============================================================================
-- TABLE 1: user_music_preference
--
-- Stores the conclusions Syan has drawn about a user's musical taste.
-- One row per (user_id, preference_type, preference_value) combination.
--
-- Examples:
--   (user_id, 'genre',          'Bollywood',   confidence=0.95)
--   (user_id, 'decade',         '1990s',       confidence=0.80)
--   (user_id, 'mood_avoid',     'sad songs',   confidence=0.90)
--   (user_id, 'life_situation', 'study music', confidence=0.75)
--
-- preference_type values (not enforced as enum — list will grow):
--   genre, artist, decade, language, life_situation, mood_target, mood_avoid
--
-- source: how the preference was last confirmed
--   'per_turn'      — extracted from a single conversation turn
--   'session_batch' — extracted by end-of-session batch analyzer (more reliable)
--
-- override_count: how many times the value was updated/corrected.
--   Useful for detecting unstable preferences (user keeps changing their mind).
-- ============================================================================

CREATE TABLE IF NOT EXISTS reddust.user_music_preference (
    user_id              UUID NOT NULL REFERENCES reddust.app_user(user_id) ON DELETE CASCADE,
    preference_type      TEXT NOT NULL,
    preference_value     TEXT NOT NULL,
    confidence           NUMERIC(5,4) NOT NULL DEFAULT 0.0
                         CHECK (confidence BETWEEN 0 AND 1),
    source               TEXT NOT NULL DEFAULT 'per_turn'
                         CHECK (source IN ('per_turn', 'session_batch')),
    first_observed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_confirmed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    override_count       SMALLINT NOT NULL DEFAULT 0
                         CHECK (override_count >= 0),

    PRIMARY KEY (user_id, preference_type, preference_value)
);

-- Index for fast lookup of all preferences for a given user
CREATE INDEX IF NOT EXISTS ix_user_music_preference_user
    ON reddust.user_music_preference (user_id, preference_type);

-- ============================================================================
-- TABLE 2: preference_extraction_log
--
-- Evidence trail — every time Syan extracts a preference from a turn or
-- session batch, it logs the raw evidence here. Never updated, only inserted.
--
-- Answers: "Why does Syan think this user likes Bollywood?"
--   → find rows for that user+type+value, read raw_evidence to see exact quotes
--
-- extraction_method:
--   'per_turn'      — extracted in real time from a single turn during session
--   'session_batch' — extracted by end-of-session batch analyzer over full transcript
-- ============================================================================

CREATE TABLE IF NOT EXISTS reddust.preference_extraction_log (
    log_id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id              UUID NOT NULL REFERENCES reddust.app_user(user_id) ON DELETE CASCADE,
    session_id           UUID NOT NULL REFERENCES reddust.user_session(session_id) ON DELETE CASCADE,
    conversation_id      UUID NOT NULL REFERENCES reddust.conversation(conversation_id) ON DELETE CASCADE,
    turn_id              BIGINT REFERENCES reddust.conversation_turn(turn_id) ON DELETE SET NULL,
    preference_type      TEXT NOT NULL,
    extracted_value      TEXT NOT NULL,
    confidence           NUMERIC(5,4) NOT NULL DEFAULT 0.0
                         CHECK (confidence BETWEEN 0 AND 1),
    extraction_method    TEXT NOT NULL DEFAULT 'per_turn'
                         CHECK (extraction_method IN ('per_turn', 'session_batch')),
    raw_evidence         TEXT,           -- the exact quote from the transcript that triggered extraction
    extracted_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for looking up extraction history for a user
CREATE INDEX IF NOT EXISTS ix_preference_extraction_log_user
    ON reddust.preference_extraction_log (user_id, preference_type, extracted_at DESC);

-- Index for looking up all extractions within a session
CREATE INDEX IF NOT EXISTS ix_preference_extraction_log_session
    ON reddust.preference_extraction_log (session_id, extracted_at);

-- ============================================================================
-- TABLE 3: transcript_segment
--
-- Stores the raw turn-by-turn transcript of every conversation.
-- One row per spoken segment (a segment is one continuous speech from one speaker).
--
-- speaker values:
--   'user' — the human speaking
--   'syan' — the AI speaking
--
-- segment_index: ordering within a session (monotonically increasing).
-- turn_id: links back to the conversation_turn row for this segment.
--
-- Who reads this table:
--   - preference_extractor.py    — reads user segments to extract music preferences
--   - dimension_scorer.py        — reads full conversation transcript to score dimensions
--   - preference_batch_extractor — reads full session transcript at session end
--   - ARQ worker                 — reads transcript to compute final soul score
-- ============================================================================

CREATE TABLE IF NOT EXISTS reddust.transcript_segment (
    segment_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id       UUID NOT NULL REFERENCES reddust.user_session(session_id) ON DELETE CASCADE,
    conversation_id  UUID NOT NULL REFERENCES reddust.conversation(conversation_id) ON DELETE CASCADE,
    turn_id          BIGINT REFERENCES reddust.conversation_turn(turn_id) ON DELETE SET NULL,
    segment_index    INTEGER NOT NULL CHECK (segment_index >= 0),  -- order within session
    speaker          TEXT NOT NULL CHECK (speaker IN ('user', 'syan')),
    text             TEXT NOT NULL,
    started_at       TIMESTAMPTZ,
    ended_at         TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT transcript_segment_time_order
        CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

-- Index for fetching all segments for a session in order
CREATE INDEX IF NOT EXISTS ix_transcript_segment_session
    ON reddust.transcript_segment (session_id, segment_index);

-- Index for fetching all segments for a conversation in order
CREATE INDEX IF NOT EXISTS ix_transcript_segment_conversation
    ON reddust.transcript_segment (conversation_id, segment_index);

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (run manually after deploying to confirm success)
-- ============================================================================
--
-- SELECT table_name
-- FROM information_schema.tables
-- WHERE table_schema = 'reddust'
--   AND table_name IN (
--       'user_music_preference',
--       'preference_extraction_log',
--       'transcript_segment'
--   );
-- Expected: 3 rows returned
--
-- ============================================================================
