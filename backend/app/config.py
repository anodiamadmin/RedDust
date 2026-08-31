# config.py — Centralised configuration management
# Uses pydantic-settings to load environment variables from the .env file.
# If a required variable (like GEMINI_API_KEY) is missing at startup,
# the app crashes immediately with a clear error — this is intentional (fail-fast pattern).
# Never hardcode secrets in source code; always load from environment.

from pydantic_settings import BaseSettings
import logging
from pydantic import model_validator


class Settings(BaseSettings):
    # Required: must be set in .env — app will not start without this
    GEMINI_API_KEY: str

    # Optional: defaults to gemini-3.5-flash-lite if not set in .env
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_DB_URL: str  # PostgreSQL connection string for asyncpg/vecs

    # YouTube Data API v3
    # Get your key at: https://console.cloud.google.com → APIs & Services → YouTube Data API v3
    # Free tier: 10,000 units/day. Each recommendation costs ~101 units (100 search + 1 video).
    YOUTUBE_API_KEY: str = ""

    # YouTube search region — filters results to be relevant/playable in this region.
    # Uses ISO 3166-1 alpha-2 country codes. Default: IN (India).
    YOUTUBE_REGION_CODE: str = "IN"

    # YouTube search language hint — biases results toward this language.
    # Uses BCP-47 language codes. Default: "en" (English).
    # Change to "hi" for Hindi-first results, or leave as "en" for mixed.
    YOUTUBE_LANGUAGE: str = "en"

    @model_validator(mode='after')
    def check_critical_keys(self) -> 'Settings':
        """Warn at startup if required external API keys are missing."""
        if not self.YOUTUBE_API_KEY:
            logging.warning(
                "YOUTUBE_API_KEY is not set — YouTube track search will fail with 403. "
                "Add it to your .env file."
            )
        return self

    class Config:
        # Tells pydantic-settings to read from .env file in addition to real env vars
        env_file = ".env"

# Singleton settings instance — imported across the app wherever config is needed
settings = Settings()   # type: ignore
