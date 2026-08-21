# db/pool.py — asyncpg connection pool
#
# Responsibility:
#   Create and manage a PostgreSQL connection pool using asyncpg.
#   The pool is created once at FastAPI startup and closed at shutdown.
#   All parts of the app access it via app.state.pool — never create
#   their own connections directly.
#
# Why a pool?
#   Creating a new DB connection per request is expensive (~50–100ms).
#   A pool keeps N connections open and reuses them, making DB access fast.
#
# Why asyncpg?
#   It's the fastest async PostgreSQL driver for Python. Fully compatible
#   with FastAPI's async request handlers.
#
# Why app.state?
#   FastAPI's app.state is a simple namespace for storing app-wide singletons.
#   It's the idiomatic way to share a connection pool across routes and services
#   without using global variables.
#
# Schema:
#   All RedDust tables live in the 'reddust' schema. We set search_path on
#   pool creation so every connection defaults to that schema — no need to
#   prefix every query with reddust.*

import asyncpg
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def create_pool() -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool.

    Pool is configured to:
      - Use the reddust schema as default search_path
      - Keep minimum 2 connections open (avoids cold-start latency)
      - Allow up to 10 concurrent connections (sufficient for MVP load)
      - Timeout after 30s if no connection is available

    Returns:
        asyncpg.Pool: the open connection pool

    Raises:
        Exception: if the database is unreachable at startup (intentional fail-fast)
    """
    logger.info("db.pool: creating asyncpg connection pool...")

    pool = await asyncpg.create_pool(
        dsn=settings.SUPABASE_DB_URL,

        # Keep at least 2 connections warm at all times
        min_size=2,

        # Maximum concurrent connections — raise this as user load grows
        max_size=10,

        # If all connections are busy, wait up to 30s before raising an error
        command_timeout=30,

        # Set search_path to reddust on every new connection so queries
        # don't need to be prefixed with reddust.*
        init=_set_search_path,
    )

    logger.info("db.pool: pool created successfully (min=2, max=10)")
    return pool


async def _set_search_path(connection: asyncpg.Connection) -> None:
    """
    Called by asyncpg on every new connection in the pool.
    Sets the PostgreSQL search_path to reddust, public so that:
      - reddust.* tables are accessible without schema prefix
      - public.* extensions (like pgvector, pgcrypto) remain accessible
    """
    await connection.execute("SET search_path TO reddust, public")
