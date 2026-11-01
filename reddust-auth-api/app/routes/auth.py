"""Google sign-in, atomic refresh rotation and current-session logout."""
from datetime import datetime, timezone
import os
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from google.auth.exceptions import GoogleAuthError
from sqlalchemy import insert, select, update

from app.dependencies.auth import Principal, fail, get_current_principal
from app.models import app_users, auth_sessions, audit_events, client_devices
from app.runtime import get_engine
from app.schemas import (
    GoogleLoginRequest, GoogleLoginResponse, LogoutRequest,
    RefreshRequest, RefreshResponse,
)
from app.security import verify_google_id_token
from app.services.identity import LoginDenied, link_verified_google_identity
from app.services.rate_limits import enforce_local_rate_limit
from app.services.tokens import (
    ACCESS_TTL_SECONDS, REFRESH_TTL_SECONDS, TokenConfigurationError,
    issue_access_token, new_refresh_secret, refresh_expiry, refresh_hash,
    signing_material,
)
from pathlib import Path

router = APIRouter(prefix="/v1/auth", tags=["authentication"])


def allowed_google_audiences() -> set[str]:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env.local", override=False)
    value = os.getenv("RD_GOOGLE_ALLOWED_AUDIENCES", "")
    audiences = {part.strip() for part in value.split(",") if part.strip()}
    if not audiences:
        raise fail(503, "AUTH_UNAVAILABLE", "Google verification not configured")
    return audiences


@router.post("/google", response_model=GoogleLoginResponse, status_code=200,
             responses={401: {"description": "Invalid Google token"},
                        403: {"description": "Account/device denied"},
                        429: {"description": "Rate limited"},
                        503: {"description": "Authorization unavailable"}})
def google_login(payload: GoogleLoginRequest, request: Request, response: Response) -> GoogleLoginResponse:
    response.headers["Cache-Control"] = "no-store"
    enforce_local_rate_limit(request, category="google", limit=10)
    try:
        verified = verify_google_id_token(payload.id_token, allowed_google_audiences())
    except HTTPException:
        raise
    except ValueError as exc:
        raise fail(401, "INVALID_GOOGLE_TOKEN", "Google credential invalid") from exc
    except GoogleAuthError as exc:
        raise fail(503, "AUTH_UNAVAILABLE", "Google verification unavailable") from exc

    # Preflight signing keys BEFORE creating an auth_sessions row.
    try:
        signing_material()
    except TokenConfigurationError as exc:
        raise fail(503, "AUTH_UNAVAILABLE", "Token signing unavailable") from exc

    refresh = new_refresh_secret()
    engine = get_engine()
    try:
        linked = link_verified_google_identity(
            engine, verified, installation_id=str(payload.installation_id),
            platform=payload.platform, refresh_token_hash=refresh_hash(refresh),
            expires_at=refresh_expiry(), request_id=str(uuid4()),
        )
    except LoginDenied as exc:
        raise fail(403, "ACCOUNT_OR_DEVICE_NOT_ALLOWED", "Account or device not allowed") from exc

    try:
        access = issue_access_token(linked.user_id, linked.auth_session_id)
    except Exception:
        # Compensate for an extremely unlikely signing failure after J.5 commit.
        with engine.begin() as connection:
            connection.execute(update(auth_sessions).where(
                auth_sessions.c["id"] == linked.auth_session_id,
            ).values(revoked_at=datetime.now(timezone.utc)))
        raise fail(503, "AUTH_UNAVAILABLE", "Token signing unavailable") from None

    with engine.connect() as connection:
        name = connection.execute(
            select(app_users.c["display_name"])
            .where(app_users.c["id"] == linked.user_id)
        ).scalar_one()
    return GoogleLoginResponse(
        user={"id": linked.user_id, "display_name": name},
        auth_session_id=linked.auth_session_id, token_type="Bearer",
        access_token=access, expires_in=ACCESS_TTL_SECONDS,
        refresh_token=refresh, refresh_expires_in=REFRESH_TTL_SECONDS,
    )


