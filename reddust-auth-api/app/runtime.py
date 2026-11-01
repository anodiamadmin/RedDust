"""Local Auth API database engine; uses the existing app.db.database_url()."""
from functools import lru_cache
import os
from sqlalchemy import Engine, create_engine
from app.db import database_url

@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = database_url()
    if os.getenv("RD_RUNTIME_ENV", "local") == "local" and url.database != "reddust_dev":
        raise RuntimeError("Local Auth API must use reddust_dev; not a test database")
    return create_engine(url, pool_pre_ping=True)