"""Current caller's account and preferences, never user-selected IDs."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.dependencies.auth import Principal, get_current_principal
from app.models import app_users, user_preferences
from app.runtime import get_engine
from app.schemas import MeResponse

router = APIRouter(prefix="/v1/users", tags=["users"])

@router.get("/me", response_model=MeResponse, status_code=200)
def users_me(principal: Principal = Depends(get_current_principal)) -> MeResponse:
    with get_engine().connect() as connection:
        user = connection.execute(
            select(app_users.c["id"], app_users.c["display_name"])
            .where(app_users.c["id"] == principal.user_id)
        ).mappings().one()
        preferences = connection.execute(
            select(user_preferences.c["preferred_persona"],
                   user_preferences.c["speaker_default"])
            .where(user_preferences.c["user_id"] == principal.user_id)
        ).mappings().one_or_none()
    return MeResponse(user=dict(user), preferences=dict(preferences) if preferences else None)