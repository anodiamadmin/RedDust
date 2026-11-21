# scripts/test_dimension_scorer.py — Integration test for dimension_scorer.py
#
# Seeds a fake transcript showing anxiety + motivation, runs the scorer,
# then checks conversation_dimension_score and wellbeing_signal for expected rows.
#
# Run from backend/ directory (PowerShell, venv_windows):
#   python -m scripts.test_dimension_scorer
#
# Expected output:
#   [PASS] conversation_dimension_score has N rows
#   [PASS] Calmness or Anxiety Level scored < 50
#   [PASS] wellbeing_signal has at least 1 row
#   ALL TESTS PASSED

import asyncio
import uuid
from datetime import datetime, timezone

import asyncpg
from dotenv import load_dotenv

load_dotenv()

from app.config import settings
from app.services.dimension_scorer import score_conversation_dimensions


# ---------------------------------------------------------------------------
# Fake transcript — shows anxiety + motivation signals clearly
# ---------------------------------------------------------------------------
FAKE_TRANSCRIPT = [
    {"speaker": "user",  "text": "I haven't slept properly in days. I feel really overwhelmed and anxious about my exams."},
    {"speaker": "syan",  "text": "I'm sorry to hear that. It sounds like you're carrying a lot right now. Let's try to help you unwind."},
    {"speaker": "user",  "text": "Yeah, my mind won't stop racing. I feel like I'm drowning in everything."},
    {"speaker": "syan",  "text": "That's really hard. What if we start with some calming music to give your mind a break?"},
    {"speaker": "user",  "text": "That would actually help. I do want to get back on track — I just need to get through this week."},
    {"speaker": "syan",  "text": "You're already showing resilience just by pushing through. Let's start with something gentle."},
]


async def run_test():
    # Connect to Supabase via asyncpg
    pool = await asyncpg.create_pool(
        dsn=settings.SUPABASE_DB_URL,
        min_size=1,
        max_size=3,
        server_settings={"search_path": "reddust,public"},
    )

    try:
        async with pool.acquire() as conn:

            # ----------------------------------------------------------------
            # Seed a minimal user → session → conversation chain
            # (using fixed UUIDs so cleanup is easy)
            # ----------------------------------------------------------------
            user_id         = uuid.UUID("00000000-0000-0000-0000-000000000001")
            session_id      = uuid.UUID("00000000-0000-0000-0000-000000000002")
            conversation_id = uuid.UUID("00000000-0000-0000-0000-000000000003")

            # Clean up in FK-safe order: children first, parents last
            await conn.execute("DELETE FROM reddust.wellbeing_signal WHERE conversation_id = $1", conversation_id)
            await conn.execute("DELETE FROM reddust.conversation_dimension_score WHERE conversation_id = $1", conversation_id)
            await conn.execute("DELETE FROM reddust.transcript_segment WHERE conversation_id = $1", conversation_id)
            await conn.execute("DELETE FROM reddust.conversation WHERE conversation_id = $1", conversation_id)
            await conn.execute("DELETE FROM reddust.user_session WHERE session_id = $1", session_id)
            await conn.execute("DELETE FROM reddust.app_user WHERE user_id = $1", user_id)

            # Seed app_user — no email, no NOT NULL columns besides user_id
            await conn.execute("""
                INSERT INTO reddust.app_user (user_id, display_name, locale, timezone)
                VALUES ($1, 'Test User', 'en', 'Asia/Kolkata')
            """, user_id)
            print("Seeded app_user")

            # Seed user_session
            await conn.execute("""
                INSERT INTO reddust.user_session (session_id, user_id, started_at, status)
                VALUES ($1, $2, now(), 'active')
            """, session_id, user_id)
            print("Seeded user_session")

            # Seed conversation — no user_id column on this table
            await conn.execute("""
                INSERT INTO reddust.conversation (conversation_id, session_id, sequence_no, started_at)
                VALUES ($1, $2, 1, now())
            """, conversation_id, session_id)
            print("Seeded conversation")

            # Seed transcript_segment rows
            for idx, seg in enumerate(FAKE_TRANSCRIPT):
                await conn.execute("""
                    INSERT INTO reddust.transcript_segment
                        (session_id, conversation_id, segment_index, speaker, text)
                    VALUES ($1, $2, $3, $4, $5)
                """, session_id, conversation_id, idx, seg["speaker"], seg["text"])

            print("Seeded test data. Running dimension scorer...")

        # ----------------------------------------------------------------
        # Run the scorer
        # ----------------------------------------------------------------
        await score_conversation_dimensions(conversation_id, session_id, user_id, pool)

        # ----------------------------------------------------------------
        # Verify results
        # ----------------------------------------------------------------
        async with pool.acquire() as conn:

            # Check conversation_dimension_score has rows
            score_count = await conn.fetchval(
                "SELECT COUNT(*) FROM reddust.conversation_dimension_score WHERE conversation_id = $1",
                conversation_id,
            )
            assert score_count > 0, f"Expected >0 dimension scores, got {score_count}"
            print(f"[PASS] conversation_dimension_score has {score_count} rows")

            # Check that at least one anxiety-related dimension scored < 50
            # (Calmness or Anxiety Level should be low given the transcript)
            low_scores = await conn.fetch("""
                SELECT wd.dimension_name, cds.score
                FROM reddust.conversation_dimension_score cds
                JOIN reddust.wellbeing_dimension wd ON wd.dimension_id = cds.dimension_id
                WHERE cds.conversation_id = $1
                AND cds.score < 50
            """, conversation_id)

            # Temporary debug — add this before the low_scores assertion
            all_scores = await conn.fetch("""
                SELECT wd.dimension_name, cds.score, cds.confidence
                FROM reddust.conversation_dimension_score cds
                JOIN reddust.wellbeing_dimension wd ON wd.dimension_id = cds.dimension_id
                WHERE cds.conversation_id = $1
                ORDER BY cds.score ASC
            """, conversation_id)
            print("Scored dimensions:")
            for row in all_scores:
                print(f"  {row['dimension_name']}: {row['score']} (confidence={row['confidence']})")

            assert len(low_scores) > 0, (
                "Expected at least one dimension to score < 50 given the anxious transcript. "
                "Check Gemini output by adding print(raw) before json.loads."
            )
            for row in low_scores:
                print(f"[PASS] {row['dimension_name']} scored {row['score']:.1f} (< 50)")

            # Check wellbeing_signal has at least 1 row (high-confidence scores)
            signal_count = await conn.fetchval(
                "SELECT COUNT(*) FROM reddust.wellbeing_signal WHERE conversation_id = $1",
                conversation_id,
            )
            assert signal_count > 0, f"Expected >0 wellbeing_signal rows, got {signal_count}"
            print(f"[PASS] wellbeing_signal has {signal_count} rows")

            print("\nALL TESTS PASSED")

    finally:
        await pool.close()
        print("Pool closed.")


if __name__ == "__main__":
    asyncio.run(run_test())