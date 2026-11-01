"""RedDust local-development RS256 JWTs and opaque refresh credentials.

K.2 local PEM keys are read only by this server. No keys are sent to clients.
A future K rotation design will use a multi-key JWKS/key registry.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import os
import secrets
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ACCESS_TTL_SECONDS = 900
REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60
ISSUER = "reddust-auth-api"
AUTH_AUDIENCE = "reddust-auth-api"
GATEWAY_AUDIENCE = "reddust-gateway"


class TokenConfigurationError(RuntimeError):
    """Key/configuration not ready; fail closed without exposing key contents."""


@dataclass(frozen=True)
class SigningMaterial:
    private_pem: bytes
    public_pem: bytes
    kid: str


@lru_cache(maxsize=1)
def signing_material() -> SigningMaterial:
    load_dotenv(ROOT / ".env.local", override=False)
    private_name = os.getenv("RD_PRIVATE_KEY_FILE", "./secrets/jwt-private.pem")
    public_name = os.getenv("RD_PUBLIC_KEY_FILE", "./secrets/jwt-public.pem")
    kid = os.getenv("RD_JWT_KID", "local-rsa-1")
    if not kid or len(kid) > 64 or any(c.isspace() for c in kid):
        raise TokenConfigurationError("Invalid RD_JWT_KID")

    def path_of(name: str) -> Path:
        p = Path(name)
        return p if p.is_absolute() else ROOT / p

    try:
        private = path_of(private_name).read_bytes()
        public = path_of(public_name).read_bytes()
        private_key = serialization.load_pem_private_key(private, password=None)
        public_key = serialization.load_pem_public_key(public)
        if private_key.public_key().public_numbers() != public_key.public_numbers():
            raise TokenConfigurationError("Signing/verification keys do not match")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise TokenConfigurationError("JWT signing keys unavailable or invalid") from exc
    return SigningMaterial(private, public, kid)


def new_refresh_secret() -> str:
    return secrets.token_urlsafe(48)


def refresh_hash(raw_secret: str) -> str:
    # SHA-256 is suitable here because the raw credential contains 384 random bits.
    return sha256(raw_secret.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TTL_SECONDS)


def issue_access_token(user_id: UUID, session_id: UUID, *, audience: str = AUTH_AUDIENCE) -> str:
    if audience not in {AUTH_AUDIENCE, GATEWAY_AUDIENCE}:
        raise ValueError("Unexpected access-token audience")
    m = signing_material()
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER, "aud": [AUTH_AUDIENCE, GATEWAY_AUDIENCE],
        "sub": str(user_id), "sid": str(session_id),
        "iat": now, "nbf": now, "exp": now + timedelta(seconds=ACCESS_TTL_SECONDS),
    }
    return jwt.encode(claims, m.private_pem, algorithm="RS256", headers={"kid": m.kid, "typ": "JWT"})


def verify_access_token(raw_token: str, *, audience: str = AUTH_AUDIENCE) -> tuple[UUID, UUID]:
    if audience not in {AUTH_AUDIENCE, GATEWAY_AUDIENCE}:
        raise ValueError("Unexpected access-token audience")
    m = signing_material()
    header = jwt.get_unverified_header(raw_token)
    if header.get("alg") != "RS256" or header.get("kid") != m.kid:
        raise jwt.InvalidTokenError("Unapproved JWT signing algorithm or key")
    claims = jwt.decode(
        raw_token, m.public_pem, algorithms=["RS256"], issuer=ISSUER,
        audience=audience, leeway=5,
        options={"require": ["iss", "aud", "sub", "sid", "iat", "nbf", "exp"]},
    )
    try:
        return UUID(claims["sub"]), UUID(claims["sid"])
    except (TypeError, ValueError, KeyError) as exc:
        raise jwt.InvalidTokenError("Invalid principal identifiers") from exc