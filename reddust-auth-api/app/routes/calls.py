"""Call session lifecycle for verified/current session owner only."""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Body, Depends
from sqlalchemy import insert, select, update
from app.dependencies.auth import Principal, fail, get_current_principal
from app.models import call_sessions
from app.runtime import get_engine
from app.schemas import CallSessionResponse, CreateCallRequest, EndCallRequest

router = APIRouter(prefix="/v1/calls", tags=["calls"])

@router.post("", response_model=CallSessionResponse, status_code=201)
def create_call(
    payload: CreateCallRequest,
    principal: Principal = Depends(get_current_principal),
) -> CallSessionResponse:
    with get_engine().begin() as connection:
        row = connection.execute(
            insert(call_sessions).values(
                user_id=principal.user_id,
                auth_session_id=principal.auth_session_id,
                status="starting",
            ).returning(
                call_sessions.c["id"], call_sessions.c["status"],
                call_sessions.c["started_at"], call_sessions.c["ended_at"],
                call_sessions.c["end_reason"],
            )
        ).mappings().one()
    return CallSessionResponse(**dict(row))

@router.post("/{id}/end", response_model=CallSessionResponse, status_code=200,
             responses={404: {"description": "Call missing or not owned"}})
def end_call(
    id: UUID,
    payload: EndCallRequest = Body(default=EndCallRequest()),
    principal: Principal = Depends(get_current_principal),
) -> CallSessionResponse:
    with get_engine().begin() as connection:
        # Atomic update: two end requests cannot overwrite each other's end time.
        result = connection.execute(
            update(call_sessions).where(
                call_sessions.c["id"] == id,
                call_sessions.c["user_id"] == principal.user_id,
                call_sessions.c["status"] != "ended",
            ).values(
                status="ended", ended_at=datetime.now(timezone.utc),
                end_reason=payload.reason,
            ).returning(
                call_sessions.c["id"], call_sessions.c["status"],
                call_sessions.c["started_at"], call_sessions.c["ended_at"],
                call_sessions.c["end_reason"],
            )
        ).mappings().one_or_none()
        if result is None:
            # Deliberately hide whether a missing UUID belongs to another user.
            result = connection.execute(
                select(
                    call_sessions.c["id"], call_sessions.c["status"],
                    call_sessions.c["started_at"], call_sessions.c["ended_at"],
                    call_sessions.c["end_reason"],
                ).where(
                    call_sessions.c["id"] == id,
                    call_sessions.c["user_id"] == principal.user_id,
                    call_sessions.c["status"] == "ended",
                )
            ).mappings().one_or_none()
        if result is None:
            raise fail(404, "CALL_NOT_FOUND", "Call not found")
    return CallSessionResponse(**dict(result))