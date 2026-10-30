# app/security.py — illustrative implementation core
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
 
def verify_google_id_token(raw_token: str, allowed_audiences: set[str]) -> dict:
    if not raw_token or not allowed_audiences:
        raise ValueError("Missing token or approved audience")
    claims = id_token.verify_oauth2_token(
        raw_token,
        google_requests.Request(),
        audience=None,  # aud is checked explicitly below
    )
    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise ValueError("Invalid Google issuer")
    if claims.get("aud") not in allowed_audiences:
        raise ValueError("Token audience not approved")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ValueError("Missing Google subject")
    return {
        "provider_subject": subject,
        "email": claims.get("email"),
        "email_verified": claims.get("email_verified") is True,
        "display_name": claims.get("name"),
    }
