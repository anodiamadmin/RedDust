"""RedDust Step 19C.7 / Appendix L.4 — Pydantic v2 HTTP contracts.
 
Schema only: no FastAPI routes, authentication, database access or token issuance.
The Gateway models describe its separate /offer service (port 8000).
"""
 
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID
 
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)
 
 
class ContractModel(BaseModel):
    """Reject fields that do not belong to a documented JSON object."""
 
    model_config = ConfigDict(extra="forbid")
 
 
def _canonical_uuid(value: object) -> object:
    """Accept canonical UUID strings on the wire and UUIDs inside Python."""
    if isinstance(value, str):
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Expected a valid canonical UUID") from exc
        if value != str(parsed):
            raise ValueError("UUID must use canonical lowercase hyphenated format")
    return value
 
 
def _utc_datetime(value: datetime) -> datetime:
    """Require a timezone-aware timestamp; normalize it to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must contain a timezone")
    return value.astimezone(timezone.utc)
 
 
CanonicalUUID = Annotated[UUID, BeforeValidator(_canonical_uuid)]
UtcDateTime = Annotated[datetime, AfterValidator(_utc_datetime)]
 
 
def _nonblank_token(value: str) -> str:
    if not value or any(char.isspace() for char in value):
        raise ValueError("Credential must be nonempty and contain no whitespace")
    return value
 
 
class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"
    service: Literal["reddust-auth-api"] = "reddust-auth-api"
 
 
class UserSummary(ContractModel):
    id: CanonicalUUID
    display_name: str | None
 
 
class GoogleLoginRequest(ContractModel):
    id_token: str = Field(min_length=1, max_length=16384, repr=False)
    installation_id: CanonicalUUID
    platform: Literal["android", "ios"]
 
    _validate_id_token = field_validator("id_token")(_nonblank_token)
 
 
class GoogleLoginResponse(ContractModel):
    user: UserSummary
    auth_session_id: CanonicalUUID
    token_type: Literal["Bearer"]
    access_token: str = Field(min_length=1, max_length=16384, repr=False)
    expires_in: int = Field(gt=0)
    refresh_token: str = Field(min_length=1, max_length=512, repr=False)
    refresh_expires_in: int = Field(gt=0)
 
 
class RefreshRequest(ContractModel):
    refresh_token: str = Field(min_length=1, max_length=512, repr=False)
 
    _validate_refresh_token = field_validator("refresh_token")(_nonblank_token)
 
 
class RefreshResponse(ContractModel):
    auth_session_id: CanonicalUUID
    token_type: Literal["Bearer"]
    access_token: str = Field(min_length=1, max_length=16384, repr=False)
    expires_in: int = Field(gt=0)
    refresh_token: str = Field(min_length=1, max_length=512, repr=False)
    refresh_expires_in: int = Field(gt=0)
 
 
class LogoutRequest(ContractModel):
    """If a body is supplied, it must be exactly {}. 204 has no response model."""
 
 
class UserPreferences(ContractModel):
    preferred_persona: str | None
    speaker_default: str | None
 
 
class MeResponse(ContractModel):
    user: UserSummary
    preferences: UserPreferences | None
 
 
class CreateCallRequest(ContractModel):
    """Client supplies {}, never user_id or auth_session_id."""
 
 
class CallSessionResponse(ContractModel):
    id: CanonicalUUID
    status: str = Field(min_length=1)
    started_at: UtcDateTime
    ended_at: UtcDateTime | None
    end_reason: str | None
 
 
class EndCallRequest(ContractModel):
    reason: Literal[
        "user_hangup", "completed", "connection_lost", "error"
    ] = "user_hangup"
 
 
class ErrorDetail(ContractModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
 
 
class ErrorResponse(ContractModel):
    detail: ErrorDetail
 
 
def _validate_sdp(value: str) -> str:
    if not value.strip():
        raise ValueError("SDP must not be empty")
    if len(value.encode("utf-8")) > 131072:
        raise ValueError("SDP exceeds 131072 UTF-8 bytes")
    return value
 
 
class GatewayOfferRequest(ContractModel):
    """Target contract for separate Gateway service; not an Auth API route."""
 
    call_id: CanonicalUUID
    type: Literal["offer"]
    sdp: str = Field(min_length=1, repr=False)
 
    _check_sdp = field_validator("sdp")(_validate_sdp)
 
 
class GatewayOfferResponse(ContractModel):
    call_id: CanonicalUUID
    type: Literal["answer"]
    sdp: str = Field(min_length=1, repr=False)
 
    _check_sdp = field_validator("sdp")(_validate_sdp)