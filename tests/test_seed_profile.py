"""Tests for SEED_* env-var connection seeding (env-seed for ephemeral deploys)."""

from src.core.profiles import InMemoryProfileStore, seed_profile_from_env

_SEED_KEYS = (
    "SEED_HOST", "SEED_USERNAME", "SEED_PASSWORD", "SEED_ENGINE", "SEED_DATABASE",
    "SEED_PROFILE_NAME", "SEED_SCHEMA", "SEED_PORT", "SEED_SSLMODE",
    "SEED_ENVIRONMENT", "SEED_SERVICE_NAME", "SEED_SID",
)

PG_ENV = {
    "SEED_HOST": "aws-1-ap-northeast-1.pooler.supabase.com",
    "SEED_USERNAME": "postgres.abc123",
    "SEED_PASSWORD": "s3cret@pw",
    "SEED_ENGINE": "postgres",
    "SEED_DATABASE": "postgres",
    "SEED_PROFILE_NAME": "Supabase",
    "SEED_SCHEMA": "public",
    "SEED_PORT": "5432",
}


def _set_env(monkeypatch, env):
    for k in _SEED_KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_noop_when_seed_vars_unset(monkeypatch):
    _set_env(monkeypatch, {})
    store = InMemoryProfileStore()
    assert seed_profile_from_env(store) is None
    assert store.list() == []


def test_noop_when_password_missing(monkeypatch):
    env = dict(PG_ENV)
    env.pop("SEED_PASSWORD")
    _set_env(monkeypatch, env)
    store = InMemoryProfileStore()
    assert seed_profile_from_env(store) is None
    assert store.list() == []


def test_creates_postgres_profile_from_env(monkeypatch):
    _set_env(monkeypatch, PG_ENV)
    store = InMemoryProfileStore()
    created = seed_profile_from_env(store)
    assert created is not None
    assert created.name == "Supabase"
    assert created.engine == "postgres"
    assert created.database == "postgres"
    assert created.current_schema == "public"
    assert created.port == 5432
    # The password is encrypted at rest; only resolve() returns the plaintext.
    assert "password" not in created.model_dump()
    resolved = store.resolve(created.id)
    assert resolved is not None
    assert resolved.password == "s3cret@pw"
    assert resolved.sslmode == "require"  # defaulted for postgres


def test_seeding_is_idempotent(monkeypatch):
    _set_env(monkeypatch, PG_ENV)
    store = InMemoryProfileStore()
    assert seed_profile_from_env(store) is not None
    # Second boot: existing profile left untouched, no duplicate, no raise.
    assert seed_profile_from_env(store) is None
    assert len(store.list()) == 1


def test_bad_config_does_not_raise(monkeypatch):
    env = dict(PG_ENV)
    env.pop("SEED_DATABASE")  # postgres requires a database name
    _set_env(monkeypatch, env)
    store = InMemoryProfileStore()
    assert seed_profile_from_env(store) is None  # warns + returns None, never raises
    assert store.list() == []


def test_oracle_engine_from_env(monkeypatch):
    _set_env(monkeypatch, {
        "SEED_HOST": "db.example.com",
        "SEED_USERNAME": "reporter",
        "SEED_PASSWORD": "hunter2",
        "SEED_ENGINE": "oracle",
        "SEED_SERVICE_NAME": "XEPDB1",
        "SEED_PROFILE_NAME": "XE",
    })
    store = InMemoryProfileStore()
    created = seed_profile_from_env(store)
    assert created is not None
    assert created.engine == "oracle"
    assert created.service_name == "XEPDB1"
    assert created.port == 1521  # oracle default
