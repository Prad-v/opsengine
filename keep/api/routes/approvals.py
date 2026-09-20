from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from keep.api.bl.approval_bl import ApprovalBl, request_to_dto
from keep.api.core.db import get_session
from keep.api.models.db.approval import (
    ApprovalDecisionDto,
    ApprovalPolicy,
    ApprovalPolicyDtoIn,
    ApprovalPolicyDtoOut,
    ApprovalRequestCreateDto,
    ApprovalRequestDtoOut,
)
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()
logger = logging.getLogger(__name__)


def _policy_to_dto(policy: ApprovalPolicy) -> ApprovalPolicyDtoOut:
    return ApprovalPolicyDtoOut(
        id=policy.id,
        name=policy.name,
        action_type=policy.action_type,
        resource_type=policy.resource_type,
        cel=policy.cel,
        enabled=policy.enabled,
        approver_roles=policy.approver_roles or [],
        approver_emails=policy.approver_emails or [],
        allow_self_approve=policy.allow_self_approve,
        timeout_seconds=policy.timeout_seconds,
        priority=policy.priority or 0,
        min_approvals=policy.min_approvals or 1,
        created_by=policy.created_by,
        created_at=policy.created_at,
        updated_by=policy.updated_by,
        updated_at=policy.updated_at,
    )


def _get_policy(session: Session, tenant_id: str, policy_id: int) -> ApprovalPolicy:
    policy = session.exec(
        select(ApprovalPolicy).where(
            ApprovalPolicy.id == policy_id,
            ApprovalPolicy.tenant_id == tenant_id,
        )
    ).first()
    if policy is None:
        raise HTTPException(status_code=404, detail="Approval policy not found")
    return policy


@router.get("/policies", description="List approval policies")
def list_approval_policies(
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> list[ApprovalPolicyDtoOut]:
    policies = session.exec(
        select(ApprovalPolicy)
        .where(ApprovalPolicy.tenant_id == authenticated_entity.tenant_id)
        .order_by(ApprovalPolicy.priority.desc(), ApprovalPolicy.id.asc())
    ).all()
    return [_policy_to_dto(policy) for policy in policies]


@router.post("/policies", description="Create an approval policy")
def create_approval_policy(
    body: ApprovalPolicyDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalPolicyDtoOut:
    now = datetime.now(tz=timezone.utc)
    policy = ApprovalPolicy(
        **body.dict(),
        tenant_id=authenticated_entity.tenant_id,
        created_by=authenticated_entity.email,
        created_at=now,
        updated_at=now,
    )
    session.add(policy)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Could not create approval policy") from exc
    session.refresh(policy)
    return _policy_to_dto(policy)


@router.get("/policies/{policy_id}", description="Get an approval policy")
def get_approval_policy(
    policy_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalPolicyDtoOut:
    return _policy_to_dto(
        _get_policy(session, authenticated_entity.tenant_id, policy_id)
    )


@router.put("/policies/{policy_id}", description="Update an approval policy")
def update_approval_policy(
    policy_id: int,
    body: ApprovalPolicyDtoIn,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalPolicyDtoOut:
    policy = _get_policy(session, authenticated_entity.tenant_id, policy_id)
    for key, value in body.dict().items():
        setattr(policy, key, value)
    policy.updated_by = authenticated_entity.email
    policy.updated_at = datetime.now(tz=timezone.utc)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return _policy_to_dto(policy)


@router.delete("/policies/{policy_id}", description="Delete an approval policy")
def delete_approval_policy(
    policy_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:approvals"])
    ),
    session: Session = Depends(get_session),
):
    policy = _get_policy(session, authenticated_entity.tenant_id, policy_id)
    session.delete(policy)
    session.commit()
    return {"message": "Approval policy deleted successfully"}


@router.get("", description="List approval requests")
def list_approval_requests(
    status: str | None = Query(None),
    action_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> list[ApprovalRequestDtoOut]:
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    return [
        request_to_dto(item)
        for item in bl.list_requests(
            status=status, action_type=action_type, resource_type=resource_type
        )
    ]


@router.post("", description="Create an approval request (Keep YAML, Temporal, external)")
def create_approval_request(
    body: ApprovalRequestCreateDto,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["write:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalRequestDtoOut:
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    request = bl.create_external_request(
        action_type=body.action_type,
        requested_by=authenticated_entity.email,
        title=body.title,
        summary=body.summary,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        payload=body.payload,
        context=body.context,
        callback=body.callback,
        idempotency_key=body.idempotency_key,
    )
    return request_to_dto(request)


@router.get("/{request_id}", description="Get an approval request")
def get_approval_request(
    request_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalRequestDtoOut:
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    return request_to_dto(bl.get_request(request_id))


@router.post("/{request_id}/approve", description="Approve a pending request and execute it")
def approve_request(
    request_id: int,
    body: ApprovalDecisionDto | None = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalRequestDtoOut:
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    comment = body.comment if body else None
    request = bl.approve(
        request_id,
        authenticated_entity.email,
        authenticated_entity.role,
        comment=comment,
    )
    return request_to_dto(request)


@router.post("/{request_id}/reject", description="Reject a pending request")
def reject_request(
    request_id: int,
    body: ApprovalDecisionDto | None = None,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalRequestDtoOut:
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    comment = body.comment if body else None
    request = bl.reject(
        request_id,
        authenticated_entity.email,
        authenticated_entity.role,
        comment=comment,
    )
    return request_to_dto(request)


@router.post("/{request_id}/cancel", description="Cancel a pending request")
def cancel_request(
    request_id: int,
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:approvals"])
    ),
    session: Session = Depends(get_session),
) -> ApprovalRequestDtoOut:
    bl = ApprovalBl(authenticated_entity.tenant_id, session)
    request = bl.cancel(
        request_id, authenticated_entity.email, authenticated_entity.role
    )
    return request_to_dto(request)
