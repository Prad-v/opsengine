from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from keep.api.bl.approval_bl import ApprovalBl, pending_response
from keep.api.core.db import get_last_alerts, get_session
from keep.api.models.db.maintenance_window import (
    DEFAULT_ALERT_STATUSES_TO_IGNORE,
    MaintenanceExtendRequest,
    MaintenancePreviewRequest,
    MaintenancePreviewResponse,
    MaintenancePreviewSample,
    MaintenanceRuleCreate,
    MaintenanceRuleRead,
    MaintenanceWindowRule,
    as_utc,
    rule_lifecycle,
    utc_now,
)
from keep.api.utils.enrichment_helpers import convert_db_alerts_to_dto_alerts
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory
from keep.rulesengine.rulesengine import RulesEngine

router = APIRouter()

_STATUS_ORDER = {"active": 0, "upcoming": 1, "disabled": 2, "expired": 3}


def to_rule_read(rule: MaintenanceWindowRule) -> MaintenanceRuleRead:
    payload = rule.dict()
    payload["status"] = rule_lifecycle(rule)
    payload.setdefault("priority", 0)
    if payload.get("ignore_statuses") is None:
        payload["ignore_statuses"] = list(DEFAULT_ALERT_STATUSES_TO_IGNORE)
    return MaintenanceRuleRead(**payload)


