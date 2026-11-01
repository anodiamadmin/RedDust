"""Offline token checks: ephemeral in-memory RSA key, no local PEM/DB used."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from app.services import tokens


@pytest.fixture
def signing_key(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    material = tokens.SigningMaterial(private, public, "test-key")
    monkeypatch.setattr(tokens, "signing_material", lambda: material)
    return material


def test_valid_access_token_roundtrip(signing_key):
    user, session = uuid4(), uuid4()
    raw = tokens.issue_access_token(user, session)
    assert tokens.verify_access_token(raw) == (user, session)
    assert tokens.verify_access_token(raw, audience=tokens.GATEWAY_AUDIENCE) == (user, session)


def test_unknown_kid_denied(signing_key):
    raw = tokens.issue_access_token(uuid4(), uuid4())
    payload = jwt.decode(raw, signing_key.public_pem, algorithms=["RS256"], options={"verify_aud": False})
    altered = jwt.encode(payload, signing_key.private_pem, algorithm="RS256", headers={"kid": "unapproved-key"})
    with pytest.raises(jwt.InvalidTokenError):
        tokens.verify_access_token(altered)


def test_expired_access_token_denied(signing_key):
    now = datetime.now(timezone.utc)
    raw = jwt.encode({"iss": tokens.ISSUER, "aud": [tokens.AUTH_AUDIENCE],
                      "sub": str(uuid4()), "sid": str(uuid4()),
                      "iat": now - timedelta(hours=2),
                      "nbf": now - timedelta(hours=2),
                      "exp": now - timedelta(hours=1)},
                     signing_key.private_pem, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(jwt.ExpiredSignatureError):
        tokens.verify_access_token(raw)


def test_refresh_secrets_are_random_and_only_hashes_match():
    a = tokens.new_refresh_secret()
    b = tokens.new_refresh_secret()
    assert a != b
    assert len(a) >= 40
    assert tokens.refresh_hash(a) == tokens.refresh_hash(a)
    assert tokens.refresh_hash(a) != tokens.refresh_hash(b)
    assert a != tokens.refresh_hash(a)