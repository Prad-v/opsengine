import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlmodel import Session, select

from keep.api.bl.approval_bl import ApprovalBl, pending_response
from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.db import get_incident_by_id, get_session
from keep.api.models.action_type import ActionType
from keep.api.models.db.provider import Provider
from keep.api.models.db.temporal_workflow_catalog import (
    DEFAULT_WORKFLOW_ID_TEMPLATE,
    StartTemporalWorkflowRequest,
    TemporalWorkflowCatalog,
    TemporalWorkflowCatalogDtoIn,
    TemporalWorkflowCatalogDtoOut,
    TemporalWorkflowCatalogUpdateDtoIn,
    slugify_catalog_key,
)
from keep.api.models.incident import IncidentDto
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


def _provider_name_map(session: Session, tenant_id: str) -> dict[str, str]:
    providers = session.exec(
        select(Provider).where(Provider.tenant_id == tenant_id)
    ).all()
    return {
        p.id: (p.name or p.id) for p in providers
    }


def _to_dto(
    entry: TemporalWorkflowCatalog, provider_names: dict[str, str]
) -> TemporalWorkflowCatalogDtoOut:
    data = entry.dict()
    data["provider_name"] = provider_names.get(entry.provider_id)
    data["input_mapping"] = entry.input_mapping or {}
    return TemporalWorkflowCatalogDtoOut(**data)


def _get_entry(
    session: Session, tenant_id: str, entry_id: int
) -> TemporalWorkflowCatalog:
    entry = session.exec(
        select(TemporalWorkflowCatalog).where(
            TemporalWorkflowCatalog.id == entry_id,
            TemporalWorkflowCatalog.tenant_id == tenant_id,
        )
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Temporal workflow catalog entry not found")
    return entry


def _get_temporal_provider(tenant_id: str, provider_id: str, session: Session):
    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    try:
        provider = session.exec(
            select(Provider).where(
                (Provider.tenant_id == tenant_id) & (Provider.id == provider_id)
            )
        ).one()
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail="Temporal provider not found") from exc

    if provider.type != "temporal":
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_id}' is type '{provider.type}', expected temporal",
        )

    provider_config = secret_manager.read_secret(
        provider.configuration_key, is_json=True
    )
    return ProvidersFactory.get_provider(
        context_manager, provider.id, provider.type, provider_config
    )


def _entry_as_definition(entry: TemporalWorkflowCatalog) -> dict:
    return {
        "id": entry.catalog_key,
        "name": entry.name,
        "description": entry.description or "",
        "workflow_type": entry.workflow_type,
        "task_queue": entry.task_queue,
        "workflow_id_template": entry.workflow_id_template
        or DEFAULT_WORKFLOW_ID_TEMPLATE,
        "input_mapping": entry.input_mapping or {},
    }


def _allocate_catalog_key(
    session: Session, tenant_id: str, name: str, preferred: str | None = None
) -> str:
    base = slugify_catalog_key(preferred or name)
    candidate = base
    suffix = 2
    while session.exec(
        select(TemporalWorkflowCatalog.id).where(
            TemporalWorkflowCatalog.tenant_id == tenant_id,
            TemporalWorkflowCatalog.catalog_key == candidate,
        )
    ).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


