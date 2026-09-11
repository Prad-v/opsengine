import io
import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import get_session
from keep.api.core.tenant_configuration import TenantConfiguration
from keep.api.models.alert import AlertDto
from keep.api.models.ai_settings import AISettings
from keep.api.models.okta import OktaSettings
from keep.api.models.smtp import SMTPSettings
from keep.api.models.webhook import WebhookSettings
from keep.api.utils.tenant_utils import (
    APIKeyException,
    create_api_key,
    get_api_key,
    get_api_keys,
    get_api_keys_secret,
    get_or_create_api_key,
    update_api_key_internal,
)
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.identitymanager.rbac import get_role_by_role_name
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()

logger = logging.getLogger(__name__)


class CreateUserRequest(BaseModel):
    email: str = Field(alias="username")
    password: Optional[str] = None  # for auth0 we don't need a password
    role: str

    class Config:
        allow_population_by_field_name = True


@router.get(
    "/webhook",
    description="Get details about the webhook endpoint (e.g. the API url and an API key)",
)
def webhook_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
) -> WebhookSettings:
    tenant_id = authenticated_entity.tenant_id
    logger.info("Getting webhook settings")
    api_url = config("KEEP_API_URL")
    keep_webhook_api_url = f"{api_url}/alerts/event"
    try:
        webhook_api_key = get_or_create_api_key(
            session=session,
            tenant_id=tenant_id,
            created_by="system",
            unique_api_key_id="webhook",
            system_description="Webhooks API key",
        )
    except Exception as e:
        logger.error(f"Error retrieving webhook settings: {str(e)}")
        return JSONResponse(
            status_code=502,
            content={"message": str(e)},
        )
    logger.info("Webhook settings retrieved successfully")
    return WebhookSettings(
        webhookApi=keep_webhook_api_url,
        apiKey=webhook_api_key,
        modelSchema=AlertDto.schema(),
    )


@router.post("/smtp", description="Install or update SMTP settings")
async def update_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Save the SMTP settings in the secret manager
    smtp_settings = smtp_settings.dict()
    smtp_settings["password"] = smtp_settings["password"].get_secret_value()
    secret_manager.write_secret(
        secret_name=f"{tenant_id}_smtp", secret_value=json.dumps(smtp_settings)
    )
    return {"status": "SMTP settings updated successfully"}


@router.get("/smtp", description="Get SMTP settings")
async def get_smtp_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Getting SMTP settings")
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    try:
        smtp_settings = secret_manager.read_secret(secret_name=f"{tenant_id}_smtp")
        smtp_settings = json.loads(smtp_settings)
        logger.info("SMTP settings retrieved successfully")
        return JSONResponse(status_code=200, content=smtp_settings)
    except Exception:
        # everything ok but no smtp settings
        return JSONResponse(status_code=200, content={})


@router.delete("/smtp", description="Delete SMTP settings")
async def delete_smtp_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info("Deleting SMTP settings")
    tenant_id = authenticated_entity.tenant_id
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    # Read the SMTP settings from the secret manager
    secret_manager.delete_secret(secret_name=f"{tenant_id}_smtp")
    logger.info("SMTP settings deleted successfully")
    return JSONResponse(status_code=200, content={})


