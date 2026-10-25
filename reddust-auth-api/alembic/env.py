"""Alembic runtime - online migrations only for this local runbook."""
from alembic import context
from sqlalchemy import create_engine, pool

from app.db import database_url
from app.models import metadata

config = context.config
target_metadata = metadata


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                include_schemas=False,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()

if context.is_offline_mode():
    raise RuntimeError("Offline mode is disabled in this learning runbook")
else:
    run_migrations_online()