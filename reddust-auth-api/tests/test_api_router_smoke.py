"""Safe smoke tests. No real credentials, PostgreSQL connection or mutations."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_healthz_200_safe_body():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "reddust-auth-api"}


def test_openapi_exact_auth_api_routes():
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/healthz", "/v1/auth/google", "/v1/auth/refresh",
        "/v1/auth/logout", "/v1/users/me", "/v1/calls",
        "/v1/calls/{id}/end",
    ):
        assert path in paths
    assert "/offer" not in paths  # Gateway owns /offer, not the Auth API.


def test_bearer_security_present_in_openapi():
    spec = client.get("/openapi.json").json()
    for path, method in (
        ("/v1/auth/logout", "post"),
        ("/v1/users/me", "get"),
        ("/v1/calls", "post"),
        ("/v1/calls/{id}/end", "post"),
    ):
        assert spec["paths"][path][method].get("security")


def test_users_me_without_bearer_is_401_not_404():
    r = client.get("/v1/users/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_google_payload_rejects_client_user_id_and_does_not_echo_secret():
    value = "NOT_A_REAL_GOOGLE_TOKEN"
    r = client.post("/v1/auth/google", json={
        "id_token": value,
        "installation_id": "70e91b9b-a66a-4c5b-a7ec-14515b0a9028",
        "platform": "android",
        "user_id": "forged-client-user",
    })
    assert r.status_code == 422
    assert value not in r.text


def test_refresh_requires_a_body():
    r = client.post("/v1/auth/refresh", json={})
    assert r.status_code == 422


def test_gateway_offer_is_not_an_auth_api_endpoint():
    r = client.post("/offer", json={"sdp": "fake", "type": "offer"})
    assert r.status_code == 404