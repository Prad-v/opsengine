import logging

import jwt
from fastapi import Depends, HTTPException

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.utils.okta_config import read_okta_settings
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme

logger = logging.getLogger(__name__)

DEFAULT_ROLE_NAME = "noc"


class OktaAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for Okta"""

    def __init__(
        self, scopes: list[str] = [], tenant_id: str = SINGLE_TENANT_UUID
    ) -> None:
        super().__init__(scopes)
        settings = read_okta_settings(tenant_id)

        self.okta_issuer = settings.get("issuer")
        self.okta_audience = settings.get("audience") or None
        self.okta_client_id = settings.get("client_id")
        self.jwks_url = settings.get("jwks_url") or None

        if not self.jwks_url and not self.okta_issuer:
            raise Exception(
                "Missing Okta JWKS URL and issuer. Configure Settings → Auth → Okta "
                "or set OKTA_JWKS_URL / OKTA_ISSUER."
            )

        if self.okta_issuer and self.okta_issuer.endswith("/"):
            self.okta_issuer = self.okta_issuer[:-1]

        if not self.jwks_url:
            self.jwks_url = f"{self.okta_issuer}/.well-known/jwks.json"

        assert self.jwks_url is not None
        self.jwks_client = jwt.PyJWKClient(self.jwks_url)
        logger.info(f"Initialized JWKS client with URL: {self.jwks_url}")

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        if not token:
            raise HTTPException(status_code=401, detail="No token provided")

        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token).key

            payload = jwt.decode(
                token,
                key=signing_key,
                algorithms=["RS256"],
                audience=self.okta_audience or self.okta_client_id,
                issuer=self.okta_issuer,
                options={"verify_exp": True},
            )

            tenant_id = payload.get("keep_tenant_id", "keep")
            email = (
                payload.get("email")
                or payload.get("sub")
                or payload.get("preferred_username")
            )

            groups = payload.get("groups", [])
            role_name = (
                payload.get("keep_role")
                or payload.get("role")
                or (groups[0] if groups else None)
                or DEFAULT_ROLE_NAME
            )

            org_id = payload.get("org_id")
            org_realm = payload.get("org_realm")

            if not email:
                raise HTTPException(status_code=401, detail="No email in token")

            logger.info(f"Successfully verified token for user with email: {email}")
            return AuthenticatedEntity(
                tenant_id=tenant_id,
                email=email,
                role=role_name,
                org_id=org_id,
                org_realm=org_realm,
                token=token,
            )

        except jwt.exceptions.InvalidKeyError as e:
            logger.error(f"Invalid key error during token validation: {str(e)}")
            raise HTTPException(
                status_code=401, detail="Invalid signing key - token validation failed"
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            logger.exception("Failed to validate token")
            raise HTTPException(
                status_code=401, detail=f"Token validation failed: {str(e)}"
            )
