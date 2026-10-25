"""RedDust 19C baseline: SQLAlchemy Core schema for Alembic."""
from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, MetaData, Table, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData(naming_convention={
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(column_0_label)s",
})

app_users = Table(
    "app_users", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("display_name", Text),
    Column("status", Text, nullable=False, server_default="active"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    CheckConstraint("status IN ('active','disabled','deleted')", name="valid_status"),
)

external_identities = Table(
    "external_identities", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False),
    Column("provider", Text, nullable=False),
    Column("provider_subject", Text, nullable=False),
    Column("email_at_verification", Text),
    Column("verified_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("provider IN ('google')", name="valid_provider"),
    UniqueConstraint("provider", "provider_subject", name="uq_external_identity_provider_subject"),
)

client_devices = Table(
    "client_devices", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False),
    Column("installation_id", Text, nullable=False),
    Column("platform", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("platform IN ('android','ios')", name="valid_platform"),
    UniqueConstraint("user_id", "installation_id", name="uq_device_user_installation"),
    UniqueConstraint("id", "user_id", name="uq_device_id_user"),
)

auth_sessions = Table(
    "auth_sessions", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False),
    Column("device_id", UUID(as_uuid=True)),
    Column("refresh_token_hash", Text, nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("id", "user_id", name="uq_auth_session_id_user"),
    ForeignKeyConstraint(
        ["device_id", "user_id"],
        ["client_devices.id", "client_devices.user_id"],
        name="fk_auth_device_same_user", ondelete="RESTRICT",
    ),
)

call_sessions = Table(
    "call_sessions", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False),
    Column("auth_session_id", UUID(as_uuid=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("ended_at", DateTime(timezone=True)),
    Column("end_reason", Text),
    CheckConstraint("status IN ('starting','active','ended','failed')", name="valid_status"),
    ForeignKeyConstraint(
        ["auth_session_id", "user_id"],
        ["auth_sessions.id", "auth_sessions.user_id"],
        name="fk_call_auth_same_user", ondelete="RESTRICT",
    ),
)

audit_events = Table(
    "audit_events", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("actor_user_id", UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL")),
    Column("auth_session_id", UUID(as_uuid=True), ForeignKey("auth_sessions.id", ondelete="SET NULL")),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("request_id", Text),
    Column("metadata_json", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("jsonb_typeof(metadata_json) = 'object'", name="metadata_is_object"),
    CheckConstraint("octet_length(metadata_json::text) <= 4096", name="metadata_size_limit"),
)

user_preferences = Table(
    "user_preferences", metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True),
    Column("preferred_persona", Text),
    Column("speaker_default", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

Index("ix_external_identities_user", external_identities.c.user_id)
Index("ix_client_devices_user", client_devices.c.user_id)
Index("ix_auth_sessions_user_created", auth_sessions.c.user_id, auth_sessions.c.created_at.desc())
Index("ix_calls_user_started", call_sessions.c.user_id, call_sessions.c.started_at.desc())
Index("ix_audit_events_occurred", audit_events.c.occurred_at.desc())
Index("ix_audit_events_actor_occurred", audit_events.c.actor_user_id, audit_events.c.occurred_at.desc())
Index("ix_audit_events_request_id", audit_events.c.request_id)