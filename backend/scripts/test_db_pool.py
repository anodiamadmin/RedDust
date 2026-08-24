r"""
scripts/test_db_pool.py — Manual test for asyncpg pool + Supabase connectivity

Run from the backend/ directory (Windows PowerShell, venv_windows):
    cd D:\Anodiam\2026\RedDust_Parent\RedDust\backend
    venv_windows\Scripts\Activate.ps1
    python -m scripts.test_db_pool

What this tests:
    1. Pool creates successfully using SUPABASE_DB_URL from .env
    2. search_path is set to reddust (can query reddust tables without prefix)
    3. All expected reddust tables exist in the DB (30 original + 3 from migration_002)
    4. Pool closes cleanly
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.pool import create_pool

# All tables that should exist after migration_001 + migration_002
EXPECTED_TABLES = sorted([
    # migration_001
    "app_user", "audio_features", "conversation", "conversation_dimension_score",
    "conversation_summary", "conversation_turn", "music_artist", "music_genre",
    "music_interaction_event", "music_language", "music_reaction_scale",
    "music_recommendation", "music_recommendation_dimension",
    "music_recommendation_reaction", "music_track", "music_track_artist",
    "music_track_genre", "music_track_language", "session_dimension_score",
    "session_summary", "soul_score_config", "soul_score_duration_policy",
    "summary_period_type", "user_dimension_state", "user_dimension_state_event",
    "user_period_summary", "user_session", "user_soul_score_snapshot",
    "wellbeing_dimension", "wellbeing_signal",
    # migration_002
    "user_music_preference", "preference_extraction_log", "transcript_segment",
])


async def main():
    # -----------------------------------------------------------------------
    # [1] Create pool
    # -----------------------------------------------------------------------
    try:
        pool = await create_pool()
    except Exception as e:
        print(f"[FAIL] Pool creation failed: {e}")
        sys.exit(1)

    print("[1] Pool created successfully")

    async with pool.acquire() as conn:
        # -------------------------------------------------------------------
        # [2] Confirm search_path is set to reddust
        # -------------------------------------------------------------------
        search_path = await conn.fetchval("SHOW search_path")
        if "reddust" not in search_path:
            print(f"[FAIL] search_path does not include reddust: {search_path}")
            await pool.close()
            sys.exit(1)

        print(f"[2] search_path confirmed: {search_path}")

        # -------------------------------------------------------------------
        # [3] Check all expected tables exist
        # -------------------------------------------------------------------
        rows = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'reddust'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        found = sorted([r["table_name"] for r in rows])
        missing = [t for t in EXPECTED_TABLES if t not in found]

        print(f"[3] Tables found in reddust schema ({len(found)}):")
        for t in found:
            print(f"    {t}")

        if missing:
            print(f"[FAIL] Missing tables: {missing}")
            await pool.close()
            sys.exit(1)

    # -----------------------------------------------------------------------
    # [4] Close pool
    # -----------------------------------------------------------------------
    await pool.close()
    print("[4] Pool closed cleanly")
    print("[5] ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