@router.post("/refresh", response_model=RefreshResponse, status_code=200,
             responses={401: {"description": "Invalid/rotated refresh token"},
                        403: {"description": "Account/device denied"},
                        429: {"description": "Rate limited"}})
def refresh_session(payload: RefreshRequest, request: Request, response: Response) -> RefreshResponse:
    response.headers["Cache-Control"] = "no-store"
    enforce_local_rate_limit(request, category="refresh", limit=30)
    try:
        signing_material()
    except TokenConfigurationError as exc:
        raise fail(503, "AUTH_UNAVAILABLE", "Token signing unavailable") from exc

    old_hash = refresh_hash(payload.refresh_token)
    new_secret = new_refresh_secret()
    new_hash = refresh_hash(new_secret)
    new_expires = refresh_expiry()

    with get_engine().begin() as connection:
        # Row lock serializes simultaneous refresh requests for the same token.
        session = connection.execute(
            select(auth_sessions).where(
                auth_sessions.c["refresh_token_hash"] == old_hash,
                auth_sessions.c["revoked_at"].is_(None),
                auth_sessions.c["expires_at"] > datetime.now(timezone.utc),
            ).with_for_update(of=auth_sessions)
        ).mappings().one_or_none()
        if session is None:
            raise fail(401, "INVALID_REFRESH_TOKEN", "Refresh credential invalid")
        uid = session["user_id"]
        status_value = connection.execute(
            select(app_users.c["status"]).where(app_users.c["id"] == uid)
        ).scalar_one_or_none()
        if status_value != "active":
            raise fail(403, "ACCOUNT_OR_DEVICE_NOT_ALLOWED", "Account not active")
        if session["device_id"] is not None:
            device = connection.execute(
                select(client_devices.c["user_id"], client_devices.c["revoked_at"])
                .where(client_devices.c["id"] == session["device_id"])
            ).mappings().one_or_none()
            if (device is None or device["user_id"] != uid
                    or device["revoked_at"] is not None):
                raise fail(403, "ACCOUNT_OR_DEVICE_NOT_ALLOWED", "Device not active")
        updated = connection.execute(
            update(auth_sessions).where(
                auth_sessions.c["id"] == session["id"],
                auth_sessions.c["refresh_token_hash"] == old_hash,
                auth_sessions.c["revoked_at"].is_(None),
            ).values(refresh_token_hash=new_hash, expires_at=new_expires)
        )
        if updated.rowcount != 1:
            raise fail(401, "INVALID_REFRESH_TOKEN", "Refresh credential invalid")
        access = issue_access_token(uid, session["id"])
        connection.execute(insert(audit_events).values(
            actor_user_id=uid, auth_session_id=session["id"],
            event_type="auth.refresh", metadata_json={"result": "rotated"},
        ))

    return RefreshResponse(
        auth_session_id=session["id"], token_type="Bearer",
        access_token=access, expires_in=ACCESS_TTL_SECONDS,
        refresh_token=new_secret, refresh_expires_in=REFRESH_TTL_SECONDS,
    )


@router.post("/logout", status_code=204, response_class=Response,
             responses={401: {"description": "Invalid or inactive access token"}})
def logout_session(
    payload: LogoutRequest | None = Body(default=None),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    with get_engine().begin() as connection:
        outcome = connection.execute(
            update(auth_sessions).where(
                auth_sessions.c["id"] == principal.auth_session_id,
                auth_sessions.c["user_id"] == principal.user_id,
                auth_sessions.c["revoked_at"].is_(None),
            ).values(revoked_at=datetime.now(timezone.utc))
        )
        if outcome.rowcount != 1:
            raise fail(401, "INVALID_ACCESS_TOKEN", "Session already inactive")
        connection.execute(insert(audit_events).values(
            actor_user_id=principal.user_id,
            auth_session_id=principal.auth_session_id,
            event_type="auth.logout", metadata_json={"result": "revoked"},
        ))
    return Response(status_code=status.HTTP_204_NO_CONTENT)