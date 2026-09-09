"""Helpers for reading/writing Okta auth settings from the secret manager."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)

OKTA_SECRET_SUFFIX = "_okta"


def _secret_name(tenant_id: str) -> str:
    return f"{tenant_id}{OKTA_SECRET_SUFFIX}"


def _normalize_issuer(issuer: Optional[str]) -> Optional[str]:
    if issuer and issuer.endswith("/"):
        return issuer[:-1]
    return issuer


def _from_env() -> dict[str, Any]:
    domain = os.environ.get("OKTA_DOMAIN")
    issuer = _normalize_issuer(os.environ.get("OKTA_ISSUER"))
    client_id = os.environ.get("OKTA_CLIENT_ID")
    client_secret = os.environ.get("OKTA_CLIENT_SECRET")
    audience = os.environ.get("OKTA_AUDIENCE") or None
    jwks_url = os.environ.get("OKTA_JWKS_URL") or None

    if not any([domain, issuer, client_id, client_secret]):
        return {}

    return {
        "domain": domain,
        "issuer": issuer,
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": audience,
        "jwks_url": jwks_url,
        "source": "env",
    }


def read_okta_settings(
    tenant_id: str = SINGLE_TENANT_UUID, *, prefer_secret: bool = True
) -> dict[str, Any]:
    """
    Load Okta settings.

    Preference order:
    1. Secret manager (when prefer_secret=True and secret exists)
    2. Environment variables
    """
    env_settings = _from_env()
    try:
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        raw = secret_manager.read_secret(secret_name=_secret_name(tenant_id))
        stored = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(stored, dict) and stored.get("client_id"):
            stored["issuer"] = _normalize_issuer(stored.get("issuer"))
            stored["source"] = "secret"
            if prefer_secret:
                # Fill gaps from env (e.g. secret without optional fields)
                for key, value in env_settings.items():
                    if key == "source":
                        continue
                    if not stored.get(key) and value:
                        stored[key] = value
                return stored
    except Exception:
        logger.debug("No Okta settings found in secret manager", exc_info=True)

    return env_settings


def write_okta_settings(tenant_id: str, settings: dict[str, Any]) -> None:
    payload = {
        "domain": settings["domain"].rstrip("/"),
        "issuer": _normalize_issuer(settings["issuer"]),
        "client_id": settings["client_id"],
        "client_secret": settings.get("client_secret") or "",
        "audience": settings.get("audience") or "",
        "jwks_url": settings.get("jwks_url") or "",
    }
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_manager.write_secret(
        secret_name=_secret_name(tenant_id), secret_value=json.dumps(payload)
    )


def delete_okta_settings(tenant_id: str) -> None:
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_manager.delete_secret(secret_name=_secret_name(tenant_id))


def mask_okta_settings(settings: dict[str, Any], auth_type: str | None = None) -> dict:
    if not settings:
        return {
            "configured": False,
            "domain": None,
            "issuer": None,
            "client_id": None,
            "client_secret_set": False,
            "audience": None,
            "jwks_url": None,
            "auth_type": auth_type,
            "frontend_env_required": True,
            "callback_url_hint": "/api/auth/callback/okta",
        }

    return {
        "configured": bool(settings.get("client_id") and settings.get("issuer")),
        "domain": settings.get("domain"),
        "issuer": settings.get("issuer"),
        "client_id": settings.get("client_id"),
        "client_secret_set": bool(settings.get("client_secret")),
        "audience": settings.get("audience") or None,
        "jwks_url": settings.get("jwks_url") or None,
        "auth_type": auth_type,
        "frontend_env_required": True,
        "callback_url_hint": "/api/auth/callback/okta",
    }


def get_okta_config_value(key: str, tenant_id: str = SINGLE_TENANT_UUID) -> Optional[str]:
    settings = read_okta_settings(tenant_id)
    value = settings.get(key)
    return value if value else None
