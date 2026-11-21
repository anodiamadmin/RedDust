# main.py — Application entry point
#
# FastAPI is instantiated here with a lifespan context manager that:
#   - Creates the asyncpg connection pool on startup
#   - Attaches it to app.state.pool (accessible everywhere via request.app.state.pool)
#   - Closes the pool cleanly on shutdown
#
# uvicorn entry point: `uvicorn app.main:app`

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.db.pool import create_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler.

    Everything before `yield` runs at startup.
    Everything after `yield` runs at shutdown.

    We use this instead of @app.on_event("startup") because lifespan is
    the modern FastAPI pattern (on_event is deprecated in FastAPI 0.93+).
    """
    # -----------------------------------------------------------------------
    # STARTUP
    # -----------------------------------------------------------------------
    logger.info("startup: initialising database pool...")
    app.state.pool = await create_pool()
    logger.info("startup: database pool ready")

    yield  # App is now running and handling requests

    # -----------------------------------------------------------------------
    # SHUTDOWN
    # -----------------------------------------------------------------------
    logger.info("shutdown: closing database pool...")
    await app.state.pool.close()
    logger.info("shutdown: database pool closed")


# Instantiate FastAPI with the lifespan handler
app = FastAPI(title="RedDust API", lifespan=lifespan)

# Mount the chat router under the /api prefix
app.include_router(chat_router, prefix="/api")


# Basic health-check route — useful for load balancers and uptime monitors
@app.get("/")
async def root():
    return {"message": "RedDust backend running"}
