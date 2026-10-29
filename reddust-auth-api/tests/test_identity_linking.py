"""J.5.7 real PostgreSQL integration tests. DESTRUCTIVE TO reddust_test ONLY.
 
Prerequisites: create reddust_test owned by reddust_app and run Alembic
baseline on that database. Never point this test module at reddust_dev.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Barrier
 
import pytest
from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.exc import IntegrityError
 
from app.db import database_url
from app.models import (
    metadata, app_users, external_identities, client_devices,
    auth_sessions, call_sessions, audit_events,
)
from app.services import identity as identity_service
from app.services.identity import LoginDenied, link_verified_google_identity
 
TEST_DB = "reddust_test"
REQUIRED_TABLES = {
    "app_users", "external_identities", "client_devices", "auth_sessions",
    "call_sessions", "audit_events", "user_preferences", "alembic_version",
}
 
 
@pytest.fixture(scope="session")
def engine():
    # Explicitly target a separate disposable database. Do not use the dev DB.
    url = database_url()
    assert url.host in {"127.0.0.1", "localhost"}, "Local PostgreSQL required"
    assert url.database == "reddust_dev", (
        "Use normal RD_DB_* settings; this fixture selects reddust_test explicitly"
    )
    test_engine = create_engine(
        url.set(database=TEST_DB),
        isolation_level="READ COMMITTED",
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 5},
    )
    try:
        with test_engine.connect() as connection:
            actual = connection.execute(text("SELECT current_database()"))
            assert actual.scalar_one() == TEST_DB
            actual_user = connection.execute(text("SELECT current_user"))
            assert actual_user.scalar_one() == "reddust_app"
            existing = set(connection.execute(text("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            """)).scalars())
            assert REQUIRED_TABLES <= existing, (
                "Missing migrated test tables: " + repr(REQUIRED_TABLES - existing)
            )
            head_rows = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all()
            assert len(head_rows) == 1, "Run reviewed Alembic upgrade on reddust_test"
        yield test_engine
    finally:
        test_engine.dispose()
 
 
@pytest.fixture(autouse=True)
def clean_disposable_test_database(engine):
    """Erase ONLY application tables in reddust_test before/after each test.
 
    The Alembic version table and schema objects remain intact.
    Requires an EXCLUSIVELY dedicated disposable test database.
    """
    def wipe():
        with engine.begin() as connection:
            assert connection.execute(
                text("SELECT current_database()")
            ).scalar_one() == TEST_DB
            connection.execute(text("""
                TRUNCATE TABLE
                    public.audit_events, public.call_sessions,
                    public.auth_sessions, public.client_devices,
                    public.external_identities, public.user_preferences,
                    public.app_users
                RESTART IDENTITY CASCADE
            """))
 
    wipe()
    yield
    wipe()
 
 
def claims(sub="google-sub-A", email="a@example.test", verified=True):
    # This dict represents the *output of J.3 verification*, not a raw ID token.
    return {
        "provider_subject": sub, "email": email,
        "email_verified": verified, "display_name": "Test User",
    }
 
 
def token_hash(label):
    # Deterministic fake hashes are ONLY for this isolated test database.
    # Real raw refresh tokens and cryptographic policy come from Appendix K.
    return sha256(("reddust-j57-test-" + label).encode("utf-8")).hexdigest()
 
 
def login(engine, *, sub="google-sub-A", install="installation-A",
          platform="android", hash_label="token-A", email="a@example.test",
          verified=True):
    return link_verified_google_identity(
        engine, claims(sub=sub, email=email, verified=verified),
        installation_id=install, platform=platform,
        refresh_token_hash=token_hash(hash_label),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        request_id="j57-test-request",
    )
 
 
def count_rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(
            select(text("count(*)")).select_from(table)
        ).scalar_one()


