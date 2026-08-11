# config.py — Centralised configuration management
# Uses pydantic-settings to load environment variables from the .env file.
# If a required variable (like GEMINI_API_KEY) is missing at startup,
# the app crashes immediately with a clear error — this is intentional (fail-fast pattern).
# Never hardcode secrets in source code; always load from environment.

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required: must be set in .env — app will not start without this
    GEMINI_API_KEY: str
    YOUTUBE_API_KEY: str = ""

    # Optional: defaults to gemini-3.5-flash-lite if not set in .env
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_DB_URL: str  # PostgreSQL connection string for asyncpg/vecs

    class Config:
        # Tells pydantic-settings to read from .env file in addition to real env vars
        env_file = ".env"


# Singleton settings instance — imported across the app wherever config is needed
settings = Settings()   # type: ignore
