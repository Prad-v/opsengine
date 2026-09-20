import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.bl.approval_bl import ApprovalBl, pending_response
from keep.api.core.db import get_session, get_workflow_by_id
from keep.api.models.db.alert_catalog import (
    AlertCatalog,
    AlertCatalogDtoIn,
    AlertCatalogDtoOut,
    AlertCatalogUpdateDtoIn,
    EnhanceAlertCatalogDescriptionDtoIn,
    EnhanceAlertCatalogDescriptionDtoOut,
)
from keep.api.utils.ai_utils import get_ai_temperature_kwargs
from keep.api.utils.openai_config import get_openai_client_for_tenant
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_dto(entry: AlertCatalog) -> AlertCatalogDtoOut:
    return AlertCatalogDtoOut(**entry.dict())


def _get_entry(session: Session, tenant_id: str, entry_id: int) -> AlertCatalog:
    entry = session.exec(
        select(AlertCatalog).where(
            AlertCatalog.id == entry_id,
            AlertCatalog.tenant_id == tenant_id,
        )
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Alert catalog entry not found")
    return entry


def _validate_workflow(tenant_id: str, workflow_id: str | None) -> None:
    if not workflow_id:
        return
    workflow = get_workflow_by_id(tenant_id, workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=400, detail=f"Keep workflow '{workflow_id}' not found"
        )


@router.get("", description="List reserved alert codes")
def list_alert_catalog(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> list[AlertCatalogDtoOut]:
    entries = session.exec(
        select(AlertCatalog)
        .where(AlertCatalog.tenant_id == authenticated_entity.tenant_id)
        .order_by(AlertCatalog.code)
    ).all()
    return [_to_dto(entry) for entry in entries]


@router.post(
    "/enhance-description",
    description="Enhance an alert-code description using Settings → AI",
)
def enhance_alert_catalog_description(
    body: EnhanceAlertCatalogDescriptionDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
) -> EnhanceAlertCatalogDescriptionDtoOut:
    client, model, _runtime = get_openai_client_for_tenant(
        authenticated_entity.tenant_id
    )
    if client is None:
        raise HTTPException(
            status_code=400,
            detail="AI is not configured. Add an API key under Settings → AI.",
        )

    draft = (body.description or "").strip()
    context_lines = []
    if body.code:
        context_lines.append(f"Reserved alert code: {body.code}")
    if body.name:
        context_lines.append(f"Catalog name: {body.name}")
    if body.runbook_url:
        context_lines.append(f"Runbook URL: {body.runbook_url}")
    if body.keep_workflow_id:
        context_lines.append(f"Linked Keep workflow: {body.keep_workflow_id}")
    if draft:
        context_lines.append(f"User draft:\n{draft}")
    if not context_lines:
        raise HTTPException(
            status_code=400,
            detail="Provide a code, name, or draft description to enhance.",
        )

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write operational catalog descriptions for Keep alert codes. "
                        "Turn the user's notes into 2-4 clear sentences: when this code fires, "
                        "typical impact, and what automation or runbook should run. "
                        "Keep the reserved code unchanged. Do not invent a new code. "
                        "Do not use markdown headings or bullet lists. Return only the description."
                    ),
                },
                {
                    "role": "user",
                    "content": "\n".join(context_lines),
                },
            ],
            max_tokens=280,
            **get_ai_temperature_kwargs(0.4),
        )
    except Exception as exc:
        logger.exception("Failed to enhance alert catalog description")
        raise HTTPException(
            status_code=400,
            detail=f"AI enhancement failed: {exc}",
        ) from exc

    text = ""
    if completion.choices:
        text = (completion.choices[0].message.content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="AI returned an empty description")
    return EnhanceAlertCatalogDescriptionDtoOut(description=text, model=model)


@router.get("/{entry_id}", description="Get an alert catalog entry")
def get_alert_catalog(
    entry_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> AlertCatalogDtoOut:
    return _to_dto(_get_entry(session, authenticated_entity.tenant_id, entry_id))


@router.post("", description="Register a reserved alert code")
def create_alert_catalog(
    body: AlertCatalogDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> AlertCatalogDtoOut:
    tenant_id = authenticated_entity.tenant_id
    _validate_workflow(tenant_id, body.keep_workflow_id)
    now = datetime.now(tz=timezone.utc)
    entry = AlertCatalog(
        **body.dict(),
        tenant_id=tenant_id,
        created_by=authenticated_entity.email,
        created_at=now,
        updated_at=now,
    )
    session.add(entry)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Alert code '{body.code}' already exists for this tenant",
        ) from exc
    session.refresh(entry)
    return _to_dto(entry)


@router.put("/{entry_id}", description="Update an alert catalog entry")
def update_alert_catalog(
    entry_id: int,
    body: AlertCatalogUpdateDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> AlertCatalogDtoOut:
    tenant_id = authenticated_entity.tenant_id
    entry = _get_entry(session, tenant_id, entry_id)
    _validate_workflow(tenant_id, body.keep_workflow_id)
    payload = body.dict()
    for key, value in payload.items():
        setattr(entry, key, value)
    entry.updated_by = authenticated_entity.email
    entry.updated_at = datetime.now(tz=timezone.utc)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Alert code '{payload['code']}' already exists for this tenant",
        ) from exc
    session.refresh(entry)
    return _to_dto(entry)


@router.delete("/{entry_id}", description="Delete an alert catalog entry")
def delete_alert_catalog(
    entry_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    entry = _get_entry(session, authenticated_entity.tenant_id, entry_id)
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    gate = bl.gate(
        action_type="delete_resource",
        requested_by=authenticated_entity.email,
        title=f"Delete alert code {entry.code}",
        payload={"resource_type": "alert_catalog", "resource_id": str(entry_id)},
        resource_type="alert_catalog",
        resource_id=str(entry_id),
        callback={"kind": "keep_action"},
        idempotency_key=f"delete:alert_catalog:{entry_id}",
    )
    if gate.pending:
        return pending_response(gate.request)
    session.delete(entry)
    session.commit()
    return {"message": "Alert catalog entry deleted successfully"}
