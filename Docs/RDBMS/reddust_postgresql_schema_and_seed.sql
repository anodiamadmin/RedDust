-- ============================================================================
-- RedDust / Syan PostgreSQL Schema
-- Purpose:
--   Users -> sessions -> conversations -> turns
--   Conversation/session/period summaries
--   Multidimensional Soul Score with duration-dependent weighting
--   Music catalogue, recommendations, reactions and listening behaviour
--
-- PostgreSQL target: 15+
-- ============================================================================
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS reddust;
SET search_path TO reddust, public;

-- ============================================================================
-- 1. CONFIGURATION / REFERENCE TABLES
-- ============================================================================

CREATE TABLE IF NOT EXISTS soul_score_config (
    config_id                    SMALLINT PRIMARY KEY DEFAULT 1,
    methodology_version          TEXT NOT NULL DEFAULT '1.0',
    score_min                    NUMERIC(5,2) NOT NULL DEFAULT 0,
    score_max                    NUMERIC(5,2) NOT NULL DEFAULT 100,
    short_term_days              INTEGER NOT NULL DEFAULT 28 CHECK (short_term_days > 0),
    long_term_days               INTEGER NOT NULL DEFAULT 365 CHECK (long_term_days > short_term_days),
    default_dashboard_dimensions SMALLINT NOT NULL DEFAULT 8 CHECK (default_dashboard_dimensions > 0),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT soul_score_config_singleton CHECK (config_id = 1),
    CONSTRAINT soul_score_config_range CHECK (score_max > score_min)
);

CREATE TABLE IF NOT EXISTS soul_score_duration_policy (
    duration_code         TEXT PRIMARY KEY,
    sort_order            SMALLINT NOT NULL UNIQUE,
    current_weight        NUMERIC(6,5) NOT NULL CHECK (current_weight BETWEEN 0 AND 1),
    short_history_weight  NUMERIC(6,5) NOT NULL CHECK (short_history_weight BETWEEN 0 AND 1),
    long_history_weight   NUMERIC(6,5) NOT NULL CHECK (long_history_weight BETWEEN 0 AND 1),
    description           TEXT,
    CONSTRAINT soul_score_duration_policy_weights_sum
        CHECK (abs((current_weight + short_history_weight + long_history_weight) - 1.0) < 0.00001)
);

CREATE TABLE IF NOT EXISTS wellbeing_dimension (
    dimension_id           SMALLINT PRIMARY KEY,
    dimension_name         TEXT NOT NULL UNIQUE,
    negative_dimension     TEXT NOT NULL,
    duration_code          TEXT NOT NULL REFERENCES soul_score_duration_policy(duration_code),
    is_primary             BOOLEAN NOT NULL DEFAULT FALSE,
    default_dashboard_rank SMALLINT,
    research_basis         TEXT,
    is_enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wellbeing_dimension_primary_rank
        CHECK (
            (is_primary = TRUE  AND default_dashboard_rank IS NOT NULL)
            OR
            (is_primary = FALSE AND default_dashboard_rank IS NULL)
        )
);

