from app.models import metadata


def test_required_tables_present():
    expected = {
        "app_users", "external_identities", "client_devices",
        "auth_sessions", "call_sessions", "audit_events",
        "user_preferences",
    }
    assert set(metadata.tables) == expected


def test_sensitive_uniqueness_constraints():
    external = metadata.tables["external_identities"]
    identity_keys = {tuple(c.name for c in u.columns)
                     for u in external.constraints
                     if u.__class__.__name__ == "UniqueConstraint"}
    assert ("provider", "provider_subject") in identity_keys