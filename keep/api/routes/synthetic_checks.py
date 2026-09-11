"""CRUD API for Temporal-backed synthetic checks (Mode 1)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlmodel import Session, select

from keep.api.core.db import get_session
from keep.api.models.db.provider import Provider
from keep.api.models.db.synthetic_check import (
    DEFAULT_TASK_QUEUE,
    SyntheticCheck,
    SyntheticCheckDtoIn,
    SyntheticCheckDtoOut,
    SyntheticCheckRunResult,
    SyntheticCheckUpdateDtoIn,
    slugify_check_key,
)
from keep.contextmanager.contextmanager import ContextManager
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.providers.providers_factory import ProvidersFactory
from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)

PROBE_TARGET_GROUP_WORKFLOW = "ProbeTargetGroup"


def _provider_name_map(session: Session, tenant_id: str) -> dict[str, str]:
    providers = session.exec(
        select(Provider).where(Provider.tenant_id == tenant_id)
    ).all()
    return {p.id: (p.name or p.id) for p in providers}


def _to_dto(entry: SyntheticCheck, provider_names: dict[str, str]) -> SyntheticCheckDtoOut:
    data = entry.dict()
    data["provider_name"] = provider_names.get(entry.temporal_provider_id)
    data["module_config"] = entry.module_config or {}
    data["targets"] = entry.targets or []
    data["labels"] = entry.labels or {}
    data["last_results"] = entry.last_results or {}
    return SyntheticCheckDtoOut(**data)


def _get_entry(session: Session, tenant_id: str, entry_id: int) -> SyntheticCheck:
    entry = session.exec(
        select(SyntheticCheck).where(
            SyntheticCheck.id == entry_id,
            SyntheticCheck.tenant_id == tenant_id,
        )
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Synthetic check not found")
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


def _allocate_check_key(
    session: Session, tenant_id: str, name: str, preferred: str | None = None
) -> str:
    base = slugify_check_key(preferred or name)
    candidate = base
    suffix = 2
    while session.exec(
        select(SyntheticCheck.id).where(
            SyntheticCheck.tenant_id == tenant_id,
            SyntheticCheck.check_key == candidate,
        )
    ).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _workflow_arg(entry: SyntheticCheck) -> dict:
    return {
        "check_id": entry.id,
        "check_key": entry.check_key,
        "name": entry.name,
        "prober": entry.prober,
        "module_config": entry.module_config or {},
        "targets": entry.targets or [],
        "labels": entry.labels or {},
        "task_queue": entry.task_queue or DEFAULT_TASK_QUEUE,
    }


def _schedule_id_for(entry: SyntheticCheck) -> str:
    return entry.schedule_id or f"synth-check-{entry.check_key}"


def _sync_schedule(entry: SyntheticCheck, provider) -> str:
    """Create/update Temporal Schedule from check config. Returns schedule_id."""
    schedule_id = _schedule_id_for(entry)
    provider.upsert_interval_schedule(
        schedule_id=schedule_id,
        workflow_type=PROBE_TARGET_GROUP_WORKFLOW,
        task_queue=entry.task_queue or DEFAULT_TASK_QUEUE,
        workflow_arg=_workflow_arg(entry),
        interval_seconds=entry.interval_seconds,
        paused=not entry.enabled,
        workflow_id=f"synth-check-{entry.check_key}",
    )
    return schedule_id


def _delete_schedule(entry: SyntheticCheck, provider) -> None:
    schedule_id = entry.schedule_id or f"synth-check-{entry.check_key}"
    try:
        provider.delete_schedule(schedule_id)
    except Exception as exc:
        logger.warning(
            "Failed to delete Temporal schedule for synthetic check",
            extra={"check_key": entry.check_key, "error": str(exc)},
        )


@router.get("", description="List synthetic checks")
def list_synthetic_checks(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> list[SyntheticCheckDtoOut]:
    tenant_id = authenticated_entity.tenant_id
    entries = session.exec(
        select(SyntheticCheck)
        .where(SyntheticCheck.tenant_id == tenant_id)
        .order_by(SyntheticCheck.name)
    ).all()
    provider_names = _provider_name_map(session, tenant_id)
    return [_to_dto(entry, provider_names) for entry in entries]


@router.get("/{entry_id}", description="Get a synthetic check")
def get_synthetic_check(
    entry_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:providers"])
    ),
    session: Session = Depends(get_session),
) -> SyntheticCheckDtoOut:
    entry = _get_entry(session, authenticated_entity.tenant_id, entry_id)
    provider_names = _provider_name_map(session, authenticated_entity.tenant_id)
    return _to_dto(entry, provider_names)


@router.post("", description="Create a synthetic check and Temporal Schedule")
def create_synthetic_check(
    body: SyntheticCheckDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> SyntheticCheckDtoOut:
    tenant_id = authenticated_entity.tenant_id
    provider = _get_temporal_provider(tenant_id, body.temporal_provider_id, session)

    if not body.targets:
        raise HTTPException(status_code=400, detail="At least one target is required")

    now = datetime.now(tz=timezone.utc)
    payload = body.dict()
    payload["module_config"] = body.module_config or {}
    payload["targets"] = body.targets or []
    payload["labels"] = body.labels or {}
    payload["task_queue"] = body.task_queue or DEFAULT_TASK_QUEUE
    if body.check_key:
        payload["check_key"] = slugify_check_key(body.check_key)
    else:
        payload["check_key"] = _allocate_check_key(session, tenant_id, body.name)

    entry = SyntheticCheck(
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
            detail=f"Check key '{payload['check_key']}' already exists for this tenant",
        ) from exc
    session.refresh(entry)

    try:
        entry.schedule_id = _sync_schedule(entry, provider)
        entry.updated_at = datetime.now(tz=timezone.utc)
        session.add(entry)
        session.commit()
        session.refresh(entry)
    except Exception as exc:
        logger.exception(
            "Synthetic check created but Temporal schedule sync failed",
            extra={"check_key": entry.check_key},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Check saved but schedule sync failed: {exc}",
        ) from exc

    provider_names = _provider_name_map(session, tenant_id)
    return _to_dto(entry, provider_names)


@router.put("/{entry_id}", description="Update a synthetic check and resync Schedule")
def update_synthetic_check(
    entry_id: int,
    body: SyntheticCheckUpdateDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> SyntheticCheckDtoOut:
    tenant_id = authenticated_entity.tenant_id
    entry = _get_entry(session, tenant_id, entry_id)
    provider = _get_temporal_provider(tenant_id, body.temporal_provider_id, session)

    if not body.targets:
        raise HTTPException(status_code=400, detail="At least one target is required")

    payload = body.dict(exclude_unset=False)
    if not payload.get("check_key"):
        payload["check_key"] = entry.check_key
    else:
        payload["check_key"] = slugify_check_key(payload["check_key"])
    payload["module_config"] = body.module_config or {}
    payload["targets"] = body.targets or []
    payload["labels"] = body.labels or {}
    payload["task_queue"] = body.task_queue or DEFAULT_TASK_QUEUE

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
            detail=f"Check key '{payload['check_key']}' already exists for this tenant",
        ) from exc
    session.refresh(entry)

    try:
        entry.schedule_id = _sync_schedule(entry, provider)
        session.add(entry)
        session.commit()
        session.refresh(entry)
    except Exception as exc:
        logger.exception(
            "Synthetic check updated but Temporal schedule sync failed",
            extra={"check_key": entry.check_key},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Check saved but schedule sync failed: {exc}",
        ) from exc

    provider_names = _provider_name_map(session, tenant_id)
    return _to_dto(entry, provider_names)


@router.delete("/{entry_id}", description="Delete a synthetic check and its Schedule")
def delete_synthetic_check(
    entry_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
):
    tenant_id = authenticated_entity.tenant_id
    entry = _get_entry(session, tenant_id, entry_id)
    try:
        provider = _get_temporal_provider(
            tenant_id, entry.temporal_provider_id, session
        )
        _delete_schedule(entry, provider)
    except Exception as exc:
        logger.warning(
            "Proceeding with synthetic check delete despite schedule cleanup error",
            extra={"check_key": entry.check_key, "error": str(exc)},
        )

    session.delete(entry)
    session.commit()
    return {"message": "Synthetic check deleted successfully"}


@router.post(
    "/{entry_id}/run",
    description="Run ProbeTargetGroup once for this check (Mode 1 manual run)",
)
def run_synthetic_check(
    entry_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:providers"])
    ),
    session: Session = Depends(get_session),
) -> SyntheticCheckRunResult:
    tenant_id = authenticated_entity.tenant_id
    entry = _get_entry(session, tenant_id, entry_id)
    if not entry.targets:
        raise HTTPException(status_code=400, detail="Check has no targets")

    provider = _get_temporal_provider(tenant_id, entry.temporal_provider_id, session)
    workflow_id = (
        f"synth-check-{entry.check_key}-manual-"
        f"{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )
    try:
        result = provider._run_async(
            provider._start_workflow(
                workflow_type=PROBE_TARGET_GROUP_WORKFLOW,
                task_queue=entry.task_queue or DEFAULT_TASK_QUEUE,
                workflow_id=workflow_id,
                args=None,
                arg=_workflow_arg(entry),
            )
        )
    except Exception as exc:
        logger.exception(
            "Failed to start ProbeTargetGroup",
            extra={"check_key": entry.check_key, "tenant_id": tenant_id},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SyntheticCheckRunResult(
        workflow_id=result.get("workflow_id"),
        run_id=result.get("run_id"),
        task_queue=result.get("task_queue") or entry.task_queue,
        workflow_type=result.get("workflow_type") or PROBE_TARGET_GROUP_WORKFLOW,
        namespace=result.get("namespace"),
        check_id=entry.id,
        check_key=entry.check_key,
    )
