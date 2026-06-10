"""Tests for connection-profile storage and credential encryption."""

import pytest
from pydantic import ValidationError

from src.core.profiles import (
    InMemoryProfileStore,
    JsonFileProfileStore,
    ProfileCreate,
)


def make_create(**overrides) -> ProfileCreate:
    base = dict(
        name="EBS DEV",
        host="db.example.com",
        port=1521,
        service_name="XEPDB1",
        username="reporter",
        password="s3cret",
        environment="DEV",
    )
    base.update(overrides)
    return ProfileCreate(**base)


def test_public_profile_never_exposes_password():
    store = InMemoryProfileStore()
    public = store.create(make_create())
    data = public.model_dump()
    assert "password" not in data
    assert "password_encrypted" not in data
    assert public.id and public.name == "EBS DEV"


def test_resolve_round_trips_password():
    store = InMemoryProfileStore()
    public = store.create(make_create(password="hunter2"))
    resolved = store.resolve(public.id)
    assert resolved is not None
    assert resolved.password == "hunter2"


def test_duplicate_name_rejected():
    store = InMemoryProfileStore()
    store.create(make_create())
    with pytest.raises(ValueError):
        store.create(make_create())


def test_service_or_sid_required():
    with pytest.raises(ValidationError):
        ProfileCreate(name="bad", host="h", username="u", password="p")


def test_delete_semantics():
    store = InMemoryProfileStore()
    public = store.create(make_create())
    assert store.delete(public.id) is True
    assert store.get(public.id) is None
    assert store.delete("does-not-exist") is False


def test_file_store_encrypts_at_rest(tmp_path):
    path = tmp_path / "profiles.json"
    store = JsonFileProfileStore(str(path))
    public = store.create(make_create(password="topsecret"))

    raw = path.read_text(encoding="utf-8")
    assert "topsecret" not in raw  # password is encrypted, not cleartext

    # A fresh instance reading the same file can still decrypt.
    store2 = JsonFileProfileStore(str(path))
    assert store2.resolve(public.id).password == "topsecret"
