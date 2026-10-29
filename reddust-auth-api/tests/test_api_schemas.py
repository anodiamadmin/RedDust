"""Appendix L.4 schema-only checks: no database, network or real credentials."""
 
from datetime import datetime, timezone
from uuid import UUID
 
import pytest
from pydantic import ValidationError
 
from app.schemas import (
    CallSessionResponse, CreateCallRequest, EndCallRequest,
    GatewayOfferRequest, GatewayOfferResponse, GoogleLoginRequest,
    GoogleLoginResponse, HealthResponse, LogoutRequest, MeResponse,
    RefreshRequest, RefreshResponse,
)
 
USER_ID = "0ba779fd-74d9-4d39-92e7-03229b6aa8ba"
SESSION_ID = "78675bb4-97a6-45d2-a66f-7019bf073237"
CALL_ID = "821b0eb5-37be-4e54-8058-075f9e8a9ce1"
INSTALL_ID = "70e91b9b-a66a-4c5b-a7ec-14515b0a9028"
 
 
def login_request(**changes):
    payload = {
        "id_token": "synthetic.jwt.value",
        "installation_id": INSTALL_ID,
        "platform": "android",
    }
    payload.update(changes)
    return payload
 
 
def login_response():
    return {
        "user": {"id": USER_ID, "display_name": "Test User"},
        "auth_session_id": SESSION_ID,
        "token_type": "Bearer",
        "access_token": "synthetic.access.jwt",
        "expires_in": 900,
        "refresh_token": "synthetic-random-refresh",
        "refresh_expires_in": 2592000,
    }
 
 
def test_health_schema_exact():
    assert HealthResponse().model_dump() == {
        "status": "ok", "service": "reddust-auth-api"
    }
    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "ok", "secret": "oops"})
 
 
def test_google_request_valid():
    result = GoogleLoginRequest.model_validate(login_request())
    assert result.installation_id == UUID(INSTALL_ID)
    assert result.platform == "android"
    assert result.model_dump(mode="json")["installation_id"] == INSTALL_ID
 
 
@pytest.mark.parametrize("changes", [
    {"platform": "windows"},
    {"installation_id": "not-a-uuid"},
    {"installation_id": INSTALL_ID.replace("-", "")},
    {"installation_id": INSTALL_ID.upper()},
    {"id_token": ""},
    {"id_token": "  "},
    {"id_token": "abc def"},
    {"id_token": "x" * 16385},
    {"user_id": USER_ID},
])
def test_google_request_rejects_bad_fields(changes):
    with pytest.raises(ValidationError):
        GoogleLoginRequest.model_validate(login_request(**changes))
 
 
def test_google_request_rejects_missing_fields():
    for field in ("id_token", "installation_id", "platform"):
        payload = login_request()
        del payload[field]
        with pytest.raises(ValidationError):
            GoogleLoginRequest.model_validate(payload)
 
 
def test_login_response_contains_exact_safe_fields():
    result = GoogleLoginResponse.model_validate(login_response())
    output = result.model_dump(mode="json")
    assert output == login_response()
    assert "refresh_token_hash" not in output
    assert "id_token" not in output
    assert "synthetic.access.jwt" not in repr(result)
    assert "synthetic-random-refresh" not in repr(result)
 
 
def test_login_response_requires_token_fields():
    for field in ("access_token", "refresh_token", "expires_in"):
        bad = login_response()
        bad.pop(field)
        with pytest.raises(ValidationError):
            GoogleLoginResponse.model_validate(bad)
 
 
def test_refresh_contract_and_rejects_extra_fields():
    assert RefreshRequest.model_validate({"refresh_token": "synthetic"}).refresh_token == "synthetic"
    with pytest.raises(ValidationError):
        RefreshRequest.model_validate({"refresh_token": "synthetic", "user_id": USER_ID})
    with pytest.raises(ValidationError):
        RefreshRequest.model_validate({"refresh_token": "synthetic\n"})
    body = login_response()
    del body["user"]
    assert RefreshResponse.model_validate(body).auth_session_id == UUID(SESSION_ID)
 
 
def test_empty_logout_and_create_call_reject_untrusted_identifiers():
    assert LogoutRequest.model_validate({}).model_dump() == {}
    assert CreateCallRequest.model_validate({}).model_dump() == {}
    for cls in (LogoutRequest, CreateCallRequest):
        with pytest.raises(ValidationError):
            cls.model_validate({"user_id": USER_ID})
 
 
def test_me_response_requires_preferences_key_but_accepts_null():
    p = {"user": {"id": USER_ID, "display_name": None}, "preferences": None}
    assert MeResponse.model_validate(p).model_dump(mode="json") == p
    p["preferences"] = {"preferred_persona": None, "speaker_default": "neutral"}
    assert MeResponse.model_validate(p).preferences.speaker_default == "neutral"
    del p["preferences"]
    with pytest.raises(ValidationError):
        MeResponse.model_validate(p)
 
 
def test_call_response_serializes_utc_timestamps_and_null_fields():
    item = CallSessionResponse.model_validate({
        "id": CALL_ID, "status": "starting",
        "started_at": "2026-10-28T11:00:00+11:00",
        "ended_at": None, "end_reason": None,
    })
    body = item.model_dump(mode="json")
    assert body["started_at"] == "2026-10-28T00:00:00Z"
    assert body["ended_at"] is None
    assert body["end_reason"] is None
 
 
def test_naive_call_timestamp_rejected():
    with pytest.raises(ValidationError):
        CallSessionResponse.model_validate({
            "id": CALL_ID, "status": "starting",
            "started_at": datetime(2026, 10, 28),
            "ended_at": None, "end_reason": None,
        })
 
 
def test_end_call_reason_defaults_and_validates():
    assert EndCallRequest.model_validate({}).reason == "user_hangup"
    assert EndCallRequest.model_validate({"reason": "completed"}).reason == "completed"
    with pytest.raises(ValidationError):
        EndCallRequest.model_validate({"reason": "made_up_reason"})
    with pytest.raises(ValidationError):
        EndCallRequest.model_validate({"reason": "completed", "user_id": USER_ID})
 
 
def test_gateway_offer_contract_and_utf8_byte_bound():
    request = {"call_id": CALL_ID, "type": "offer", "sdp": "v=0\r\n"}
    assert GatewayOfferRequest.model_validate(request).type == "offer"
    assert GatewayOfferResponse.model_validate({**request, "type": "answer"}).type == "answer"
    with pytest.raises(ValidationError):
        GatewayOfferRequest.model_validate({**request, "type": "answer"})
    with pytest.raises(ValidationError):
        GatewayOfferRequest.model_validate({**request, "sdp": "😀" * 32769})
    with pytest.raises(ValidationError):
        GatewayOfferRequest.model_validate({**request, "sdp": " \n "})
    with pytest.raises(ValidationError):
        GatewayOfferRequest.model_validate({**request, "user_id": USER_ID})
 
 
def test_contract_schema_json_is_available():
    assert "properties" in GoogleLoginRequest.model_json_schema()
    assert "properties" in CallSessionResponse.model_json_schema()