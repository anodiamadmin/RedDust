"""J.5.7 teaching implementation: verified Google claims -> one RedDust user.

Only call with claims returned by app.security.verify_google_id_token.
The caller (Appendix K) supplies a cryptographically derived refresh_token_hash.
This module does NOT issue JWTs or verify Google's signature itself.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Any
from uuid import UUID

from sqlalchemy import Engine, Connection, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.models import (
    app_users, external_identities, client_devices, auth_sessions, audit_events,
)


class LoginDenied(Exception):
    """The verified identity is not authorized to start a RedDust session."""


class IdentityRaceRecoveryError(Exception):
    """A specific identity race occurred but the winning link was not found."""


@dataclass(frozen=True)
class LoginResult:
    user_id: UUID
    device_id: UUID
    auth_session_id: UUID
    created_user: bool
    recovered_identity_race: bool


def _lookup_identity(connection: Connection, subject: str):
    return connection.execute(
        select(external_identities.c["user_id"], app_users.c["status"])
        .join(app_users, external_identities.c["user_id"] == app_users.c["id"])
        .where(
            external_identities.c["provider"] == "google",
            external_identities.c["provider_subject"] == subject,
        )
    ).mappings().one_or_none()


def _is_identity_unique_conflict(error: IntegrityError) -> bool:
    original = error.orig
    return (
        getattr(original, "sqlstate", None) == "23505"
        and getattr(getattr(original, "diag", None), "constraint_name", None)
        == "uq_external_identity_provider_subject"
    )


def _register_device_session_and_audit(
    connection: Connection, user_id: UUID, installation_id: str,
    platform: str, refresh_token_hash: str, expires_at: datetime,
    request_id: str | None, outcome: str,
) -> tuple[UUID, UUID]:
    # The ON CONFLICT target is deliberately narrow: only same-user installation.
    candidate = pg_insert(client_devices).values(
        user_id=user_id, installation_id=installation_id, platform=platform
    ).on_conflict_do_nothing(
        constraint="uq_device_user_installation"
    ).returning(client_devices.c["id"])
    connection.execute(candidate).scalar_one_or_none()

    device = connection.execute(
        select(client_devices.c["id"], client_devices.c["platform"],
               client_devices.c["revoked_at"])
        .where(client_devices.c["user_id"] == user_id,
               client_devices.c["installation_id"] == installation_id)
    ).mappings().one()
    if device["revoked_at"] is not None:
        raise LoginDenied("Device is revoked")
    if device["platform"] != platform:
        raise LoginDenied("Installation platform mismatch")

    session_id = connection.execute(
        insert(auth_sessions).values(
            user_id=user_id, device_id=device["id"],
            refresh_token_hash=refresh_token_hash, expires_at=expires_at,
        ).returning(auth_sessions.c["id"])
    ).scalar_one()
    # Auditable metadata is strictly allowlisted. Do not persist token/claims.
    connection.execute(insert(audit_events).values(
        actor_user_id=user_id,
        auth_session_id=session_id,
        event_type="auth.google.login",
        request_id=request_id,
        metadata_json={"result": outcome},
    ))
    return device["id"], session_id


def link_verified_google_identity(
    engine: Engine, verified_claims: Mapping[str, Any], *,
    installation_id: str, platform: str, refresh_token_hash: str,
    expires_at: datetime, request_id: str | None = None,
) -> LoginResult:
    """Create/reuse a user atomically and recover the specific Google-sub race.

    Each engine.begin() block owns a separate transaction/connection.  The
    initial failed transaction fully rolls back before recovery starts.
    """
    subject = verified_claims.get("provider_subject")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Expected a verified non-empty Google subject")
    if not isinstance(installation_id, str) or not installation_id.strip():
        raise ValueError("installation_id is required")
    if platform not in {"android", "ios"}:
        raise ValueError("platform must be android or ios")
    if not isinstance(refresh_token_hash, str) or not refresh_token_hash:
        raise ValueError("Appendix K must supply a refresh-token hash")
    if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
        raise ValueError("expires_at must be future and timezone-aware")
    if request_id is not None and (not isinstance(request_id, str)
                                   or len(request_id) > 128):
        raise ValueError("request_id must be a short non-secret identifier")

    try:
        with engine.begin() as connection:
            found = _lookup_identity(connection, subject)
            created_user = found is None
            if found is None:
                user_id = connection.execute(
                    insert(app_users).values(
                        display_name=verified_claims.get("display_name"),
                    ).returning(app_users.c["id"])
                ).scalar_one()
                # Only store Google email if Google actually verified it.
                email = (verified_claims.get("email")
                         if verified_claims.get("email_verified") is True
                         else None)
                connection.execute(insert(external_identities).values(
                    user_id=user_id, provider="google",
                    provider_subject=subject,
                    email_at_verification=email,
                ))
            else:
                user_id = found["user_id"]
                if found["status"] != "active":
                    raise LoginDenied("RedDust account is not active")

            device_id, session_id = _register_device_session_and_audit(
                connection, user_id, installation_id, platform,
                refresh_token_hash, expires_at, request_id,
                "created" if created_user else "existing",
            )
        return LoginResult(user_id, device_id, session_id, created_user, False)
    except IntegrityError as exc:
        if not _is_identity_unique_conflict(exc):
            raise  # Never disguise unrelated DB errors as normal sign-in.

    # The context manager already rolled back any tentative new app_users row.
    # A fresh READ COMMITTED transaction sees the winning committed identity.
    with engine.begin() as connection:
        found = _lookup_identity(connection, subject)
        if found is None:
            raise IdentityRaceRecoveryError(
                "The winning Google identity is not visible after conflict"
            )
        if found["status"] != "active":
            raise LoginDenied("RedDust account is not active")
        user_id = found["user_id"]
        device_id, session_id = _register_device_session_and_audit(
            connection, user_id, installation_id, platform,
            refresh_token_hash, expires_at, request_id, "race_recovered",
        )
    return LoginResult(user_id, device_id, session_id, False, True)
