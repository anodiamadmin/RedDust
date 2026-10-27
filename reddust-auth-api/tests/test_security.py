# tests/test_security.py
# RedDust — Google ID Token Verification Unit Tests
# These tests mock Google's verification helper.
# They do not require live Google tokens or network access.

import pytest
from app.security import verify_google_id_token

APPROVED_CLIENT_ID = ("reddust-test-client.apps.googleusercontent.com")

def mock_google_verification(monkeypatch, claims):
    """Replace Google's token verifier with a local mock."""
    def fake_verify(raw_token, request, audience=None):
        assert raw_token == "mock-google-token"
        assert audience is None
        return claims

    monkeypatch.setattr("app.security.id_token.verify_oauth2_token", fake_verify,)

def valid_claims():
    return {
        "iss": "https://accounts.google.com",
        "aud": APPROVED_CLIENT_ID,
        "sub": "google-test-subject-123",
        "email": "test@example.com",
        "email_verified": True,
        "name": "RedDust Test User",
    }

def test_valid_google_token(monkeypatch):
    """A token with acceptable claims should be accepted."""
    mock_google_verification(monkeypatch, valid_claims(),)
    result = verify_google_id_token("mock-google-token", {APPROVED_CLIENT_ID},)
    assert result["provider_subject"] == ("google-test-subject-123")
    assert result["email"] == "test@example.com"
    assert result["email_verified"] is True
    assert result["display_name"] == "RedDust Test User"

def test_wrong_audience_rejected(monkeypatch):
    """A token for another application must be rejected."""
    claims = valid_claims()
    claims["aud"] = ("unapproved-client.apps.googleusercontent.com")
    mock_google_verification(monkeypatch, claims)
    with pytest.raises(ValueError, match="Token audience not approved",):
        verify_google_id_token("mock-google-token", {APPROVED_CLIENT_ID},)

def test_wrong_issuer_rejected(monkeypatch):
    """An unapproved issuer must be rejected."""
    claims = valid_claims()
    claims["iss"] = "https://untrusted.example.com"
    mock_google_verification(monkeypatch, claims)
    with pytest.raises( ValueError, match="Invalid Google issuer",):
        verify_google_id_token("mock-google-token", {APPROVED_CLIENT_ID},)

def test_missing_subject_rejected(monkeypatch):
    """A missing Google subject must be rejected."""
    claims = valid_claims()
    claims["sub"] = ""
    mock_google_verification(monkeypatch, claims)
    with pytest.raises(ValueError, match="Missing Google subject",):
        verify_google_id_token("mock-google-token", {APPROVED_CLIENT_ID},)

def test_missing_token_rejected():
    """An empty token must be rejected."""
    with pytest.raises(ValueError, match="Missing token or approved audience",):
        verify_google_id_token("", {APPROVED_CLIENT_ID},)

def test_missing_allowed_audiences_rejected():
    """Verification must not run without approved audiences."""
    with pytest.raises(ValueError, match="Missing token or approved audience",):
        verify_google_id_token("mock-google-token", set(),)

def test_unverified_email_not_trusted(monkeypatch):
    """The email_verified field must be strictly boolean."""
    claims = valid_claims()
    claims["email_verified"] = False
    mock_google_verification(monkeypatch, claims)
    result = verify_google_id_token( "mock-google-token", {APPROVED_CLIENT_ID},)
    assert result["email_verified"] is False