CREATE TABLE IF NOT EXISTS summary_period_type (
    period_type TEXT PRIMARY KEY,
    sort_order  SMALLINT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS music_reaction_scale (
    rating      SMALLINT PRIMARY KEY CHECK (rating BETWEEN 1 AND 5),
    code        TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    description TEXT
);

-- ============================================================================
-- 2. USERS, SESSIONS, CONVERSATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS app_user (
    user_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_auth_subject TEXT UNIQUE,
    email                 TEXT,
    display_name          TEXT,
    locale                TEXT,
    timezone              TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at            TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_app_user_email_lower
    ON app_user (lower(email))
    WHERE email IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS user_session (
    session_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at         TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','completed','abandoned','failed')),
    client_platform  TEXT,
    app_version      TEXT,
    session_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_session_time_order CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS ix_user_session_user_started
    ON user_session (user_id, started_at DESC);

CREATE TABLE IF NOT EXISTS conversation (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES user_session(session_id) ON DELETE CASCADE,
    sequence_no     INTEGER NOT NULL CHECK (sequence_no > 0),
    topic           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, sequence_no),
    CONSTRAINT conversation_time_order CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS ix_conversation_session
    ON conversation (session_id, sequence_no);

CREATE TABLE IF NOT EXISTS conversation_turn (
    turn_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id  UUID NOT NULL REFERENCES conversation(conversation_id) ON DELETE CASCADE,
    turn_no          INTEGER NOT NULL CHECK (turn_no > 0),
    speaker          TEXT NOT NULL CHECK (speaker IN ('user','syan','system','tool')),
    transcript_text  TEXT,
    started_at       TIMESTAMPTZ,
    ended_at         TIMESTAMPTZ,
    tone_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    tool_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, turn_no),
    CONSTRAINT conversation_turn_time_order CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE INDEX IF NOT EXISTS ix_conversation_turn_conversation
    ON conversation_turn (conversation_id, turn_no);

-- ============================================================================
-- 3. SUMMARIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversation_summary (
    conversation_id UUID PRIMARY KEY REFERENCES conversation(conversation_id) ON DELETE CASCADE,
    summary_text     TEXT NOT NULL,
    key_topics       JSONB NOT NULL DEFAULT '[]'::jsonb,
    emotional_notes  JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_name       TEXT,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_summary (
    session_id       UUID PRIMARY KEY REFERENCES user_session(session_id) ON DELETE CASCADE,
    summary_text     TEXT NOT NULL,
    key_topics       JSONB NOT NULL DEFAULT '[]'::jsonb,
    progress_notes   JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_name       TEXT,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_period_summary (
    period_summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    period_type       TEXT NOT NULL REFERENCES summary_period_type(period_type),
    period_start      DATE NOT NULL,
    period_end        DATE NOT NULL,
    summary_text      TEXT NOT NULL,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_name        TEXT,
    UNIQUE (user_id, period_type, period_start, period_end),
    CONSTRAINT user_period_summary_date_order CHECK (period_end >= period_start)
);

CREATE INDEX IF NOT EXISTS ix_user_period_summary_user_period
    ON user_period_summary (user_id, period_type, period_end DESC);

-- ============================================================================
-- 4. SOUL SCORE: SIGNALS, DIMENSION STATE, CONVERSATION & SESSION SCORES
-- ============================================================================

-- Explainable source evidence used by the scoring layer.
-- source_type intentionally remains extensible rather than being a fixed enum.
CREATE TABLE IF NOT EXISTS wellbeing_signal (
    signal_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    session_id       UUID REFERENCES user_session(session_id) ON DELETE CASCADE,
    conversation_id  UUID REFERENCES conversation(conversation_id) ON DELETE CASCADE,
    turn_id          BIGINT REFERENCES conversation_turn(turn_id) ON DELETE SET NULL,
    dimension_id     SMALLINT REFERENCES wellbeing_dimension(dimension_id),
    source_type      TEXT NOT NULL,
    raw_score        NUMERIC(5,2) CHECK (raw_score BETWEEN 0 AND 100),
    direction        SMALLINT CHECK (direction IN (-1,0,1)),
    confidence       NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    evidence_text    TEXT,
    evidence_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_wellbeing_signal_user_dimension_time
    ON wellbeing_signal (user_id, dimension_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS ix_wellbeing_signal_session
    ON wellbeing_signal (session_id, observed_at);

-- Current display/monitoring state of every dimension for a user.
CREATE TABLE IF NOT EXISTS user_dimension_state (
    user_id           UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    dimension_id      SMALLINT NOT NULL REFERENCES wellbeing_dimension(dimension_id),
    visibility_state  TEXT NOT NULL CHECK (visibility_state IN ('active','hidden','passive')),
    dashboard_rank    SMALLINT,
    priority_score    NUMERIC(6,3) NOT NULL DEFAULT 0,
    activation_reason TEXT,
    activated_at      TIMESTAMPTZ,
    last_reviewed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, dimension_id),
    CONSTRAINT user_dimension_state_rank
        CHECK (
            (visibility_state = 'active' AND dashboard_rank IS NOT NULL)
            OR
            (visibility_state <> 'active' AND dashboard_rank IS NULL)
        )
);

CREATE INDEX IF NOT EXISTS ix_user_dimension_state_dashboard
    ON user_dimension_state (user_id, visibility_state, dashboard_rank);

CREATE UNIQUE INDEX IF NOT EXISTS ux_user_dimension_state_active_rank
    ON user_dimension_state (user_id, dashboard_rank)
    WHERE visibility_state = 'active' AND dashboard_rank IS NOT NULL;

CREATE TABLE IF NOT EXISTS user_dimension_state_event (
    state_event_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    dimension_id      SMALLINT NOT NULL REFERENCES wellbeing_dimension(dimension_id),
    old_state         TEXT CHECK (old_state IN ('active','hidden','passive')),
    new_state         TEXT NOT NULL CHECK (new_state IN ('active','hidden','passive')),
    reason_code       TEXT,
    reason_text       TEXT,
    triggering_signal_id UUID REFERENCES wellbeing_signal(signal_id) ON DELETE SET NULL,
    changed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_user_dimension_state_event
    ON user_dimension_state_event (user_id, dimension_id, changed_at DESC);

-- One score per dimension per conversation.
CREATE TABLE IF NOT EXISTS conversation_dimension_score (
    conversation_id UUID NOT NULL REFERENCES conversation(conversation_id) ON DELETE CASCADE,
    dimension_id    SMALLINT NOT NULL REFERENCES wellbeing_dimension(dimension_id),
    score           NUMERIC(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    confidence      NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    rationale       TEXT,
    evidence_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    algorithm_version TEXT NOT NULL DEFAULT '1.0',
    calculated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, dimension_id)
);

CREATE INDEX IF NOT EXISTS ix_conversation_dimension_score_dimension
    ON conversation_dimension_score (dimension_id, calculated_at DESC);

-- Current-session score per dimension.
-- This can be supplied by the final session assessment or derived from conversation scores.
CREATE TABLE IF NOT EXISTS session_dimension_score (
    session_id       UUID NOT NULL REFERENCES user_session(session_id) ON DELETE CASCADE,
    dimension_id     SMALLINT NOT NULL REFERENCES wellbeing_dimension(dimension_id),
    score            NUMERIC(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    confidence       NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    source_method    TEXT NOT NULL DEFAULT 'conversation_aggregate',
    source_conversation_count INTEGER NOT NULL DEFAULT 0 CHECK (source_conversation_count >= 0),
    rationale        TEXT,
    evidence_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    algorithm_version TEXT NOT NULL DEFAULT '1.0',
    calculated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, dimension_id)
);

CREATE INDEX IF NOT EXISTS ix_session_dimension_score_dimension
    ON session_dimension_score (dimension_id, calculated_at DESC);

-- Persisted dashboard-ready result, including all three components for explainability.
CREATE TABLE IF NOT EXISTS user_soul_score_snapshot (
    snapshot_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    dimension_id         SMALLINT NOT NULL REFERENCES wellbeing_dimension(dimension_id),
    as_of_session_id     UUID NOT NULL REFERENCES user_session(session_id) ON DELETE CASCADE,
    current_session_score NUMERIC(5,2),
    short_history_score   NUMERIC(5,2),
    long_history_score    NUMERIC(5,2),
    current_weight        NUMERIC(6,5) NOT NULL,
    short_history_weight  NUMERIC(6,5) NOT NULL,
    long_history_weight   NUMERIC(6,5) NOT NULL,
    final_score           NUMERIC(5,2) NOT NULL CHECK (final_score BETWEEN 0 AND 100),
    confidence            NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
    duration_code         TEXT NOT NULL REFERENCES soul_score_duration_policy(duration_code),
    calculation_version   TEXT NOT NULL DEFAULT '1.0',
    calculated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, dimension_id, as_of_session_id)
);

CREATE INDEX IF NOT EXISTS ix_user_soul_score_snapshot_latest
    ON user_soul_score_snapshot (user_id, dimension_id, calculated_at DESC);

-- ============================================================================
-- 5. MUSIC CATALOGUE
-- ============================================================================

CREATE TABLE IF NOT EXISTS music_track (
    track_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider           TEXT NOT NULL DEFAULT 'youtube',
    provider_track_id  TEXT,
    track_url          TEXT NOT NULL,
    title              TEXT NOT NULL,
    album_title        TEXT,
    release_year       SMALLINT CHECK (release_year BETWEEN 1800 AND 2200),
    release_decade     SMALLINT GENERATED ALWAYS AS (
                           CASE WHEN release_year IS NULL
                                THEN NULL
                                ELSE (release_year / 10) * 10
                           END
                       ) STORED,
    duration_ms        INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    explicit_content   BOOLEAN,
    metadata_json      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_track_id)
);

CREATE INDEX IF NOT EXISTS ix_music_track_title
    ON music_track (lower(title));

CREATE TABLE IF NOT EXISTS music_artist (
    artist_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artist_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS music_track_artist (
    track_id    UUID NOT NULL REFERENCES music_track(track_id) ON DELETE CASCADE,
    artist_id   UUID NOT NULL REFERENCES music_artist(artist_id) ON DELETE CASCADE,
    artist_role TEXT NOT NULL DEFAULT 'primary',
    artist_order SMALLINT NOT NULL DEFAULT 1 CHECK (artist_order > 0),
    PRIMARY KEY (track_id, artist_id, artist_role)
);

CREATE TABLE IF NOT EXISTS music_genre (
    genre_id   SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    genre_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS music_track_genre (
    track_id UUID NOT NULL REFERENCES music_track(track_id) ON DELETE CASCADE,
    genre_id SMALLINT NOT NULL REFERENCES music_genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (track_id, genre_id)
);

CREATE TABLE IF NOT EXISTS music_language (
    language_code TEXT PRIMARY KEY,
    language_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS music_track_language (
    track_id      UUID NOT NULL REFERENCES music_track(track_id) ON DELETE CASCADE,
    language_code TEXT NOT NULL REFERENCES music_language(language_code),
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (track_id, language_code)
);

-- ============================================================================
-- 6. MUSIC RECOMMENDATIONS, REACTIONS, BEHAVIOUR
-- ============================================================================

CREATE TABLE IF NOT EXISTS music_recommendation (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    session_id        UUID NOT NULL REFERENCES user_session(session_id) ON DELETE CASCADE,
    conversation_id   UUID NOT NULL REFERENCES conversation(conversation_id) ON DELETE CASCADE,
    turn_id           BIGINT REFERENCES conversation_turn(turn_id) ON DELETE SET NULL,
    track_id          UUID NOT NULL REFERENCES music_track(track_id),
    recommendation_rank SMALLINT NOT NULL DEFAULT 1 CHECK (recommendation_rank > 0),
    desired_outcome   TEXT,
    rationale         TEXT,
    recommendation_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommended_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_music_recommendation_user_time
    ON music_recommendation (user_id, recommended_at DESC);

CREATE INDEX IF NOT EXISTS ix_music_recommendation_conversation
    ON music_recommendation (conversation_id, recommended_at);

CREATE TABLE IF NOT EXISTS music_recommendation_dimension (
    recommendation_id UUID NOT NULL REFERENCES music_recommendation(recommendation_id) ON DELETE CASCADE,
    dimension_id      SMALLINT NOT NULL REFERENCES wellbeing_dimension(dimension_id),
    target_direction  TEXT NOT NULL DEFAULT 'support'
                      CHECK (target_direction IN ('increase','decrease_negative','stabilise','support')),
    target_weight     NUMERIC(5,4) NOT NULL DEFAULT 1.0 CHECK (target_weight BETWEEN 0 AND 1),
    PRIMARY KEY (recommendation_id, dimension_id)
);

CREATE TABLE IF NOT EXISTS music_recommendation_reaction (
    recommendation_id UUID PRIMARY KEY REFERENCES music_recommendation(recommendation_id) ON DELETE CASCADE,
    rating             SMALLINT REFERENCES music_reaction_scale(rating),
    played             BOOLEAN NOT NULL DEFAULT FALSE,
    completed          BOOLEAN NOT NULL DEFAULT FALSE,
    skipped            BOOLEAN NOT NULL DEFAULT FALSE,
    replayed           BOOLEAN NOT NULL DEFAULT FALSE,
    played_along       BOOLEAN NOT NULL DEFAULT FALSE,
    listened_seconds   INTEGER CHECK (listened_seconds IS NULL OR listened_seconds >= 0),
    free_text          TEXT,
    reacted_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Generic listening behaviour supports the methodology's behavioural evidence:
-- played, skipped, replayed, liked, favourite, etc.
CREATE TABLE IF NOT EXISTS music_interaction_event (
    interaction_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          UUID NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
    session_id       UUID REFERENCES user_session(session_id) ON DELETE SET NULL,
    conversation_id  UUID REFERENCES conversation(conversation_id) ON DELETE SET NULL,
    recommendation_id UUID REFERENCES music_recommendation(recommendation_id) ON DELETE SET NULL,
    track_id         UUID NOT NULL REFERENCES music_track(track_id),
    event_type       TEXT NOT NULL,
    event_value      NUMERIC,
    event_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_music_interaction_user_time
    ON music_interaction_event (user_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS ix_music_interaction_track
    ON music_interaction_event (track_id, occurred_at DESC);

-- ============================================================================
-- 7. INITIALISE ALL 32 DIMENSIONS FOR A NEW USER
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_initialise_user_dimensions()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO user_dimension_state (
        user_id,
        dimension_id,
        visibility_state,
        dashboard_rank,
        priority_score,
        activation_reason,
        activated_at
    )
    SELECT
        NEW.user_id,
        d.dimension_id,
        CASE WHEN d.is_primary THEN 'active' ELSE 'hidden' END,
        d.default_dashboard_rank,
        CASE WHEN d.is_primary THEN 100 ELSE 0 END,
        CASE WHEN d.is_primary THEN 'Primary foundational Soul dimension' ELSE NULL END,
        CASE WHEN d.is_primary THEN now() ELSE NULL END
    FROM wellbeing_dimension d
    WHERE d.is_enabled = TRUE
    ON CONFLICT (user_id, dimension_id) DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_initialise_user_dimensions ON app_user;

CREATE TRIGGER trg_initialise_user_dimensions
AFTER INSERT ON app_user
FOR EACH ROW
EXECUTE FUNCTION fn_initialise_user_dimensions();

-- ============================================================================
-- 8. SESSION SCORE AGGREGATION FROM CONVERSATION SCORES
-- ============================================================================

CREATE OR REPLACE PROCEDURE refresh_session_dimension_scores(p_session_id UUID)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO session_dimension_score (
        session_id,
        dimension_id,
        score,
        confidence,
        source_method,
        source_conversation_count,
        rationale,
        algorithm_version,
        calculated_at
    )
    SELECT
        c.session_id,
        cds.dimension_id,
        ROUND(
            COALESCE(
                SUM(cds.score * cds.confidence) / NULLIF(SUM(cds.confidence), 0),
                AVG(cds.score)
            ),
            2
        ) AS score,
        ROUND(AVG(cds.confidence), 4) AS confidence,
        'conversation_aggregate',
        COUNT(*)::INTEGER,
        'Confidence-weighted aggregate of conversation-level dimension scores',
        MAX(cds.algorithm_version),
        now()
    FROM conversation c
    JOIN conversation_dimension_score cds
      ON cds.conversation_id = c.conversation_id
    WHERE c.session_id = p_session_id
    GROUP BY c.session_id, cds.dimension_id
    ON CONFLICT (session_id, dimension_id)
    DO UPDATE SET
        score = EXCLUDED.score,
        confidence = EXCLUDED.confidence,
        source_method = EXCLUDED.source_method,
        source_conversation_count = EXCLUDED.source_conversation_count,
        rationale = EXCLUDED.rationale,
        algorithm_version = EXCLUDED.algorithm_version,
        calculated_at = now();
END;
$$;

-- ============================================================================
-- 9. COMPUTE DURATION-WEIGHTED SOUL SCORE
--
-- Definition used here:
--   CURRENT    = the specified session's dimension score
--   SHORT TERM = prior session scores inside config.short_term_days
--   LONG TERM  = prior scores older than the short-term window, but inside
--                config.long_term_days
--
-- If a component is absent, the available weights are automatically
-- re-normalised rather than treating the missing component as zero.
-- ============================================================================

CREATE OR REPLACE FUNCTION compute_soul_score(
    p_user_id UUID,
    p_as_of_session_id UUID
)
RETURNS TABLE (
    dimension_id SMALLINT,
    dimension_name TEXT,
    duration_code TEXT,
    current_session_score NUMERIC,
    short_history_score NUMERIC,
    long_history_score NUMERIC,
    current_weight NUMERIC,
    short_history_weight NUMERIC,
    long_history_weight NUMERIC,
    final_score NUMERIC,
    confidence NUMERIC
)
LANGUAGE SQL
STABLE
AS $$
WITH cfg AS (
    SELECT *
    FROM soul_score_config
    WHERE config_id = 1
),
anchor AS (
    SELECT s.session_id, s.user_id, s.started_at
    FROM user_session s
    WHERE s.session_id = p_as_of_session_id
      AND s.user_id = p_user_id
),
base AS (
    SELECT
        d.dimension_id,
        d.dimension_name,
        d.duration_code,
        p.current_weight,
        p.short_history_weight,
        p.long_history_weight,
        sds.score AS current_session_score,
        sds.confidence AS current_confidence,
        a.started_at AS anchor_time,
        cfg.short_term_days,
        cfg.long_term_days
    FROM wellbeing_dimension d
    JOIN soul_score_duration_policy p
      ON p.duration_code = d.duration_code
    CROSS JOIN anchor a
    CROSS JOIN cfg
    LEFT JOIN session_dimension_score sds
      ON sds.session_id = a.session_id
     AND sds.dimension_id = d.dimension_id
    WHERE d.is_enabled = TRUE
),
history AS (
    SELECT
        b.*,

        (
            SELECT ROUND(
                COALESCE(
                    SUM(hs.score * hs.confidence) / NULLIF(SUM(hs.confidence), 0),
                    AVG(hs.score)
                ),
                2
            )
            FROM session_dimension_score hs
            JOIN user_session us
              ON us.session_id = hs.session_id
            WHERE us.user_id = p_user_id
              AND hs.dimension_id = b.dimension_id
              AND hs.session_id <> p_as_of_session_id
              AND us.started_at < b.anchor_time
              AND us.started_at >=
                  b.anchor_time - (b.short_term_days::TEXT || ' days')::INTERVAL
        ) AS short_history_score,

        (
            SELECT AVG(hs.confidence)
            FROM session_dimension_score hs
            JOIN user_session us
              ON us.session_id = hs.session_id
            WHERE us.user_id = p_user_id
              AND hs.dimension_id = b.dimension_id
              AND hs.session_id <> p_as_of_session_id
              AND us.started_at < b.anchor_time
              AND us.started_at >=
                  b.anchor_time - (b.short_term_days::TEXT || ' days')::INTERVAL
        ) AS short_confidence,

        (
            SELECT ROUND(
                COALESCE(
                    SUM(hs.score * hs.confidence) / NULLIF(SUM(hs.confidence), 0),
                    AVG(hs.score)
                ),
                2
            )
            FROM session_dimension_score hs
            JOIN user_session us
              ON us.session_id = hs.session_id
            WHERE us.user_id = p_user_id
              AND hs.dimension_id = b.dimension_id
              AND hs.session_id <> p_as_of_session_id
              AND us.started_at <
                  b.anchor_time - (b.short_term_days::TEXT || ' days')::INTERVAL
              AND us.started_at >=
                  b.anchor_time - (b.long_term_days::TEXT || ' days')::INTERVAL
        ) AS long_history_score,

        (
            SELECT AVG(hs.confidence)
            FROM session_dimension_score hs
            JOIN user_session us
              ON us.session_id = hs.session_id
            WHERE us.user_id = p_user_id
              AND hs.dimension_id = b.dimension_id
              AND hs.session_id <> p_as_of_session_id
              AND us.started_at <
                  b.anchor_time - (b.short_term_days::TEXT || ' days')::INTERVAL
              AND us.started_at >=
                  b.anchor_time - (b.long_term_days::TEXT || ' days')::INTERVAL
        ) AS long_confidence

    FROM base b
),
weighted AS (
    SELECT
        h.*,

        (
            CASE WHEN current_session_score IS NOT NULL
                 THEN current_session_score * current_weight ELSE 0 END
          + CASE WHEN short_history_score IS NOT NULL
                 THEN short_history_score * short_history_weight ELSE 0 END
          + CASE WHEN long_history_score IS NOT NULL
                 THEN long_history_score * long_history_weight ELSE 0 END
        ) AS weighted_score_numerator,

        (
            CASE WHEN current_session_score IS NOT NULL
                 THEN current_weight ELSE 0 END
          + CASE WHEN short_history_score IS NOT NULL
                 THEN short_history_weight ELSE 0 END
          + CASE WHEN long_history_score IS NOT NULL
                 THEN long_history_weight ELSE 0 END
        ) AS available_weight,

        (
            CASE WHEN current_session_score IS NOT NULL AND current_confidence IS NOT NULL
                 THEN current_confidence * current_weight ELSE 0 END
          + CASE WHEN short_history_score IS NOT NULL AND short_confidence IS NOT NULL
                 THEN short_confidence * short_history_weight ELSE 0 END
          + CASE WHEN long_history_score IS NOT NULL AND long_confidence IS NOT NULL
                 THEN long_confidence * long_history_weight ELSE 0 END
        ) AS weighted_confidence_numerator,

        (
            CASE WHEN current_session_score IS NOT NULL AND current_confidence IS NOT NULL
                 THEN current_weight ELSE 0 END
          + CASE WHEN short_history_score IS NOT NULL AND short_confidence IS NOT NULL
                 THEN short_history_weight ELSE 0 END
          + CASE WHEN long_history_score IS NOT NULL AND long_confidence IS NOT NULL
                 THEN long_history_weight ELSE 0 END
        ) AS confidence_weight
    FROM history h
)
SELECT
    dimension_id,
    dimension_name,
    duration_code,
    current_session_score,
    short_history_score,
    long_history_score,
    current_weight,
    short_history_weight,
    long_history_weight,
    ROUND(weighted_score_numerator / NULLIF(available_weight, 0), 2) AS final_score,
    ROUND(weighted_confidence_numerator / NULLIF(confidence_weight, 0), 4) AS confidence
FROM weighted
WHERE available_weight > 0
ORDER BY dimension_id;
$$;

CREATE OR REPLACE PROCEDURE refresh_soul_score_snapshot(
    p_user_id UUID,
    p_as_of_session_id UUID
)
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO user_soul_score_snapshot (
        user_id,
        dimension_id,
        as_of_session_id,
        current_session_score,
        short_history_score,
        long_history_score,
        current_weight,
        short_history_weight,
        long_history_weight,
        final_score,
        confidence,
        duration_code,
        calculation_version,
        calculated_at
    )
    SELECT
        p_user_id,
        x.dimension_id,
        p_as_of_session_id,
        x.current_session_score,
        x.short_history_score,
        x.long_history_score,
        x.current_weight,
        x.short_history_weight,
        x.long_history_weight,
        x.final_score,
        x.confidence,
        x.duration_code,
        '1.0',
        now()
    FROM compute_soul_score(p_user_id, p_as_of_session_id) x
    ON CONFLICT (user_id, dimension_id, as_of_session_id)
    DO UPDATE SET
        current_session_score = EXCLUDED.current_session_score,
        short_history_score = EXCLUDED.short_history_score,
        long_history_score = EXCLUDED.long_history_score,
        current_weight = EXCLUDED.current_weight,
        short_history_weight = EXCLUDED.short_history_weight,
        long_history_weight = EXCLUDED.long_history_weight,
        final_score = EXCLUDED.final_score,
        confidence = EXCLUDED.confidence,
        duration_code = EXCLUDED.duration_code,
        calculation_version = EXCLUDED.calculation_version,
        calculated_at = now();
END;
$$;

-- Latest score for every user/dimension.
CREATE OR REPLACE VIEW v_latest_user_soul_score AS
SELECT DISTINCT ON (s.user_id, s.dimension_id)
    s.user_id,
    s.dimension_id,
    d.dimension_name,
    s.final_score,
    s.confidence,
    s.current_session_score,
    s.short_history_score,
    s.long_history_score,
    s.current_weight,
    s.short_history_weight,
    s.long_history_weight,
    s.duration_code,
    s.as_of_session_id,
    s.calculated_at
FROM user_soul_score_snapshot s
JOIN wellbeing_dimension d
  ON d.dimension_id = s.dimension_id
ORDER BY s.user_id, s.dimension_id, s.calculated_at DESC;

-- Dashboard only: dimensions currently active for the user.
CREATE OR REPLACE VIEW v_user_dashboard_soul_score AS
SELECT
    st.user_id,
    st.dashboard_rank,
    st.priority_score,
    ls.dimension_id,
    ls.dimension_name,
    ls.final_score,
    ls.confidence,
    ls.current_session_score,
    ls.short_history_score,
    ls.long_history_score,
    ls.duration_code,
    ls.calculated_at
FROM user_dimension_state st
JOIN v_latest_user_soul_score ls
  ON ls.user_id = st.user_id
 AND ls.dimension_id = st.dimension_id
WHERE st.visibility_state = 'active'
ORDER BY st.user_id, st.dashboard_rank;

-- ============================================================================
-- 10. HEADER / MASTER DATA
-- ============================================================================

INSERT INTO soul_score_config (
    config_id,
    methodology_version,
    score_min,
    score_max,
    short_term_days,
    long_term_days,
    default_dashboard_dimensions
)
VALUES (1, '1.0', 0, 100, 28, 365, 8)
ON CONFLICT (config_id) DO UPDATE SET
    methodology_version = EXCLUDED.methodology_version,
    score_min = EXCLUDED.score_min,
    score_max = EXCLUDED.score_max,
    short_term_days = EXCLUDED.short_term_days,
    long_term_days = EXCLUDED.long_term_days,
    default_dashboard_dimensions = EXCLUDED.default_dashboard_dimensions,
    updated_at = now();

-- Weight policy implements the requested rule exactly:
-- lower Duration -> CURRENT low, SHORT HISTORY medium, LONG HISTORY high
-- higher Duration -> CURRENT high, SHORT HISTORY medium, LONG HISTORY low
-- "Short–Long" is treated as balanced because it spans both ends.
INSERT INTO soul_score_duration_policy (
    duration_code,
    sort_order,
    current_weight,
    short_history_weight,
    long_history_weight,
    description
)
VALUES
    ('Short',         1, 0.10, 0.30, 0.60, 'Low duration: favour long-term history; current session has low weight'),
    ('Short–Medium',  2, 0.20, 0.30, 0.50, 'Short-to-medium duration'),
    ('Medium',        3, 0.33, 0.34, 0.33, 'Balanced duration'),
    ('Medium–Long',   4, 0.50, 0.30, 0.20, 'Medium-to-long duration'),
    ('Long',          5, 0.60, 0.30, 0.10, 'High duration: favour current session; long-term history has low weight'),
    ('Short–Long',    6, 0.33, 0.34, 0.33, 'Broad duration range: balanced weighting')
ON CONFLICT (duration_code) DO UPDATE SET
    sort_order = EXCLUDED.sort_order,
    current_weight = EXCLUDED.current_weight,
    short_history_weight = EXCLUDED.short_history_weight,
    long_history_weight = EXCLUDED.long_history_weight,
    description = EXCLUDED.description;

INSERT INTO summary_period_type (period_type, sort_order, description)
VALUES
    ('weekly',    1, 'Weekly user summary'),
    ('monthly',   2, 'Monthly user summary'),
    ('quarterly', 3, 'Quarterly user summary'),
    ('yearly',    4, 'Yearly user summary')
ON CONFLICT (period_type) DO UPDATE SET
    sort_order = EXCLUDED.sort_order,
    description = EXCLUDED.description;

INSERT INTO music_reaction_scale (rating, code, label, description)
VALUES
    (1, 'hated',       'Hated',                    'Strong negative reaction'),
    (2, 'disliked',    'Disliked',                 'Did not like the recommendation'),
    (3, 'neutral',     'Neutral / Okay',           'Neither liked nor disliked'),
    (4, 'liked',       'Liked',                    'Positive reaction'),
    (5, 'super_liked', 'Super-liked / Played along', 'Strong positive reaction; may have played or sung along')
ON CONFLICT (rating) DO UPDATE SET
    code = EXCLUDED.code,
    label = EXCLUDED.label,
    description = EXCLUDED.description;

-- 32 Soul Score dimensions from the supplied SoulScoreDimensions workbook.
-- default_dashboard_rank follows the eight foundational dimensions in the methodology:
-- Calmness, Energy, Focus, Motivation, Connection, Self-Belief, Purpose, Joy.
INSERT INTO wellbeing_dimension (
    dimension_id,
    dimension_name,
    negative_dimension,
    duration_code,
    is_primary,
    default_dashboard_rank,
    research_basis
)
VALUES
    ( 1, 'Relaxedness',             'Tension',                               'Short',        FALSE, NULL, 'BRECVEMA; Koelsch; WHO'),
    ( 2, 'Energy',                  'Tiredness / fatigue',                   'Short',        TRUE,     2, 'Saarikallio & Erkkilä; BRECVEMA; Koelsch'),
    ( 3, 'Focus',                   'Distractibility',                       'Short',        TRUE,     3, 'BRECVEMA; Koelsch; WHO'),
    ( 4, 'Positive Mood',           'Low mood',                              'Short',        FALSE, NULL, 'Saarikallio & Erkkilä; BRECVEMA; Koelsch; Cochrane'),
    ( 5, 'Emotional Release',       'Emotional buildup',                     'Short',        FALSE, NULL, 'Saarikallio & Erkkilä; Cochrane'),
    ( 6, 'Joy',                     'Sadness',                               'Short',        TRUE,     8, 'Saarikallio & Erkkilä; BRECVEMA; Koelsch'),
    ( 7, 'Pleasure / Enjoyment',    'Anhedonia / lack of enjoyment',         'Short',        FALSE, NULL, 'Koelsch; BRECVEMA; Cochrane'),
    ( 8, 'Restfulness',             'Restlessness',                          'Short',        FALSE, NULL, 'BRECVEMA; Koelsch; WHO'),
    ( 9, 'Sleep Readiness',         'Alertness when rest is needed',         'Short',        FALSE, NULL, 'BRECVEMA; Koelsch; WHO'),
    (10, 'Calmness',                'Stress / anxiety',                      'Short–Medium', TRUE,     1, 'Saarikallio & Erkkilä; BRECVEMA; WHO; Koelsch; Cochrane'),
    (11, 'Motivation',              'Apathy / low drive',                    'Short–Medium', TRUE,     4, 'Saarikallio & Erkkilä; Koelsch; Cochrane'),
    (12, 'Emotional Balance',       'Mood instability',                      'Short–Medium', FALSE, NULL, 'Saarikallio & Erkkilä; WHO; Cochrane'),
    (13, 'Sense of Support',        'Feeling unsupported',                   'Short–Medium', FALSE, NULL, 'Saarikallio & Erkkilä; WHO; Cochrane'),
    (14, 'Emotional Expression',    'Suppression',                           'Short–Medium', FALSE, NULL, 'Saarikallio & Erkkilä; Cochrane'),
    (15, 'Creativity',              'Creative block',                        'Short–Medium', FALSE, NULL, 'BRECVEMA; Koelsch; WHO'),
    (16, 'Inspiration',             'Dullness / stagnation',                 'Short–Medium', FALSE, NULL, 'BRECVEMA; Saarikallio & Erkkilä'),
    (17, 'Engagement',              'Disengagement',                         'Short–Medium', FALSE, NULL, 'WHO; Koelsch; Cochrane'),
    (18, 'Confidence',              'Insecurity',                            'Medium',       FALSE, NULL, 'WHO; Cochrane'),
    (19, 'Recovery',                'Burnout / depletion',                   'Medium',       FALSE, NULL, 'WHO; Cochrane; Koelsch'),
    (20, 'Social Openness',         'Withdrawal',                            'Medium',       FALSE, NULL, 'WHO; Koelsch; Cochrane'),
    (21, 'Hopefulness',             'Hopelessness',                          'Medium–Long',  FALSE, NULL, 'WHO; Cochrane; Saarikallio & Erkkilä'),
    (22, 'Resilience',              'Fragility / overwhelm',                 'Medium–Long',  FALSE, NULL, 'WHO; Cochrane'),
    (23, 'Self-Belief',             'Self-doubt',                            'Medium–Long',  TRUE,     6, 'WHO; Cochrane'),
    (24, 'Connection',              'Loneliness',                            'Medium–Long',  TRUE,     5, 'WHO; Koelsch; Saarikallio & Erkkilä'),
    (25, 'Belonging',               'Isolation',                             'Medium–Long',  FALSE, NULL, 'WHO; Koelsch'),
    (26, 'Self-Reflection',         'Avoidance / lack of insight',           'Medium–Long',  FALSE, NULL, 'Saarikallio & Erkkilä; BRECVEMA; Koelsch'),
    (27, 'Self-Awareness',          'Emotional confusion',                   'Medium–Long',  FALSE, NULL, 'Saarikallio & Erkkilä; Koelsch'),
    (28, 'Consistency',             'Irregularity',                          'Medium–Long',  FALSE, NULL, 'WHO'),
    (29, 'Healthy Routine',         'Poor habits',                           'Medium–Long',  FALSE, NULL, 'WHO'),
    (30, 'Purpose',                 'Aimlessness',                           'Long',         TRUE,     7, 'WHO; Saarikallio & Erkkilä'),
    (31, 'Meaningfulness',          'Emptiness',                             'Long',         FALSE, NULL, 'WHO; Saarikallio & Erkkilä'),
    (32, 'Aesthetic Appreciation',  'Emotional numbness / lack of wonder',   'Short–Long',   FALSE, NULL, 'BRECVEMA; Koelsch; WHO')
ON CONFLICT (dimension_id) DO UPDATE SET
    dimension_name = EXCLUDED.dimension_name,
    negative_dimension = EXCLUDED.negative_dimension,
    duration_code = EXCLUDED.duration_code,
    is_primary = EXCLUDED.is_primary,
    default_dashboard_rank = EXCLUDED.default_dashboard_rank,
    research_basis = EXCLUDED.research_basis,
    is_enabled = TRUE;

-- Backfill dimension state for users that existed before this schema/seed was run.
INSERT INTO user_dimension_state (
    user_id,
    dimension_id,
    visibility_state,
    dashboard_rank,
    priority_score,
    activation_reason,
    activated_at
)
SELECT
    u.user_id,
    d.dimension_id,
    CASE WHEN d.is_primary THEN 'active' ELSE 'hidden' END,
    d.default_dashboard_rank,
    CASE WHEN d.is_primary THEN 100 ELSE 0 END,
    CASE WHEN d.is_primary THEN 'Primary foundational Soul dimension' ELSE NULL END,
    CASE WHEN d.is_primary THEN now() ELSE NULL END
FROM app_user u
CROSS JOIN wellbeing_dimension d
WHERE d.is_enabled = TRUE
ON CONFLICT (user_id, dimension_id) DO NOTHING;

COMMIT;

-- ============================================================================
-- EXAMPLE EXECUTION AT THE END OF A SESSION
-- ============================================================================
--
-- 1. Insert/update conversation_dimension_score rows as each conversation is assessed.
--
-- 2. Aggregate conversation scores into a current-session score:
--      CALL reddust.refresh_session_dimension_scores('<session-uuid>');
--
-- 3. Compute/persist dashboard Soul Scores:
--      CALL reddust.refresh_soul_score_snapshot('<user-uuid>', '<session-uuid>');
--
-- 4. Dashboard query:
--      SELECT *
--      FROM reddust.v_user_dashboard_soul_score
--      WHERE user_id = '<user-uuid>'
--      ORDER BY dashboard_rank;
--
-- ============================================================================
