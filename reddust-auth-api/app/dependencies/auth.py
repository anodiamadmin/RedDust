"""Bearer-JWT verification AND current PostgreSQL session/account checks."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.models import app_users, auth_sessions, client_devices
from app.runtime import get_engine
from app.services.tokens import TokenConfigurationError, verify_access_token

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    auth_session_id: UUID


def fail(status: int, code: str, message: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return HTTPException(status, detail={"code": code, "message": message}, headers=headers)


def get_current_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise fail(401, "INVALID_ACCESS_TOKEN", "Bearer credential required")
    try:
        user_id, session_id = verify_access_token(credentials.credentials)
    except TokenConfigurationError as exc:
        raise fail(503, "AUTH_UNAVAILABLE", "Authorization unavailable") from exc
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise fail(401, "INVALID_ACCESS_TOKEN", "Invalid or expired credential") from exc

    engine = get_engine()
    with engine.connect() as connection:
        session = connection.execute(
            select(
                auth_sessions.c["id"], auth_sessions.c["user_id"],
                auth_sessions.c["device_id"], auth_sessions.c["expires_at"],
                auth_sessions.c["revoked_at"],
            ).where(
                auth_sessions.c["id"] == session_id,
                auth_sessions.c["user_id"] == user_id,
            )
        ).mappings().one_or_none()
        if (session is None or session["revoked_at"] is not None
                or session["expires_at"] <= datetime.now(timezone.utc)):
            raise fail(401, "INVALID_ACCESS_TOKEN", "Session inactive")
        user_status = connection.execute(
            select(app_users.c["status"]).where(app_users.c["id"] == user_id)
        ).scalar_one_or_none()
        if user_status != "active":
            raise fail(403, "ACCOUNT_NOT_ALLOWED", "Account not active")
        if session["device_id"] is not None:
            device = connection.execute(
                select(client_devices.c["user_id"], client_devices.c["revoked_at"])
                .where(client_devices.c["id"] == session["device_id"])
            ).mappings().one_or_none()
            if (device is None or device["user_id"] != user_id
                    or device["revoked_at"] is not None):
                raise fail(401, "INVALID_ACCESS_TOKEN", "Device inactive")
    return Principal(user_id=user_id, auth_session_id=session_id)