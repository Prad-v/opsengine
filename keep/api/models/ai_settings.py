from typing import List, Optional

from pydantic import BaseModel, Field, SecretStr


class AISettings(BaseModel):
    api_key: Optional[SecretStr] = Field(
        default=None, description="OpenAI (or OpenAI-compatible) API key"
    )
    model: Optional[str] = Field(
        default=None, description="Default chat model for AI assistant features"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Optional OpenAI-compatible base URL (e.g. LiteLLM proxy)",
    )
    organization_id: Optional[str] = Field(
        default=None, description="Optional OpenAI organization ID"
    )

    class Config:
        schema_extra = {
            "example": {
                "api_key": "sk-...",
                "model": "gpt-4o-mini",
                "base_url": "",
                "organization_id": "",
            }
        }


class AISettingsResponse(BaseModel):
    configured: bool = False
    api_key_set: bool = False
    model: Optional[str] = None
    base_url: Optional[str] = None
    organization_id: Optional[str] = None
    source: Optional[str] = None
    env_override: bool = False


class AIModelsResponse(BaseModel):
    models: List[str] = Field(default_factory=list)
    source: str = "fallback"


class AIRuntimeSettings(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    organization_id: Optional[str] = None
    source: Optional[str] = None
    configured: bool = False
