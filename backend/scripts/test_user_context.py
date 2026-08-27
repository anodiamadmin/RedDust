# scripts/test_user_context.py — Integration test for handle_fetch_user_context()
#
# Purpose:
#   Verifies that fetch_user_context() correctly queries all 4 data sources
#   (profile, preferences, soul scores, recent sessions) for a given user.
#
# What this tests:
#   1. asyncpg pool connects and uses reddust search_path correctly
#   2. app_user query returns display_name and timezone (or None for new users)
#   3. user_music_preference query returns rows (if seeded) or empty list
#   4. v_user_dashboard_soul_score view is accessible and returns rows (if seeded)
#   5. conversation + user_session join returns recent summaries (if seeded)
#   6. No crash on new/empty users — context still returns with empty lists
#
# How to run (Windows PowerShell from backend/ directory):
#   python -m scripts.test_user_context
#
# Expected output:
#   - "Pool created" message
#   - Pretty-printed context dict with keys:
#       display_name, timezone, preferences, soul_scores, recent_sessions
#   - For a real user: preferences and soul_scores populated
#   - For a new/unknown user: all lists empty, display_name = None
#   - "Pool closed" at the end — no hanging connections
#
# Possible errors:
#   - asyncpg.exceptions.InvalidPasswordError  → wrong SUPABASE_DB_URL in .env
#   - asyncpg.exceptions.UndefinedTableError   → schema not deployed; re-run migration_001
#   - asyncpg.exceptions.UndefinedColumnError  → view column mismatch; check v_user_dashboard_soul_score
#   - "error" key in returned dict             → partial context; check logs for the real exception
#   - OSError / errno 101                      → running from WSL; use Windows PowerShell instead

import asyncio
import json
import sys
from uuid import UUID

# ---------------------------------------------------------------------------
# Path fix: makes sure `app` package is importable when running as a script
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.pool import create_pool
from app.services.functions.user_context import handle_fetch_user_context


# ---------------------------------------------------------------------------
# TEST USER — change this to a real user_id from your app_user table,
# or leave as-is to test the empty/new-user path (all lists will be empty).
# ---------------------------------------------------------------------------
# To find a real user_id: run this in Supabase SQL Editor:
#   SELECT user_id, display_name FROM reddust.app_user LIMIT 5;
TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")  # replace with real UUID if available


async def main():
    print("=" * 60)
    print("TEST: handle_fetch_user_context()")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Create pool — same as app startup
    # ------------------------------------------------------------------
    pool = await create_pool()
    print("[OK] Pool created\n")

    try:
        # ------------------------------------------------------------------
        # 2. Call the handler directly (no Gemini Live involved)
        # ------------------------------------------------------------------
        print(f"Fetching context for user_id: {TEST_USER_ID}\n")
        context = await handle_fetch_user_context(pool=pool, user_id=TEST_USER_ID)

        # ------------------------------------------------------------------
        # 3. Pretty-print the full context dict
        # ------------------------------------------------------------------
        print("--- Returned context ---")
        print(json.dumps(context, indent=2, default=str))
        print()

        # ------------------------------------------------------------------
        # 4. Assertions — basic structural checks
        # ------------------------------------------------------------------
        assert "display_name" in context,    "FAIL: missing display_name key"
        assert "timezone" in context,        "FAIL: missing timezone key"
        assert "preferences" in context,     "FAIL: missing preferences key"
        assert "soul_scores" in context,     "FAIL: missing soul_scores key"
        assert "recent_sessions" in context, "FAIL: missing recent_sessions key"
        assert isinstance(context["preferences"],     list), "FAIL: preferences must be a list"
        assert isinstance(context["soul_scores"],     list), "FAIL: soul_scores must be a list"
        assert isinstance(context["recent_sessions"], list), "FAIL: recent_sessions must be a list"

        # Check for partial-error flag (should not be present on clean run)
        if "error" in context:
            print(f"[WARN] Partial context returned — DB error: {context['error']}")
            print("       Check logs above for the full traceback.")
        else:
            print("[OK] No errors in context")

        # Report what was found
        print(f"[INFO] display_name   : {context['display_name']}")
        print(f"[INFO] timezone       : {context['timezone']}")
        print(f"[INFO] preferences    : {len(context['preferences'])} rows")
        print(f"[INFO] soul_scores    : {len(context['soul_scores'])} rows")
        print(f"[INFO] recent_sessions: {len(context['recent_sessions'])} rows")

        print("\n[PASS] All structural checks passed")

    finally:
        # ------------------------------------------------------------------
        # 5. Always close the pool — prevents hanging connections
        # ------------------------------------------------------------------
        await pool.close()
        print("[OK] Pool closed")


if __name__ == "__main__":
    asyncio.run(main())