def _get_tenant_rule(
    session: Session, tenant_id: str, rule_id: int
) -> MaintenanceWindowRule:
    rule = (
        session.query(MaintenanceWindowRule)
        .filter(
            MaintenanceWindowRule.tenant_id == tenant_id,
            MaintenanceWindowRule.id == rule_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(
            status_code=404, detail="Maintenance rule not found or access denied"
        )
    return rule


@router.get(
    "",
    response_model=list[MaintenanceRuleRead],
    description="Get all maintenance rules",
)
def get_maintenance_rules(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> list[MaintenanceRuleRead]:
    rules = (
        session.query(MaintenanceWindowRule)
        .filter(MaintenanceWindowRule.tenant_id == authenticated_entity.tenant_id)
        .all()
    )
    reads = [to_rule_read(rule) for rule in rules]
    reads.sort(
        key=lambda rule: (
            _STATUS_ORDER.get(rule.status, 9),
            -(rule.priority or 0),
            -rule.id,
        )
    )
    return reads


@router.post(
    "", description="Create a new maintenance rule"
)
def create_maintenance_rule(
    rule_dto: MaintenanceRuleCreate,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
):
    payload = rule_dto.dict()
    topology_service_id = payload.pop("topology_service_id", None)
    topology_category = payload.pop("topology_category", None)
    topology_reason = payload.pop("topology_reason", None)
    action_type = (
        "node_maintenance" if topology_service_id else "create_maintenance"
    )
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    gate = bl.gate(
        action_type=action_type,
        requested_by=authenticated_entity.email,
        title=rule_dto.name,
        summary=rule_dto.description,
        payload=payload,
        context={
            "service": topology_service_id,
            "category": topology_category,
            "reason": topology_reason,
            "duration_seconds": rule_dto.duration_seconds,
        },
        resource_type="maintenance",
        resource_id=topology_service_id,
        callback={"kind": "keep_action"},
        idempotency_key=(
            f"node_maintenance:{topology_service_id}"
            if topology_service_id
            else None
        ),
    )
    if gate.pending:
        return pending_response(gate.request)

    end_time = rule_dto.start_time + timedelta(seconds=rule_dto.duration_seconds)
    new_rule = MaintenanceWindowRule(
        **payload,
        end_time=end_time,
        created_by=authenticated_entity.email,
        tenant_id=authenticated_entity.tenant_id,
    )
    session.add(new_rule)
    session.commit()
    session.refresh(new_rule)
    return to_rule_read(new_rule)


@router.post(
    "/preview",
    response_model=MaintenancePreviewResponse,
    description="Preview how many recent alerts match a CEL query",
)
def preview_maintenance_rule(
    body: MaintenancePreviewRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:maintenance"])
    ),
) -> MaintenancePreviewResponse:
    db_alerts = get_last_alerts(
        tenant_id=authenticated_entity.tenant_id,
        limit=200,
        timeframe=1,
    )
    alert_dtos = convert_db_alerts_to_dto_alerts(db_alerts)
    try:
        rules_engine = RulesEngine(tenant_id=authenticated_entity.tenant_id)
        matched = rules_engine.filter_alerts(alert_dtos, body.cel_query)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid CEL query")
    sample = [
        MaintenancePreviewSample(
            fingerprint=alert.fingerprint,
            name=alert.name,
            source=alert.source,
            status=str(alert.status.value if hasattr(alert.status, "value") else alert.status),
        )
        for alert in matched[:10]
    ]
    return MaintenancePreviewResponse(count=len(matched), sample=sample)


@router.post(
    "/{rule_id}/end-now",
    response_model=MaintenanceRuleRead,
    description="End an active maintenance rule immediately",
)
def end_maintenance_rule_now(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> MaintenanceRuleRead:
    rule = _get_tenant_rule(session, authenticated_entity.tenant_id, rule_id)
    now = utc_now()
    rule.enabled = False
    rule.end_time = now
    start = as_utc(rule.start_time)
    rule.duration_seconds = max(1, int((now - start).total_seconds()))
    session.commit()
    session.refresh(rule)
    return to_rule_read(rule)


@router.post(
    "/{rule_id}/extend",
    response_model=MaintenanceRuleRead,
    description="Extend a maintenance rule by a duration in seconds",
)
def extend_maintenance_rule(
    rule_id: int,
    body: MaintenanceExtendRequest,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> MaintenanceRuleRead:
    rule = _get_tenant_rule(session, authenticated_entity.tenant_id, rule_id)
    now = utc_now()
    end = as_utc(rule.end_time)
    base = end if end > now else now
    rule.end_time = base + timedelta(seconds=body.duration_seconds)
    rule.enabled = True
    rule.duration_seconds = max(
        1, int((as_utc(rule.end_time) - as_utc(rule.start_time)).total_seconds())
    )
    session.commit()
    session.refresh(rule)
    return to_rule_read(rule)


@router.put(
    "/{rule_id}",
    response_model=MaintenanceRuleRead,
    description="Update an existing maintenance rule",
)
def update_maintenance_rule(
    rule_id: int,
    rule_dto: MaintenanceRuleCreate,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
) -> MaintenanceRuleRead:
    rule = _get_tenant_rule(session, authenticated_entity.tenant_id, rule_id)

    for key, value in rule_dto.dict(
        exclude={"topology_service_id", "topology_category", "topology_reason"}
    ).items():
        setattr(rule, key, value)

    end_time = rule_dto.start_time + timedelta(seconds=rule_dto.duration_seconds)
    rule.end_time = end_time

    session.commit()
    session.refresh(rule)
    return to_rule_read(rule)


@router.delete("/{rule_id}", description="Delete a maintenance rule")
def delete_maintenance_rule(
    rule_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:maintenance"])
    ),
    session: Session = Depends(get_session),
):
    _get_tenant_rule(session, authenticated_entity.tenant_id, rule_id)
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    gate = bl.gate(
        action_type="delete_resource",
        requested_by=authenticated_entity.email,
        title=f"Delete maintenance rule {rule_id}",
        payload={"resource_type": "maintenance", "resource_id": str(rule_id)},
        resource_type="maintenance",
        resource_id=str(rule_id),
        callback={"kind": "keep_action"},
        idempotency_key=f"delete:maintenance:{rule_id}",
    )
    if gate.pending:
        return pending_response(gate.request)
    rule = _get_tenant_rule(session, authenticated_entity.tenant_id, rule_id)
    session.delete(rule)
    session.commit()
    return {"detail": "Maintenance rule deleted successfully"}