@router.get("", description="List registered Temporal workflows")
def list_temporal_workflows(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> list[TemporalWorkflowCatalogDtoOut]:
    tenant_id = authenticated_entity.tenant_id
    entries = session.exec(
        select(TemporalWorkflowCatalog)
        .where(TemporalWorkflowCatalog.tenant_id == tenant_id)
        .order_by(TemporalWorkflowCatalog.name)
    ).all()
    provider_names = _provider_name_map(session, tenant_id)
    return [_to_dto(entry, provider_names) for entry in entries]


@router.get("/{entry_id}", description="Get a Temporal workflow catalog entry")
def get_temporal_workflow(
    entry_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> TemporalWorkflowCatalogDtoOut:
    entry = _get_entry(session, authenticated_entity.tenant_id, entry_id)
    provider_names = _provider_name_map(session, authenticated_entity.tenant_id)
    return _to_dto(entry, provider_names)


@router.post("", description="Register a Temporal workflow in the catalog")
def create_temporal_workflow(
    body: TemporalWorkflowCatalogDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> TemporalWorkflowCatalogDtoOut:
    tenant_id = authenticated_entity.tenant_id
    # Validate provider exists and is temporal
    _get_temporal_provider(tenant_id, body.provider_id, session)

    now = datetime.now(tz=timezone.utc)
    payload = body.dict()
    payload["input_mapping"] = body.input_mapping or {}
    payload["workflow_id_template"] = (
        body.workflow_id_template or DEFAULT_WORKFLOW_ID_TEMPLATE
    )
    if body.catalog_key:
        # Explicit key from client — must be unique (409 on conflict)
        payload["catalog_key"] = slugify_catalog_key(body.catalog_key)
    else:
        payload["catalog_key"] = _allocate_catalog_key(session, tenant_id, body.name)
    entry = TemporalWorkflowCatalog(
        **payload,
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
            detail=f"Catalog key '{payload['catalog_key']}' already exists for this tenant",
        ) from exc
    session.refresh(entry)
    provider_names = _provider_name_map(session, tenant_id)
    return _to_dto(entry, provider_names)


@router.put("/{entry_id}", description="Update a Temporal workflow catalog entry")
def update_temporal_workflow(
    entry_id: int,
    body: TemporalWorkflowCatalogUpdateDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> TemporalWorkflowCatalogDtoOut:
    tenant_id = authenticated_entity.tenant_id
    entry = _get_entry(session, tenant_id, entry_id)
    _get_temporal_provider(tenant_id, body.provider_id, session)

    # Keep catalog_key stable on edit unless explicitly provided.
    payload = body.dict(exclude_unset=False)
    if not payload.get("catalog_key"):
        payload["catalog_key"] = entry.catalog_key
    payload["workflow_id_template"] = (
        payload.get("workflow_id_template") or DEFAULT_WORKFLOW_ID_TEMPLATE
    )
    payload["input_mapping"] = body.input_mapping or {}

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
            detail=f"Catalog key '{payload['catalog_key']}' already exists for this tenant",
        ) from exc
    session.refresh(entry)
    provider_names = _provider_name_map(session, tenant_id)
    return _to_dto(entry, provider_names)


@router.delete("/{entry_id}", description="Delete a Temporal workflow catalog entry")
def delete_temporal_workflow(
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
        title=f"Delete Temporal catalog {entry.catalog_key}",
        payload={"resource_type": "temporal_catalog", "resource_id": str(entry_id)},
        resource_type="temporal_catalog",
        resource_id=str(entry_id),
        callback={"kind": "keep_action"},
        idempotency_key=f"delete:temporal_catalog:{entry_id}",
    )
    if gate.pending:
        return pending_response(gate.request)
    session.delete(entry)
    session.commit()
    return {"message": "Temporal workflow catalog entry deleted successfully"}


@router.post(
    "/{entry_id}/start",
    description="Start a registered Temporal workflow for an incident and link the run",
)
def start_temporal_workflow_for_incident(
    entry_id: int,
    body: StartTemporalWorkflowRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:incident"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    entry = _get_entry(session, tenant_id, entry_id)
    if entry.disabled:
        raise HTTPException(status_code=400, detail="Catalog entry is disabled")

    incident = get_incident_by_id(tenant_id=tenant_id, incident_id=body.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident_dto = IncidentDto.from_db_incident(incident)
    incident_payload = incident_dto.dict()
    incident_payload["name"] = (
        incident_dto.user_generated_name or incident_dto.ai_generated_name
    )

    provider = _get_temporal_provider(tenant_id, entry.provider_id, session)
    try:
        result = provider.start_workflow_from_definition(
            _entry_as_definition(entry),
            incident=incident_payload,
        )
    except Exception as exc:
        logger.exception(
            "Failed to start Temporal workflow from catalog",
            extra={
                "entry_id": entry_id,
                "incident_id": body.incident_id,
                "tenant_id": tenant_id,
            },
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    linked = {
        "catalog_id": entry.catalog_key,
        "catalog_db_id": entry.id,
        "catalog_name": entry.name,
        "workflow_id": result.get("workflow_id"),
        "run_id": result.get("run_id"),
        "workflow_type": result.get("workflow_type") or entry.workflow_type,
        "task_queue": result.get("task_queue") or entry.task_queue,
        "namespace": result.get("namespace"),
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    previous = []
    if getattr(incident_dto, "enrichments", None):
        previous = list(incident_dto.enrichments.get("temporal_workflows") or [])
    next_runs = [
        item
        for item in previous
        if not (
            item.get("catalog_id") == linked["catalog_id"]
            and item.get("workflow_id") == linked["workflow_id"]
        )
    ]
    next_runs.append(linked)

    enrichment_bl = EnrichmentsBl(tenant_id, session)
    enrichment_bl.enrich_entity(
        fingerprint=body.incident_id,
        enrichments={
            "temporal_workflows": next_runs,
            "temporal_last_workflow_id": linked["workflow_id"],
            "temporal_last_run_id": linked.get("run_id"),
            "temporal_last_catalog_id": entry.catalog_key,
        },
        action_type=ActionType.INCIDENT_ENRICH,
        action_callee=authenticated_entity.email,
        action_description=(
            f"Started Temporal workflow {linked['workflow_id']} "
            f"from catalog '{entry.catalog_key}'"
        ),
        force=True,
    )

    return {
        **result,
        "catalog_db_id": entry.id,
        "catalog_id": entry.catalog_key,
        "catalog_name": entry.name,
        "incident_id": str(body.incident_id),
    }
