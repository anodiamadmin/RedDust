"""Local connection configuration; never commit .env.local."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local", override=False)


def database_url() -> URL:
    names = ("RD_DB_HOST", "RD_DB_PORT", "RD_DB_NAME",
             "RD_DB_USER", "RD_DB_PASSWORD")
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing database settings: " + ", ".join(missing))
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["RD_DB_USER"],
        password=os.environ["RD_DB_PASSWORD"],
        host=os.environ["RD_DB_HOST"],
        port=int(os.environ["RD_DB_PORT"]),
        database=os.environ["RD_DB_NAME"],
    )
