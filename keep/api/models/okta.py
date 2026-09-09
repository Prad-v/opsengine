from typing import Optional

from pydantic import BaseModel, Field, SecretStr


class OktaSettings(BaseModel):
    domain: str = Field(..., description="Okta domain, e.g. https://company.okta.com")
    issuer: str = Field(
        ...,
        description="Okta issuer URL, e.g. https://company.okta.com/oauth2/default",
    )
    client_id: str = Field(..., description="Okta OIDC application client ID")
    client_secret: Optional[SecretStr] = Field(
        default=None, description="Okta OIDC application client secret"
    )
    audience: Optional[str] = Field(
        default=None,
        description="Expected audience claim; defaults to client_id when unset",
    )
    jwks_url: Optional[str] = Field(
        default=None,
        description="Explicit JWKS URL; derived from issuer when unset",
    )

    class Config:
        schema_extra = {
            "example": {
                "domain": "https://company.okta.com",
                "issuer": "https://company.okta.com/oauth2/default",
                "client_id": "0oa1bcdef2ghijklm3n4",
                "client_secret": "abcd1234efgh5678",
                "audience": "",
                "jwks_url": "",
            }
        }


class OktaSettingsResponse(BaseModel):
    configured: bool = False
    domain: Optional[str] = None
    issuer: Optional[str] = None
    client_id: Optional[str] = None
    client_secret_set: bool = False
    audience: Optional[str] = None
    jwks_url: Optional[str] = None
    auth_type: Optional[str] = None
    frontend_env_required: bool = True
    callback_url_hint: Optional[str] = None
