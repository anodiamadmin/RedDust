# scripts/test_preference_extractor.py — Unit test for preference_extractor.py
#
# Run from: Windows PowerShell
# Command:  python -m scripts.test_preference_extractor
#
# Prerequisites:
#   - venv_windows activated
#   - .env has GEMINI_API_KEY, SUPABASE_DB_URL
#   - DB has reddust schema deployed (migration_001 + migration_002)

import asyncio
import uuid
from datetime import datetime, timezone

import asyncpg

from app.config import settings
from app.db.pool import create_pool
from app.services.preference_extractor import extract_preferences_from_turn

# ── Test turns ────────────────────────────────────────────────────────────────
# Turn 1: explicit strong preferences — should extract 2 items
TURN_EXPLICIT = "I really love AR Rahman and I absolutely hate loud EDM music."

# Turn 2: hypothetical — should extract 0 items
TURN_HYPOTHETICAL = "What if someone liked jazz? I think maybe classical could be nice."

# Turn 3: vague — should extract 0 items
TURN_VAGUE = "I like music a lot. Music is great."

# Turn 4: decade + language preference — should extract 2 items
TURN_DECADE_LANG = "I always listen to 90s Bollywood. I never listen to English songs."


async def main():
    pool = await create_pool()
    passed = 0
    failed = 0

    # ── Seed fake user/session/conversation/turn ──────────────────────────────
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    async with pool.acquire() as conn:
        # Insert app_user
        await conn.execute(
            """
            INSERT INTO reddust.app_user (user_id, display_name, created_at, updated_at)
            VALUES ($1, 'Test User', now(), now())
            """,
            user_id,
        )

        # Insert user_session
        await conn.execute(
            """
            INSERT INTO reddust.user_session (session_id, user_id, started_at, created_at)
            VALUES ($1, $2, now(), now())
            """,
            session_id, user_id,
        )

        # Insert conversation
        await conn.execute(
            """
            INSERT INTO reddust.conversation (conversation_id, session_id, sequence_no, started_at, created_at)
            VALUES ($1, $2, 1, now(), now())
            """,
            conversation_id, session_id,
        )

        # Insert a conversation_turn (needed for FK in preference_extraction_log)
        turn_id = await conn.fetchval(
            """
            INSERT INTO reddust.conversation_turn
                (conversation_id, turn_no, speaker, transcript_text, created_at)
            VALUES ($1, 1, 'user', $2, now())
            RETURNING turn_id
            """,
            conversation_id, TURN_EXPLICIT,
        )

    print(f"\nSeeded: user={user_id}, session={session_id}, conversation={conversation_id}, turn_id={turn_id}")

    # ── Test 1: Explicit preferences ──────────────────────────────────────────
    print("\n[TEST 1] Explicit preferences — expect >= 2 extractions")
    await extract_preferences_from_turn(
        turn_text=TURN_EXPLICIT,
        user_id=user_id,
        session_id=session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        pool=pool,
    )
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM reddust.preference_extraction_log WHERE user_id=$1",
            user_id,
        )
    if count >= 2:
        print(f"  PASS — {count} rows in preference_extraction_log")
        passed += 1
    else:
        print(f"  FAIL — expected >= 2 rows, got {count}")
        failed += 1

    # ── Test 2: user_music_preference populated ───────────────────────────────
    print("\n[TEST 2] user_music_preference upserted — expect >= 1 row")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT preference_type, preference_value, confidence FROM reddust.user_music_preference WHERE user_id=$1",
            user_id,
        )
    if len(rows) >= 1:
        print(f"  PASS — {len(rows)} row(s):")
        for r in rows:
            print(f"    {r['preference_type']} = {r['preference_value']} (confidence={r['confidence']})")
        passed += 1
    else:
        print(f"  FAIL — expected >= 1 row in user_music_preference, got {len(rows)}")
        failed += 1

    # ── Test 3: Hypothetical — should extract nothing ─────────────────────────
    print("\n[TEST 3] Hypothetical turn — expect 0 new extractions")
    count_before = await pool.fetchval(
        "SELECT COUNT(*) FROM reddust.preference_extraction_log WHERE user_id=$1", user_id
    )
    await extract_preferences_from_turn(
        turn_text=TURN_HYPOTHETICAL,
        user_id=user_id,
        session_id=session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        pool=pool,
    )
    count_after = await pool.fetchval(
        "SELECT COUNT(*) FROM reddust.preference_extraction_log WHERE user_id=$1", user_id
    )
    if count_after == count_before:
        print(f"  PASS — no new rows extracted")
        passed += 1
    else:
        print(f"  FAIL — extracted {count_after - count_before} rows from hypothetical turn")
        failed += 1

    # ── Test 4: Decade + language ─────────────────────────────────────────────
    print("\n[TEST 4] Decade + language turn — expect >= 2 extractions")
    count_before = await pool.fetchval(
        "SELECT COUNT(*) FROM reddust.preference_extraction_log WHERE user_id=$1", user_id
    )
    await extract_preferences_from_turn(
        turn_text=TURN_DECADE_LANG,
        user_id=user_id,
        session_id=session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        pool=pool,
    )
    count_after = await pool.fetchval(
        "SELECT COUNT(*) FROM reddust.preference_extraction_log WHERE user_id=$1", user_id
    )
    new_extractions = count_after - count_before
    if new_extractions >= 2:
        print(f"  PASS — {new_extractions} new extractions")
        passed += 1
    else:
        print(f"  FAIL — expected >= 2, got {new_extractions}")
        failed += 1

    # ── Cleanup ───────────────────────────────────────────────────────────────
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM reddust.app_user WHERE user_id=$1", user_id)
    print("\nCleaned up test data.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n[{passed + failed}] {passed} PASSED, {failed} FAILED")
    if failed == 0:
        print("ALL TESTS PASSED")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())