def violated_constraint(error: IntegrityError) -> str | None:
    """Read PostgreSQL's constraint name without dynamic .diag warnings."""
    diagnostics = getattr(error.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def test_schema_has_unique_identity_constraint(engine):
    assert "external_identities" in metadata.tables
    with engine.connect() as connection:
        constraint = connection.execute(text("""
            SELECT pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE conrelid = 'public.external_identities'::regclass
               AND conname = 'uq_external_identity_provider_subject'
               AND contype = 'u' AND convalidated
        """)).scalar_one()
    assert "UNIQUE (provider, provider_subject)" in constraint
 
 
def test_first_login_creates_user_identity_device_session_and_audit(engine):
    result = login(engine)
    assert result.created_user is True
    assert result.recovered_identity_race is False
    for table in (app_users, external_identities, client_devices,
                  auth_sessions, audit_events):
        assert count_rows(engine, table) == 1
    with engine.connect() as connection:
        identity = connection.execute(select(external_identities)).mappings().one()
        device = connection.execute(select(client_devices)).mappings().one()
        session = connection.execute(select(auth_sessions)).mappings().one()
        audit = connection.execute(select(audit_events)).mappings().one()
    assert identity["user_id"] == device["user_id"] == session["user_id"] == result.user_id
    assert session["device_id"] == result.device_id
    assert session["id"] == result.auth_session_id
    assert session["refresh_token_hash"] == token_hash("token-A")
    assert audit["metadata_json"] == {"result": "created"}
    assert audit["actor_user_id"] == result.user_id
    assert audit["auth_session_id"] == result.auth_session_id
 
 
def test_repeat_login_reuses_same_user_and_device(engine):
    first = login(engine, hash_label="first")
    second = login(engine, hash_label="second")
    assert first.user_id == second.user_id
    assert first.device_id == second.device_id
    assert first.auth_session_id != second.auth_session_id
    assert second.created_user is False
    assert count_rows(engine, app_users) == 1
    assert count_rows(engine, external_identities) == 1
    assert count_rows(engine, client_devices) == 1
    assert count_rows(engine, auth_sessions) == 2
 
 
def test_changed_email_does_not_change_stable_google_subject_mapping(engine):
    first = login(engine, email="old@example.test", hash_label="first")
    second = login(engine, email="new@example.test", hash_label="second")
    assert first.user_id == second.user_id
    assert count_rows(engine, external_identities) == 1
 
 
def test_unverified_email_is_not_stored_as_verified_identity_metadata(engine):
    login(engine, email="unverified@example.test", verified=False)
    with engine.connect() as connection:
        stored = connection.execute(
            select(external_identities.c["email_at_verification"])
        )
        assert stored.scalar_one() is None
 
 
def test_distinct_google_subjects_with_same_email_stay_separate(engine):
    a = login(engine, sub="sub-A", install="install-A", hash_label="A")
    b = login(engine, sub="sub-B", install="install-B", hash_label="B")
    assert a.user_id != b.user_id
    assert count_rows(engine, app_users) == 2
    assert count_rows(engine, external_identities) == 2
 
 
def test_missing_subject_fails_without_database_changes(engine):
    with pytest.raises(ValueError, match="non-empty Google subject"):
        link_verified_google_identity(
            engine, claims(sub=""), installation_id="x", platform="android",
            refresh_token_hash=token_hash("invalid"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    assert count_rows(engine, app_users) == 0
 
 
def test_unsupported_platform_rejected_before_writes(engine):
    with pytest.raises(ValueError, match="platform must be"):
        login(engine, platform="windows")
    assert count_rows(engine, app_users) == 0
 
 
def test_disabled_account_does_not_get_new_session(engine):
    first = login(engine)
    with engine.begin() as connection:
        connection.execute(
            update(app_users)
            .where(app_users.c["id"] == first.user_id)
            .values(status="disabled")
        )
    with pytest.raises(LoginDenied, match="not active"):
        login(engine, hash_label="second")
    assert count_rows(engine, auth_sessions) == 1
 
 
def test_revoked_device_does_not_get_new_session(engine):
    first = login(engine)
    with engine.begin() as connection:
        connection.execute(
            update(client_devices)
            .where(client_devices.c["id"] == first.device_id)
            .values(revoked_at=datetime.now(timezone.utc))
        )
    with pytest.raises(LoginDenied, match="revoked"):
        login(engine, hash_label="second")
    assert count_rows(engine, auth_sessions) == 1
 
 
def test_duplicate_refresh_hash_is_not_misclassified_as_identity_race(engine):
    login(engine, install="first", hash_label="same")
    with pytest.raises(IntegrityError) as error:
        login(engine, install="second", hash_label="same")
    assert getattr(error.value.orig, "sqlstate", None) == "23505"
    assert violated_constraint(error.value) == (
        "uq_auth_sessions_refresh_token_hash"
    )
    # Both the tentative second device and session roll back.
    assert count_rows(engine, client_devices) == 1
    assert count_rows(engine, auth_sessions) == 1
 
 
def test_composite_device_foreign_key_rejects_another_users_device(engine):
    a = login(engine, sub="sub-A", install="A", hash_label="A")
    b = login(engine, sub="sub-B", install="B", hash_label="B")
    with pytest.raises(IntegrityError) as error:
        with engine.begin() as connection:
            connection.execute(insert(auth_sessions).values(
                user_id=a.user_id, device_id=b.device_id,
                refresh_token_hash=token_hash("cross-device"),
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ))
    assert getattr(error.value.orig, "sqlstate", None) == "23503"
    assert violated_constraint(error.value) == "fk_auth_device_same_user"
    assert count_rows(engine, auth_sessions) == 2
 
 
def test_composite_call_foreign_key_rejects_another_users_session(engine):
    a = login(engine, sub="sub-A", install="A", hash_label="A")
    b = login(engine, sub="sub-B", install="B", hash_label="B")
    with pytest.raises(IntegrityError) as error:
        with engine.begin() as connection:
            connection.execute(insert(call_sessions).values(
                user_id=a.user_id, auth_session_id=b.auth_session_id,
                status="starting",
            ))
    assert getattr(error.value.orig, "sqlstate", None) == "23503"
    assert violated_constraint(error.value) == "fk_call_auth_same_user"
    assert count_rows(engine, call_sessions) == 0
 
 
def test_simultaneous_first_signins_recover_with_one_user(engine, monkeypatch):
    # Force both real PostgreSQL transactions to read "not found" before
    # either is allowed to insert. This is a true two-connection race test.
    subject = "same-google-sub-for-two-threads"
    barrier = Barrier(2)
    original = identity_service._lookup_identity
 
    def synchronized_lookup(connection, query_subject):
        found = original(connection, query_subject)
        if query_subject == subject and found is None:
            barrier.wait(timeout=15)
        return found
 
    monkeypatch.setattr(identity_service, "_lookup_identity", synchronized_lookup)
 
    def run_login(number):
        return login(engine, sub=subject,
                     install=f"installation-{number}",
                     hash_label=f"concurrent-{number}")
 
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_login, n) for n in (1, 2)]
        results = [future.result(timeout=30) for future in futures]
 
    assert results[0].user_id == results[1].user_id
    assert results[0].auth_session_id != results[1].auth_session_id
    assert sorted(r.recovered_identity_race for r in results) == [False, True]
    assert count_rows(engine, app_users) == 1  # No orphaned losing user.
    assert count_rows(engine, external_identities) == 1
    assert count_rows(engine, client_devices) == 2
    assert count_rows(engine, auth_sessions) == 2
    assert count_rows(engine, audit_events) == 2
    with engine.connect() as connection:
        outcomes = connection.execute(
            select(audit_events.c["metadata_json"])
        ).scalars().all()
    assert {row["result"] for row in outcomes} == {"created", "race_recovered"}
 
 
def test_two_sessions_on_same_installation_do_not_duplicate_device(engine):
    login(engine, hash_label="first")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(
            login, engine, hash_label=f"parallel-{n}"
        ) for n in (1, 2)]
        results = [future.result(timeout=30) for future in futures]
    assert results[0].user_id == results[1].user_id
    assert count_rows(engine, client_devices) == 1
    assert count_rows(engine, auth_sessions) == 3
 
 
def test_audit_evidence_contains_no_raw_credential_or_google_email(engine):
    login(engine, email="private@example.test")
    with engine.connect() as connection:
        audit = connection.execute(select(audit_events)).mappings().one()
    rendered = repr(dict(audit))
    assert "private@example.test" not in rendered
    assert "mock-google-token" not in rendered
    assert "Bearer " not in rendered
    assert audit["metadata_json"] == {"result": "created"}
