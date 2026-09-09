"""Tests for Settings → Auth → Okta configuration and DB first-login password change."""

import hashlib
import json

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import client, test_app  # noqa


def _create_db_user(
    db_session, username, password, role="admin", must_change_password=False
):
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
def test_signin_returns_must_change_password_flag(db_session, client, test_app):
    _create_db_user(
        db_session, "admin", "admin", must_change_password=True
    )
    response = _signin(client, "admin", "admin")
    assert response.status_code == 200
    body = response.json()
    assert body["mustChangePassword"] is True
    assert body["email"] == "admin"


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_change_password_clears_must_change_flag(db_session, client, test_app):
    _create_db_user(
        db_session, "admin", "admin", must_change_password=True
    )
    signin = _signin(client, "admin", "admin")
    token = signin.json()["accessToken"]

    response = client.put(
        "/auth/users/me/password",
        json={"current_password": "admin", "new_password": "securepass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["mustChangePassword"] is False

    second = _signin(client, "admin", "securepass")
    assert second.status_code == 200
    assert second.json()["mustChangePassword"] is False


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_admin_password_reset_forces_must_change(db_session, client, test_app):
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    _create_db_user(db_session, "managed_user", "initialpass", role="noc")

    token = _signin(client, "admin_user", "adminpass").json()["accessToken"]
    response = client.put(
        "/auth/users/managed_user",
        json={"password": "resetpass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    managed_signin = _signin(client, "managed_user", "resetpass")
    assert managed_signin.status_code == 200
    assert managed_signin.json()["mustChangePassword"] is True


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_okta_settings_crud(db_session, client, test_app, monkeypatch):
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

    empty = client.get("/settings/auth/okta", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["configured"] is False

    save = client.post(
        "/settings/auth/okta",
        headers=headers,
        json={
            "domain": "https://company.okta.com",
            "issuer": "https://company.okta.com/oauth2/default",
            "client_id": "0oaclient",
            "client_secret": "supersecret",
            "audience": "",
            "jwks_url": "",
        },
    )
    assert save.status_code == 200
    assert save.json()["settings"]["configured"] is True
    assert save.json()["settings"]["client_secret_set"] is True
    assert "client_secret" not in save.json()["settings"] or save.json()[
        "settings"
    ].get("client_secret") in (None, "")

    stored = json.loads(store[f"{SINGLE_TENANT_UUID}_okta"])
    assert stored["client_id"] == "0oaclient"
    assert stored["client_secret"] == "supersecret"

    # Update without sending secret should keep previous secret
    update = client.post(
        "/settings/auth/okta",
        headers=headers,
        json={
            "domain": "https://company.okta.com",
            "issuer": "https://company.okta.com/oauth2/default",
            "client_id": "0oaclient2",
        },
    )
    assert update.status_code == 200
    stored = json.loads(store[f"{SINGLE_TENANT_UUID}_okta"])
    assert stored["client_id"] == "0oaclient2"
    assert stored["client_secret"] == "supersecret"

    deleted = client.delete("/settings/auth/okta", headers=headers)
    assert deleted.status_code == 200
    assert f"{SINGLE_TENANT_UUID}_okta" not in store


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_db_auth_settings_endpoint(db_session, client, test_app):
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    token = _signin(client, "admin_user", "adminpass").json()["accessToken"]
    response = client.get(
        "/settings/auth/db",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["password_change_supported"] is True
