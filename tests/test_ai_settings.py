"""Tests for Settings → AI (OpenAI) configuration."""

import json

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import client, test_app  # noqa


def _create_db_user(
    db_session, username, password, role="admin", must_change_password=False
):
    import hashlib

    from keep.api.models.db.user import User

    db_session.add(
        User(
            tenant_id=SINGLE_TENANT_UUID,
            username=username,
            password_hash=hashlib.sha256(password.encode()).hexdigest(),
            role=role,
            must_change_password=must_change_password,
        )
    )
    db_session.commit()


def _signin(client, username, password):
    return client.post(
        "/signin",
        json={"username": username, "password": password},
    )


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_ai_settings_crud(db_session, client, test_app, monkeypatch):
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    token = _signin(client, "admin_user", "adminpass").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    store = {}

    class FakeSecretManager:
        def write_secret(self, secret_name, secret_value):
            store[secret_name] = secret_value

        def read_secret(self, secret_name, **kwargs):
            if secret_name not in store:
                raise Exception("not found")
            return store[secret_name]

        def delete_secret(self, secret_name):
            if secret_name not in store:
                raise Exception("not found")
            del store[secret_name]

    monkeypatch.setattr(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager",
        lambda *args, **kwargs: FakeSecretManager(),
    )
    # Ensure env does not override secret manager in this test
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_API_KEY", raising=False)

    empty = client.get("/settings/ai", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["configured"] is False
    assert empty.json()["api_key_set"] is False

    save = client.post(
        "/settings/ai",
        headers=headers,
        json={
            "api_key": "sk-test-key",
            "model": "gpt-4o-mini",
            "base_url": "",
            "organization_id": "",
        },
    )
    assert save.status_code == 200
    assert save.json()["settings"]["configured"] is True
    assert save.json()["settings"]["api_key_set"] is True
    assert save.json()["settings"]["model"] == "gpt-4o-mini"
    assert "api_key" not in save.json()["settings"] or save.json()[
        "settings"
    ].get("api_key") in (None, "")

    stored = json.loads(store[f"{SINGLE_TENANT_UUID}_openai"])
    assert stored["api_key"] == "sk-test-key"
    assert stored["model"] == "gpt-4o-mini"

    # Update model without re-sending secret should keep previous key
    update = client.post(
        "/settings/ai",
        headers=headers,
        json={
            "model": "gpt-4o",
        },
    )
    assert update.status_code == 200
    stored = json.loads(store[f"{SINGLE_TENANT_UUID}_openai"])
    assert stored["api_key"] == "sk-test-key"
    assert stored["model"] == "gpt-4o"

    runtime = client.get("/settings/ai/runtime", headers=headers)
    assert runtime.status_code == 200
    assert runtime.json()["configured"] is True
    assert runtime.json()["api_key"] == "sk-test-key"
    assert runtime.json()["model"] == "gpt-4o"

    models = client.get("/settings/ai/models", headers=headers)
    assert models.status_code == 200
    assert "models" in models.json()
    assert isinstance(models.json()["models"], list)
    assert len(models.json()["models"]) > 0

    deleted = client.delete("/settings/ai", headers=headers)
    assert deleted.status_code == 200
    assert f"{SINGLE_TENANT_UUID}_openai" not in store

    after = client.get("/settings/ai", headers=headers)
    assert after.status_code == 200
    assert after.json()["configured"] is False


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_ai_settings_requires_api_key_on_first_save(
    db_session, client, test_app, monkeypatch
):
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    token = _signin(client, "admin_user", "adminpass").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    store = {}

    class FakeSecretManager:
        def write_secret(self, secret_name, secret_value):
            store[secret_name] = secret_value

        def read_secret(self, secret_name, **kwargs):
            if secret_name not in store:
                raise Exception("not found")
            return store[secret_name]

        def delete_secret(self, secret_name):
            if secret_name not in store:
                raise Exception("not found")
            del store[secret_name]

    monkeypatch.setattr(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager",
        lambda *args, **kwargs: FakeSecretManager(),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_API_KEY", raising=False)

    response = client.post(
        "/settings/ai",
        headers=headers,
        json={"model": "gpt-4o-mini"},
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_ai_settings_test_connectivity(db_session, client, test_app, monkeypatch):
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    token = _signin(client, "admin_user", "adminpass").json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    store = {}

    class FakeSecretManager:
        def write_secret(self, secret_name, secret_value):
            store[secret_name] = secret_value

        def read_secret(self, secret_name, **kwargs):
            if secret_name not in store:
                raise Exception("not found")
            return store[secret_name]

        def delete_secret(self, secret_name):
            if secret_name not in store:
                raise Exception("not found")
            del store[secret_name]

    monkeypatch.setattr(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager",
        lambda *args, **kwargs: FakeSecretManager(),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPEN_AI_API_KEY", raising=False)

    def fake_success(**kwargs):
        return {
            "success": True,
            "message": "Connected successfully.",
            "details": {"model": kwargs.get("model"), "models_visible": 3},
        }

    monkeypatch.setattr(
        "keep.api.utils.openai_config.test_openai_connectivity",
        fake_success,
    )

    # Save first so stored key can be used when form key is blank
    client.post(
        "/settings/ai",
        headers=headers,
        json={"api_key": "sk-test-key", "model": "gpt-4o"},
    )

    response = client.post(
        "/settings/ai/test",
        headers=headers,
        json={"model": "gpt-4o"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    def fake_failure(**kwargs):
        return {
            "success": False,
            "message": "Invalid API key",
            "details": None,
        }

    monkeypatch.setattr(
        "keep.api.utils.openai_config.test_openai_connectivity",
        fake_failure,
    )
    failed = client.post(
        "/settings/ai/test",
        headers=headers,
        json={"api_key": "sk-bad", "model": "gpt-4o"},
    )
    assert failed.status_code == 400
    assert failed.json()["success"] is False
    assert "Invalid API key" in failed.json()["message"]
