from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"

    class Config:
        env_file = ".env"


settings = Settings()   # type: ignore
