import os

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.user import Group, Role, User
from keep.api.utils.okta_config import read_okta_settings
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.identity_managers.okta.okta_authverifier import OktaAuthVerifier
from keep.identitymanager.identitymanager import BaseIdentityManager


class OktaIdentityManager(BaseIdentityManager):
    """
    Identity manager implementation for Okta.
    Authentication works but management functions are disabled.
    Configuration is read from Settings → Auth → Okta (secret manager)
    with environment variable fallback.
    """

    def __init__(self, tenant_id, context_manager: ContextManager, **kwargs):
        super().__init__(tenant_id, context_manager, **kwargs)
        settings = read_okta_settings(tenant_id or SINGLE_TENANT_UUID)

        self.okta_domain = settings.get("domain") or os.environ.get("OKTA_DOMAIN")
        self.okta_issuer = settings.get("issuer") or os.environ.get("OKTA_ISSUER")
        self.okta_client_id = settings.get("client_id") or os.environ.get(
            "OKTA_CLIENT_ID"
        )
        self.okta_client_secret = settings.get("client_secret") or os.environ.get(
            "OKTA_CLIENT_SECRET"
        )
        self.okta_api_token = os.environ.get("OKTA_API_TOKEN")

        if not all(
            [
                self.okta_domain,
                self.okta_issuer,
                self.okta_client_id,
                self.okta_client_secret,
            ]
        ):
            missing_vars = []
            if not self.okta_domain:
                missing_vars.append("OKTA_DOMAIN (or Settings → Auth → Okta)")
            if not self.okta_issuer:
                missing_vars.append("OKTA_ISSUER (or Settings → Auth → Okta)")
            if not self.okta_client_id:
                missing_vars.append("OKTA_CLIENT_ID (or Settings → Auth → Okta)")
            if not self.okta_client_secret:
                missing_vars.append("OKTA_CLIENT_SECRET (or Settings → Auth → Okta)")

            self.logger.error(
                f"Missing Okta configuration: {', '.join(missing_vars)}"
            )
            raise Exception(f"Missing Okta configuration: {', '.join(missing_vars)}")

        if self.okta_issuer.endswith("/"):
            self.okta_issuer = self.okta_issuer[:-1]

        self.logger.info(
            "Okta Identity Manager initialized (management functions disabled)"
        )

    def on_start(self, app) -> None:
        self.logger.info("Okta Identity Manager started (roles creation disabled)")

    @property
    def support_sso(self) -> bool:
        return True

    def get_sso_providers(self) -> list[str]:
        return ["okta"]

    def get_sso_wizard_url(self, authenticated_entity: AuthenticatedEntity) -> str:
        return ""

    def get_users(self) -> list[User]:
        self.logger.info("get_users called but management functions are disabled")
        return []

    def create_user(
        self, user_email: str, user_name: str, password: str, role: str, groups: list[str] = []
    ) -> dict:
        self.logger.info("create_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def update_user(self, user_email: str, update_data: dict) -> dict:
        self.logger.info("update_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def delete_user(self, user_email: str) -> dict:
        self.logger.info("delete_user called but management functions are disabled")
        return {"status": "not_implemented", "message": "User management is disabled"}

    def get_auth_verifier(self, scopes: list) -> AuthVerifierBase:
        return OktaAuthVerifier(scopes, tenant_id=self.tenant_id)

    def get_groups(self) -> list[Group]:
        self.logger.info("get_groups called but management functions are disabled")
        return []

    def create_group(self, group_name: str, members: list[str], roles: list[str]) -> None:
        self.logger.info("create_group called but management functions are disabled")
        return None

    def update_group(self, group_name: str, members: list[str], roles: list[str]) -> None:
        self.logger.info("update_group called but management functions are disabled")
        return None

    def delete_group(self, group_name: str) -> None:
        self.logger.info("delete_group called but management functions are disabled")
        return None

    def create_role(self, role: Role, predefined=False) -> str:
        self.logger.info("create_role called but management functions are disabled")
        return ""

    def delete_role(self, role_id: str) -> None:
        self.logger.info("delete_role called but management functions are disabled")
        return None