@router.post("/smtp/test", description="Test SMTP settings")
async def test_smtp_settings(
    smtp_settings: SMTPSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    # Logic to test SMTP settings, perhaps by sending a test email
    # You would use the provided SMTP settings to try and send an email
    success, message, logs = test_smtp_connection(smtp_settings)
    if success:
        return JSONResponse(status_code=200, content={"message": message, "logs": logs})
    else:
        return JSONResponse(status_code=400, content={"message": message, "logs": logs})


def test_smtp_connection(settings: SMTPSettings) -> Tuple[bool, str, str]:
    # Capture the SMTP session output
    log_stream = io.StringIO()
    try:
        # A patched version of smtplib.SMTP that captures the SMTP session output
        logger.info("Testing SMTP")
        server = PatchedSMTP(
            settings.host, settings.port, timeout=10, log_stream=log_stream
        )
        if settings.secure:
            logger.info("Configuring TLS")
            server.starttls()

        if settings.username and settings.password:
            logger.info("Configuring user and pass")
            server.login(settings.username, settings.password.get_secret_value())

        # Create an HTML test email
        html_content = """
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h1 style="color: #333;">SMTP Settings Test</h1>
                    <p style="color: #666;">This is a test email from Keep to verify your SMTP settings.</p>
                    <div style="margin: 20px 0; padding: 15px; background-color: #e8f5e9; border-left: 4px solid #4caf50;">
                        <p style="margin: 0; color: #2e7d32;"><strong>✓ Success!</strong> Your SMTP settings are configured correctly.</p>
                    </div>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>SMTP Server</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Port</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Security</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{}</td>
                        </tr>
                    </table>
                </div>
            </body>
        </html>
        """.format(settings.host, settings.port, "TLS/STARTTLS" if settings.secure else "None")
        
        # Create MIMEText with HTML content
        message = MIMEText(html_content, "html")
        message["From"] = settings.from_email
        message["To"] = settings.to_email
        message["Subject"] = "Test SMTP Settings - Keep"

        logger.info("Sending test email")
        server.sendmail(settings.from_email, [settings.to_email], message.as_string())
        server.quit()
        # Get the SMTP session log
        smtp_log = log_stream.getvalue().splitlines()
        log_stream.close()
        logger.info("Finished to send test email")
        return True, "SMTP settings are correct and an email has been sent.", smtp_log
    except Exception as e:
        logger.exception("Failed to test SMTP")
        return False, str(e), log_stream.getvalue().splitlines()


class PatchedSMTP(smtplib.SMTP):
    debuglevel = 1

    def __init__(
        self,
        host="",
        port=0,
        local_hostname=None,
        timeout=...,
        source_address=None,
        log_stream=None,
    ):
        self.log_stream = log_stream
        super().__init__(host, port, local_hostname, timeout, source_address)

    def _print_debug(self, *args):
        if self.log_stream is not None:
            # Write debug info to the StringIO stream
            self.log_stream.write(" ".join(str(arg) for arg in args) + "\n")
        else:
            super()._print_debug(*args)


@router.post("/apikey", description="Create API key")
async def create_key(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    try:
        identity_manager = IdentityManagerFactory.get_identity_manager(
            tenant_id=authenticated_entity.tenant_id,
        )
        body = await request.json()
        unique_api_key_id = body["name"].replace(" ", "")
        role = identity_manager.get_role_by_role_name(body["role"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    try:
        api_key = create_api_key(
            session=session,
            tenant_id=authenticated_entity.tenant_id,
            created_by=authenticated_entity.email,
            unique_api_key_id=unique_api_key_id,
            role=role.name,
            is_system=False,
        )

        tenant_api_key = get_api_key(
            session,
            unique_api_key_id=unique_api_key_id,
            tenant_id=authenticated_entity.tenant_id,
        )

        return {
            "reference_id": tenant_api_key.reference_id,
            "tenant": tenant_api_key.tenant,
            "is_deleted": tenant_api_key.is_deleted,
            "created_at": tenant_api_key.created_at,
            "created_by": tenant_api_key.created_by,
            "last_used": tenant_api_key.last_used,
            "secret": api_key,
            "role": tenant_api_key.role,
        }
    except APIKeyException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error creating API key: {str(e)}",
        )


@router.get("/apikeys", description="Get API keys")
def get_keys(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    role = get_role_by_role_name(authenticated_entity.role)

    logger.info(f"Getting active API keys for tenant {tenant_id}")

    api_keys = get_api_keys(
        session=session,
        tenant_id=tenant_id,
        email=authenticated_entity.email,
        role=role,
    )

    if api_keys:
        api_keys = get_api_keys_secret(tenant_id=tenant_id, api_keys=api_keys)

    logger.info(
        f"Active API keys for tenant {tenant_id} retrieved successfully",
    )

    return {"apiKeys": api_keys}


@router.put("/apikey", description="Update API key secret")
async def update_api_key(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    try:
        body = await request.json()
        unique_api_key_id = body["apiKeyId"]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    tenant_id = authenticated_entity.tenant_id

    logger.info(
        f"Updating API key ({unique_api_key_id}) secret",
        extra={"tenant_id": tenant_id, "unique_api_key_id": unique_api_key_id},
    )

    api_key = update_api_key_internal(
        session=session,
        tenant_id=tenant_id,
        unique_api_key_id=unique_api_key_id,
    )

    if api_key:
        logger.info(f"Api key ({unique_api_key_id}) secret updated")
        return {"message": "API key secret updated", "apiKey": api_key}
    else:
        logger.info(f"Api key ({unique_api_key_id}) not found")
        raise HTTPException(
            status_code=404, detail=f"API key ({unique_api_key_id}) not found"
        )


@router.delete("/apikey/{keyId}", description="Delete API key")
def delete_api_key(
    keyId: str,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
    session: Session = Depends(get_session),
):
    logger.info(f"Deleting api key ({keyId})")
    tenant_id = authenticated_entity.tenant_id
    api_key = get_api_key(
        session, unique_api_key_id=keyId, tenant_id=authenticated_entity.tenant_id
    )

    if api_key and api_key.is_deleted is False:
        try:
            context_manager = ContextManager(tenant_id=tenant_id)
            secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
            secret_manager.delete_secret(
                secret_name=f"{tenant_id}-{api_key.reference_id}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unable to deactivate Api key ({keyId}) secret. Error: {str(e)}",
            )

        try:
            api_key.is_deleted = True
            session.commit()
        except Exception:
            raise HTTPException(
                status_code=500,
                detail=f"Unable to flag Api key ({keyId}) as deactivated",
            )

        logger.info(f"Api key ({keyId}) has been deactivated")
        return {"message": "Api key has been deactivated"}
    else:
        logger.info(f"Api key ({keyId}) not found")
        raise HTTPException(status_code=404, detail=f"Api key ({keyId}) not found")


@router.get("/sso")
async def get_sso_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    identity_manager = IdentityManagerFactory.get_identity_manager(
        tenant_id=authenticated_entity.tenant_id,
        context_manager=ContextManager(tenant_id=authenticated_entity.tenant_id),
    )

    if identity_manager.support_sso:
        providers = identity_manager.get_sso_providers()
        return {
            "sso": True,
            "providers": providers,
            "wizardUrl": identity_manager.get_sso_wizard_url(authenticated_entity),
        }
    else:
        return {"sso": False}


@router.get("/tenant/configuration")
def get_tenant_configuration(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
) -> dict:
    tenant_id = authenticated_entity.tenant_id
    tenant_configuration = TenantConfiguration()
    config_value = tenant_configuration.get_configuration(tenant_id=tenant_id)
    return JSONResponse(status_code=200, content=config_value)


@router.get("/ai", description="Get OpenAI / AI assistant settings")
async def get_ai_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    from keep.api.utils.openai_config import mask_openai_settings, read_openai_settings

    tenant_id = authenticated_entity.tenant_id
    settings = read_openai_settings(tenant_id)
    return JSONResponse(status_code=200, content=mask_openai_settings(settings))


@router.get(
    "/ai/runtime",
    description="Get OpenAI credentials for server-side AI (env overrides tenant secret)",
)
async def get_ai_runtime_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    from keep.api.utils.openai_config import get_runtime_openai_settings

    tenant_id = authenticated_entity.tenant_id
    return JSONResponse(
        status_code=200, content=get_runtime_openai_settings(tenant_id)
    )


@router.post("/ai", description="Install or update OpenAI / AI assistant settings")
async def update_ai_settings(
    ai_settings: AISettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    from keep.api.utils.openai_config import (
        mask_openai_settings,
        read_openai_settings,
        write_openai_settings,
    )

    tenant_id = authenticated_entity.tenant_id
    existing = read_openai_settings(tenant_id)
    api_key = (
        ai_settings.api_key.get_secret_value() if ai_settings.api_key else None
    )
    if not api_key:
        api_key = existing.get("api_key") or ""
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="API key is required when configuring AI settings",
        )

    write_openai_settings(
        tenant_id,
        {
            "api_key": api_key,
            "model": ai_settings.model or existing.get("model") or "gpt-4o-mini",
            "base_url": ai_settings.base_url
            if ai_settings.base_url is not None
            else existing.get("base_url") or "",
            "organization_id": ai_settings.organization_id
            if ai_settings.organization_id is not None
            else existing.get("organization_id") or "",
        },
    )
    refreshed = read_openai_settings(tenant_id)
    return {
        "status": "AI settings updated successfully",
        "settings": mask_openai_settings(refreshed),
    }


@router.delete("/ai", description="Delete OpenAI / AI assistant settings")
async def delete_ai_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:settings"])
    ),
):
    from keep.api.utils.openai_config import delete_openai_settings

    tenant_id = authenticated_entity.tenant_id
    try:
        delete_openai_settings(tenant_id)
    except Exception as e:
        logger.warning(f"Failed to delete AI settings: {e}")
        raise HTTPException(status_code=404, detail="AI settings not found")
    return JSONResponse(
        status_code=200, content={"status": "AI settings deleted successfully"}
    )


@router.get("/ai/models", description="List available OpenAI chat models")
async def list_ai_models(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    from keep.api.utils.openai_config import (
        get_runtime_openai_settings,
        list_openai_models,
    )

    tenant_id = authenticated_entity.tenant_id
    runtime = get_runtime_openai_settings(tenant_id)
    result = list_openai_models(
        api_key=runtime.get("api_key"),
        base_url=runtime.get("base_url"),
        organization_id=runtime.get("organization_id"),
    )
    return JSONResponse(status_code=200, content=result)


@router.post(
    "/ai/models",
    description="List OpenAI chat models using a candidate API key (before save)",
)
async def list_ai_models_preview(
    ai_settings: AISettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    from keep.api.utils.openai_config import list_openai_models, read_openai_settings

    tenant_id = authenticated_entity.tenant_id
    existing = read_openai_settings(tenant_id)
    api_key = (
        ai_settings.api_key.get_secret_value() if ai_settings.api_key else None
    ) or existing.get("api_key")
    base_url = (
        ai_settings.base_url
        if ai_settings.base_url is not None
        else existing.get("base_url")
    )
    organization_id = (
        ai_settings.organization_id
        if ai_settings.organization_id is not None
        else existing.get("organization_id")
    )
    result = list_openai_models(
        api_key=api_key,
        base_url=base_url or None,
        organization_id=organization_id or None,
    )
    return JSONResponse(status_code=200, content=result)


@router.post("/ai/test", description="Test OpenAI / AI assistant connectivity")
async def test_ai_settings(
    ai_settings: AISettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    from keep.api.utils.openai_config import (
        read_openai_settings,
        test_openai_connectivity,
    )

    tenant_id = authenticated_entity.tenant_id
    existing = read_openai_settings(tenant_id)
    api_key = (
        ai_settings.api_key.get_secret_value() if ai_settings.api_key else None
    ) or existing.get("api_key")
    base_url = (
        ai_settings.base_url
        if ai_settings.base_url is not None
        else existing.get("base_url")
    )
    organization_id = (
        ai_settings.organization_id
        if ai_settings.organization_id is not None
        else existing.get("organization_id")
    )
    model = ai_settings.model or existing.get("model") or "gpt-4o-mini"

    result = test_openai_connectivity(
        api_key=api_key,
        model=model,
        base_url=base_url or None,
        organization_id=organization_id or None,
    )
    status_code = 200 if result.get("success") else 400
    return JSONResponse(status_code=status_code, content=result)


@router.get("/auth/okta", description="Get Okta authentication settings")
async def get_okta_auth_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    from keep.api.utils.okta_config import mask_okta_settings, read_okta_settings

    tenant_id = authenticated_entity.tenant_id
    auth_type = config("AUTH_TYPE", default="")
    settings = read_okta_settings(tenant_id)
    return JSONResponse(
        status_code=200, content=mask_okta_settings(settings, auth_type=auth_type)
    )


@router.post("/auth/okta", description="Install or update Okta authentication settings")
async def update_okta_auth_settings(
    okta_settings: OktaSettings = Body(...),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:settings"])
    ),
):
    from keep.api.utils.okta_config import (
        mask_okta_settings,
        read_okta_settings,
        write_okta_settings,
    )

    tenant_id = authenticated_entity.tenant_id
    existing = read_okta_settings(tenant_id)
    client_secret = (
        okta_settings.client_secret.get_secret_value()
        if okta_settings.client_secret
        else None
    )
    # Keep previously stored secret when the form submits an empty secret
    if not client_secret:
        client_secret = existing.get("client_secret") or ""
    if not client_secret:
        raise HTTPException(
            status_code=400, detail="Client secret is required when configuring Okta"
        )

    write_okta_settings(
        tenant_id,
        {
            "domain": okta_settings.domain,
            "issuer": okta_settings.issuer,
            "client_id": okta_settings.client_id,
            "client_secret": client_secret,
            "audience": okta_settings.audience or "",
            "jwks_url": okta_settings.jwks_url or "",
        },
    )
    auth_type = config("AUTH_TYPE", default="")
    refreshed = read_okta_settings(tenant_id)
    return {
        "status": "Okta settings updated successfully",
        "settings": mask_okta_settings(refreshed, auth_type=auth_type),
        "note": (
            "Backend will use these settings immediately. "
            "Set matching OKTA_* environment variables on the frontend and set "
            "AUTH_TYPE=OKTA, then restart the frontend for sign-in with Okta."
        ),
    }


@router.delete("/auth/okta", description="Delete Okta authentication settings")
async def delete_okta_auth_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["delete:settings"])
    ),
):
    from keep.api.utils.okta_config import delete_okta_settings

    tenant_id = authenticated_entity.tenant_id
    try:
        delete_okta_settings(tenant_id)
    except Exception as e:
        logger.warning(f"Failed to delete Okta settings: {e}")
        raise HTTPException(status_code=404, detail="Okta settings not found")
    return JSONResponse(
        status_code=200, content={"status": "Okta settings deleted successfully"}
    )


@router.get("/auth/db", description="Get DB authentication settings summary")
async def get_db_auth_settings(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:settings"])
    ),
):
    auth_type = config("AUTH_TYPE", default="")
    default_username = config("KEEP_DEFAULT_USERNAME", default="admin")
    return {
        "auth_type": auth_type,
        "enabled": auth_type.lower() in ("db", "single_tenant"),
        "default_username": default_username,
        "password_change_supported": auth_type.lower() in ("db", "single_tenant"),
        "note": (
            "Default credentials are admin/admin on first install. "
            "Users with must_change_password must update their password after first login."
        ),
    }
