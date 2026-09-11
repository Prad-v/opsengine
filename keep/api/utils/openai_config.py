"""Helpers for reading/writing OpenAI settings from the secret manager."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.contextmanager.contextmanager import ContextManager
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

logger = logging.getLogger(__name__)

OPENAI_SECRET_SUFFIX = "_openai"

# Curated chat models shown when the Models API is unavailable
DEFAULT_CHAT_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o4-mini",
    "o3-mini",
    "o3",
    "chatgpt-4o-latest",
]


def _secret_name(tenant_id: str) -> str:
    return f"{tenant_id}{OPENAI_SECRET_SUFFIX}"


def _from_env() -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_API_KEY")
    model = os.environ.get("OPENAI_MODEL_NAME") or None
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    organization_id = os.environ.get("OPEN_AI_ORGANIZATION_ID") or None

    if not any([api_key, model, base_url, organization_id]):
        return {}

    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "organization_id": organization_id,
        "source": "env",
    }


def read_openai_settings(
    tenant_id: str = SINGLE_TENANT_UUID, *, prefer_secret: bool = True
) -> dict[str, Any]:
    """
    Load OpenAI settings.

    Preference order:
    1. Secret manager (when prefer_secret=True and secret exists with api_key)
    2. Environment variables
    """
    env_settings = _from_env()
    try:
        context_manager = ContextManager(tenant_id=tenant_id)
        secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
        raw = secret_manager.read_secret(secret_name=_secret_name(tenant_id))
        stored = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(stored, dict) and stored.get("api_key"):
            stored["source"] = "secret"
            if prefer_secret:
                for key, value in env_settings.items():
                    if key == "source":
                        continue
                    if not stored.get(key) and value:
                        stored[key] = value
                return stored
    except Exception:
        logger.debug("No OpenAI settings found in secret manager", exc_info=True)

    return env_settings


def write_openai_settings(tenant_id: str, settings: dict[str, Any]) -> None:
    payload = {
        "api_key": settings.get("api_key") or "",
        "model": (settings.get("model") or "").strip(),
        "base_url": (settings.get("base_url") or "").strip(),
        "organization_id": (settings.get("organization_id") or "").strip(),
    }
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_manager.write_secret(
        secret_name=_secret_name(tenant_id), secret_value=json.dumps(payload)
    )


def delete_openai_settings(tenant_id: str) -> None:
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    secret_manager.delete_secret(secret_name=_secret_name(tenant_id))


def mask_openai_settings(settings: dict[str, Any]) -> dict[str, Any]:
    env_settings = _from_env()
    env_override = bool(env_settings.get("api_key")) and (
        not settings or settings.get("source") == "env"
    )

    if not settings or not settings.get("api_key"):
        return {
            "configured": False,
            "api_key_set": False,
            "model": None,
            "base_url": None,
            "organization_id": None,
            "source": None,
            "env_override": bool(env_settings.get("api_key")),
        }

    return {
        "configured": True,
        "api_key_set": True,
        "model": settings.get("model") or None,
        "base_url": settings.get("base_url") or None,
        "organization_id": settings.get("organization_id") or None,
        "source": settings.get("source"),
        "env_override": env_override,
    }


def get_runtime_openai_settings(tenant_id: str = SINGLE_TENANT_UUID) -> dict[str, Any]:
    """Return credentials for server-side AI (CopilotKit / backend LLM calls).

    Env API key wins when set (ops override); otherwise tenant secret is used.
    """
    env_settings = _from_env()
    if env_settings.get("api_key"):
        return {
            "api_key": env_settings.get("api_key"),
            "model": env_settings.get("model"),
            "base_url": env_settings.get("base_url"),
            "organization_id": env_settings.get("organization_id"),
            "source": "env",
            "configured": True,
        }

    settings = read_openai_settings(tenant_id, prefer_secret=True)
    if not settings.get("api_key"):
        return {
            "api_key": None,
            "model": None,
            "base_url": None,
            "organization_id": None,
            "source": None,
            "configured": False,
        }

    return {
        "api_key": settings.get("api_key"),
        "model": settings.get("model") or None,
        "base_url": settings.get("base_url") or None,
        "organization_id": settings.get("organization_id") or None,
        "source": settings.get("source") or "secret",
        "configured": True,
    }


def _is_chat_model(model_id: str) -> bool:
    mid = model_id.lower()
    if any(
        skip in mid
        for skip in (
            "embedding",
            "whisper",
            "tts",
            "dall-e",
            "davinci",
            "babbage",
            "moderation",
            "transcribe",
            "realtime",
            "audio",
            "image",
        )
    ):
        return False
    return mid.startswith(
        ("gpt-", "o1", "o3", "o4", "chatgpt-", "ft:")
    ) or mid in {"gpt-4o", "gpt-4o-mini"}


def list_openai_models(
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> dict[str, Any]:
    """List chat-capable models from OpenAI (or compatible) API."""
    if not api_key:
        return {"models": list(DEFAULT_CHAT_MODELS), "source": "fallback"}

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            organization=organization_id or None,
            **({"base_url": base_url} if base_url else {}),
        )
        response = client.models.list()
        models = sorted(
            {m.id for m in response.data if _is_chat_model(m.id)},
            key=lambda x: x.lower(),
        )
        if not models:
            return {"models": list(DEFAULT_CHAT_MODELS), "source": "fallback"}
        # Prefer curated models first when present
        preferred = [m for m in DEFAULT_CHAT_MODELS if m in models]
        others = [m for m in models if m not in preferred]
        return {"models": preferred + others, "source": "api"}
    except Exception:
        logger.warning("Failed to list OpenAI models; using fallback", exc_info=True)
        return {"models": list(DEFAULT_CHAT_MODELS), "source": "fallback"}


def test_openai_connectivity(
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> dict[str, Any]:
    """Validate API credentials with a models list + optional tiny chat call."""
    if not api_key:
        return {
            "success": False,
            "message": "API key is required to test connectivity",
            "details": None,
        }

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            organization=organization_id or None,
            **({"base_url": base_url} if base_url else {}),
        )
        models_response = client.models.list()
        model_ids = [m.id for m in models_response.data]
        details = {
            "models_visible": len(model_ids),
            "base_url": base_url or "https://api.openai.com/v1",
        }

        selected_model = (model or "").strip() or "gpt-4o-mini"
        details["model"] = selected_model

        # Minimal completion to verify the selected model accepts chat requests
        completion = client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        reply = ""
        if completion.choices:
            reply = (completion.choices[0].message.content or "").strip()
        details["completion_ok"] = True
        details["sample_reply"] = reply[:80] if reply else None

        return {
            "success": True,
            "message": (
                f"Connected successfully. Model '{selected_model}' responded "
                f"({len(model_ids)} models visible)."
            ),
            "details": details,
        }
    except Exception as exc:
        logger.warning("OpenAI connectivity test failed", exc_info=True)
        return {
            "success": False,
            "message": str(exc) or "Connectivity test failed",
            "details": {
                "model": (model or "").strip() or None,
                "base_url": base_url or "https://api.openai.com/v1",
            },
        }
