"""Approval engine: match policies, persist pending requests, dispatch on decide."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import celpy
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from keep.api.core.db import get_session_sync
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.db.approval import (
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalRequestDtoOut,
    utc_now,
)
from keep.identitymanager.rbac import Roles

logger = logging.getLogger(__name__)


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def request_to_dto(request: ApprovalRequest) -> ApprovalRequestDtoOut:
    return ApprovalRequestDtoOut(
        id=request.id,
        policy_id=request.policy_id,
        action_type=request.action_type,
        status=request.status,
        title=request.title,
        summary=request.summary,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        payload=request.payload_json or {},
        context=request.context_json or {},
        callback=request.callback_json or {},
        result=request.result_json or {},
        idempotency_key=request.idempotency_key,
        requested_by=request.requested_by,
        requested_at=request.requested_at,
        decided_by=request.decided_by,
        decided_at=request.decided_at,
        decision_comment=request.decision_comment,
        expires_at=request.expires_at,
    )


def pending_response(request: ApprovalRequest) -> JSONResponse:
    return JSONResponse(
        status_code=202,
        content=jsonable_encoder(
            {
                "status": "pending",
                "request_id": request.id,
                "approval": request_to_dto(request).dict(),
            }
        ),
    )


def is_pending_payload(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("status") == "pending"
        and payload.get("request_id") is not None
    )


@dataclass
class GateResult:
    executed: bool
    request: Optional[ApprovalRequest] = None

    @property
    def pending(self) -> bool:
        return not self.executed and self.request is not None


class ApprovalBl:
    def __init__(self, tenant_id: str, session: Session | None = None):
        self.tenant_id = tenant_id
        self.session = session
        self._owns_session = session is None
        if session is None:
            self.session = get_session_sync()

    def close(self) -> None:
        if self._owns_session and self.session is not None:
            self.session.close()

    def gate(
        self,
        *,
        action_type: str,
        requested_by: str,
        title: str,
        payload: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        callback: dict[str, Any] | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        summary: str | None = None,
        idempotency_key: str | None = None,
        force: bool = False,
    ) -> GateResult:
        payload = payload or {}
        context = context or {}
        cel_payload = {
            "action_type": action_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload,
            **context,
        }
        policy = self._match_policy(action_type, resource_type, cel_payload)
        if policy is None and not force:
            return GateResult(executed=True)

        if idempotency_key:
            existing = self._pending_by_key(idempotency_key)
            if existing is not None:
                return GateResult(executed=False, request=existing)

        request = self._insert_request(
            policy=policy,
            action_type=action_type,
            title=title,
            summary=summary,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
            context=context,
            callback=callback or {},
            idempotency_key=idempotency_key,
            requested_by=requested_by,
        )
        self._notify("approval-update", request)
        return GateResult(executed=False, request=request)

    def create_external_request(
        self,
        *,
        action_type: str,
        requested_by: str,
        title: str,
        payload: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        callback: dict[str, Any] | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        summary: str | None = None,
        idempotency_key: str | None = None,
    ) -> ApprovalRequest:
        result = self.gate(
            action_type=action_type,
            requested_by=requested_by,
            title=title,
            payload=payload,
            context=context,
            callback=callback,
            resource_type=resource_type,
            resource_id=resource_id,
            summary=summary,
            idempotency_key=idempotency_key,
            force=True,
        )
        assert result.request is not None
        return result.request

    def get_request(self, request_id: int) -> ApprovalRequest:
        request = self.session.exec(
            select(ApprovalRequest).where(
                ApprovalRequest.id == request_id,
                ApprovalRequest.tenant_id == self.tenant_id,
            )
        ).first()
        if request is None:
            raise HTTPException(status_code=404, detail="Approval request not found")
        return request

    def list_requests(
        self,
        status: str | None = None,
        action_type: str | None = None,
        resource_type: str | None = None,
    ) -> list[ApprovalRequest]:
        query = select(ApprovalRequest).where(
            ApprovalRequest.tenant_id == self.tenant_id
        )
        if status:
            query = query.where(ApprovalRequest.status == status)
        if action_type:
            query = query.where(ApprovalRequest.action_type == action_type)
        if resource_type:
            query = query.where(ApprovalRequest.resource_type == resource_type)
        query = query.order_by(ApprovalRequest.requested_at.desc())
        return list(self.session.exec(query).all())

    def approve(
        self,
        request_id: int,
        decided_by: str,
        role: str | None,
        comment: str | None = None,
    ) -> ApprovalRequest:
        request = self.get_request(request_id)
        self._assert_can_decide(request, decided_by, role)
        if request.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request is not pending")
        callback_kind = (request.callback_json or {}).get("kind")
        is_external = request.action_type in ("temporal_signal", "webhook") or callback_kind in (
            "temporal_signal",
            "webhook",
        )
        request.decided_by = decided_by
        request.decided_at = utc_now()
        request.decision_comment = comment
        try:
            if is_external:
                request.status = "approved"
                self.session.add(request)
                self.session.commit()
                self.session.refresh(request)
                self._notify_external_decision(request, approved=True)
            else:
                self.dispatch(request, approved=True)
                request.status = "approved"
                self.session.add(request)
                self.session.commit()
                self.session.refresh(request)
        except HTTPException:
            self.session.rollback()
            raise
        except Exception:
            logger.exception(
                "Approval dispatch failed",
                extra={"request_id": request.id, "tenant_id": self.tenant_id},
            )
            self.session.rollback()
            raise HTTPException(
                status_code=500, detail="Approved action failed to execute"
            ) from None
        self._notify("approval-update", request)
        return request

    def reject(
        self,
        request_id: int,
        decided_by: str,
        role: str | None,
        comment: str | None = None,
    ) -> ApprovalRequest:
        request = self.get_request(request_id)
        self._assert_can_decide(request, decided_by, role, allow_requester=True)
        if request.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request is not pending")
        request.status = "rejected"
        request.decided_by = decided_by
        request.decided_at = utc_now()
        request.decision_comment = comment
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        self._notify_external_decision(request, approved=False)
        self._notify("approval-update", request)
        return request

    def cancel(self, request_id: int, actor: str, role: str | None) -> ApprovalRequest:
        request = self.get_request(request_id)
        if request.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request is not pending")
        is_admin = (role or "").lower() == Roles.ADMIN.value
        if request.requested_by != actor and not is_admin:
            raise HTTPException(
                status_code=403, detail="Only the requester or an admin can cancel"
            )
        request.status = "cancelled"
        request.decided_by = actor
        request.decided_at = utc_now()
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        self._notify_external_decision(request, approved=False)
        self._notify("approval-update", request)
        return request

    def expire_pending(self, now: datetime | None = None) -> int:
        current = now or utc_now()
        pending = self.session.exec(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.tenant_id,
                ApprovalRequest.status == "pending",
                ApprovalRequest.expires_at != None,  # noqa: E711
            )
        ).all()
        expired = 0
        for request in pending:
            expires = request.expires_at
            if expires is None:
                continue
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > current:
                continue
            request.status = "expired"
            request.decided_by = "system"
            request.decided_at = current
            request.decision_comment = "Expired waiting for approval"
            self.session.add(request)
            self._notify_external_decision(request, approved=False)
            self._notify("approval-update", request)
            expired += 1
        if expired:
            self.session.commit()
        return expired

    @staticmethod
    def expire_all_tenants(logger_: logging.Logger, session: Session | None = None) -> int:
        _owns = session is None
        if session is None:
            session = get_session_sync()
        try:
            tenant_ids = session.exec(
                select(ApprovalRequest.tenant_id)
                .where(ApprovalRequest.status == "pending")
                .distinct()
            ).all()
            total = 0
            for tenant_id in tenant_ids:
                total += ApprovalBl(tenant_id, session).expire_pending()
            if total:
                logger_.info("Expired %s pending approval requests", total)
            return total
        finally:
            if _owns:
                session.close()

    def dispatch(self, request: ApprovalRequest, approved: bool = True) -> None:
        if not approved:
            self._notify_external_decision(request, approved=False)
            return
        action = request.action_type
        callback = request.callback_json or {}
        kind = callback.get("kind")
        if action in ("create_maintenance", "node_maintenance"):
            request.result_json = self._dispatch_create_maintenance(request)
            request.resource_id = str(
                (request.result_json or {}).get("id") or request.resource_id or ""
            )
            self.session.add(request)
            return
        if action == "run_workflow" or (
            kind == "keep_action" and callback.get("workflow_id")
        ):
            request.result_json = self._dispatch_run_workflow(request)
            self.session.add(request)
            return
        if action == "delete_resource":
            request.result_json = self._dispatch_delete_resource(request)
            self.session.add(request)
            return
        if action == "temporal_signal" or kind == "temporal_signal":
            request.result_json = self._dispatch_temporal_signal(request, approved=True)
            self.session.add(request)
            return
        if action == "webhook" or kind == "webhook":
            request.result_json = self._dispatch_webhook(request, approved=True)
            self.session.add(request)
            return
        if kind == "keep_action":
            request.result_json = self._dispatch_run_workflow(request)
            self.session.add(request)
            return
        request.result_json = {"ok": True, "note": "no-op custom approval"}
        self.session.add(request)

    def _notify_external_decision(self, request: ApprovalRequest, approved: bool) -> None:
        callback = request.callback_json or {}
        kind = callback.get("kind")
        try:
            if request.action_type == "temporal_signal" or kind == "temporal_signal":
                self._dispatch_temporal_signal(request, approved=approved)
            elif request.action_type == "webhook" or kind == "webhook":
                self._dispatch_webhook(request, approved=approved)
        except Exception:
            logger.exception(
                "Failed to notify external system of approval decision",
                extra={"request_id": request.id, "approved": approved},
            )

    def _match_policy(
        self,
        action_type: str,
        resource_type: str | None,
        cel_payload: dict[str, Any],
    ) -> ApprovalPolicy | None:
        policies = self.session.exec(
            select(ApprovalPolicy)
            .where(
                ApprovalPolicy.tenant_id == self.tenant_id,
                ApprovalPolicy.enabled == True,  # noqa: E712
                ApprovalPolicy.action_type == action_type,
            )
            .order_by(ApprovalPolicy.priority.desc(), ApprovalPolicy.id.asc())
        ).all()
        env = celpy.Environment()
        for policy in policies:
            if policy.resource_type and policy.resource_type != resource_type:
                continue
            if self._evaluate_cel(policy.cel, cel_payload, env):
                return policy
        return None

    def _evaluate_cel(
        self, cel: str | None, payload: dict[str, Any], env: celpy.Environment
    ) -> bool:
        expression = (cel or "").strip()
        if not expression or expression == "true":
            return True
        try:
            ast = env.compile(expression)
            program = env.program(ast)
            activation = celpy.json_to_cel(json_safe(payload))
            return bool(program.evaluate(activation))
        except Exception as exc:
            logger.warning(
                "Approval policy CEL failed: %s",
                exc,
                extra={"tenant_id": self.tenant_id, "cel": expression},
            )
            return False

    def _pending_by_key(self, idempotency_key: str) -> ApprovalRequest | None:
        return self.session.exec(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.tenant_id,
                ApprovalRequest.status == "pending",
                ApprovalRequest.idempotency_key == idempotency_key,
            )
        ).first()

    def _insert_request(
        self,
        *,
        policy: ApprovalPolicy | None,
        action_type: str,
        title: str,
        summary: str | None,
        resource_type: str | None,
        resource_id: str | None,
        payload: dict[str, Any],
        context: dict[str, Any],
        callback: dict[str, Any],
        idempotency_key: str | None,
        requested_by: str,
    ) -> ApprovalRequest:
        now = utc_now()
        expires_at = None
        if policy and policy.timeout_seconds:
            expires_at = now + timedelta(seconds=policy.timeout_seconds)
        request = ApprovalRequest(
            tenant_id=self.tenant_id,
            policy_id=policy.id if policy else None,
            action_type=action_type,
            status="pending",
            title=title,
            summary=summary,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            payload_json=json_safe(payload),
            context_json=json_safe(context),
            callback_json=json_safe(callback),
            result_json={},
            idempotency_key=idempotency_key,
            requested_by=requested_by,
            requested_at=now,
            expires_at=expires_at,
        )
        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        return request

    def _load_policy(self, policy_id: int | None) -> ApprovalPolicy | None:
        if policy_id is None:
            return None
        return self.session.exec(
            select(ApprovalPolicy).where(
                ApprovalPolicy.id == policy_id,
                ApprovalPolicy.tenant_id == self.tenant_id,
            )
        ).first()

    def _assert_can_decide(
        self,
        request: ApprovalRequest,
        email: str,
        role: str | None,
        allow_requester: bool = False,
    ) -> None:
        if request.status != "pending":
            raise HTTPException(status_code=409, detail="Approval request is not pending")
        policy = self._load_policy(request.policy_id)
        allow_self = bool(policy.allow_self_approve) if policy else False
        is_requester = bool(
            email
            and request.requested_by
            and email.lower() == request.requested_by.lower()
        )
        if is_requester and allow_requester:
            return
        if is_requester and not allow_self:
            raise HTTPException(
                status_code=403, detail="Requester cannot approve their own request"
            )
        is_admin = (role or "").lower() == Roles.ADMIN.value
        if is_admin:
            return
        emails = [item.lower() for item in (policy.approver_emails or [])] if policy else []
        roles = [item.lower() for item in (policy.approver_roles or [])] if policy else []
        if email and email.lower() in emails:
            return
        if role and role.lower() in roles:
            return
        raise HTTPException(
            status_code=403, detail="Not allowed to decide this approval request"
        )

    def _notify(self, event: str, request: ApprovalRequest) -> None:
        try:
            client = get_pusher_client()
            if not client:
                return
            client.trigger(
                f"private-{self.tenant_id}",
                event,
                jsonable_encoder({"request_id": request.id, "status": request.status}),
            )
        except Exception:
            logger.debug("Pusher approval notify failed", exc_info=True)

    def _dispatch_create_maintenance(self, request: ApprovalRequest) -> dict[str, Any]:
        from datetime import timedelta as td

        from keep.api.models.db.maintenance_window import (
            DEFAULT_ALERT_STATUSES_TO_IGNORE,
            MaintenanceWindowRule,
        )

        payload = dict(request.payload_json or {})
        start_time = payload.get("start_time")
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        duration = int(payload.get("duration_seconds") or 0)
        if start_time is None or duration <= 0:
            raise ValueError("maintenance payload requires start_time and duration_seconds")
        ignore = payload.get("ignore_statuses") or list(DEFAULT_ALERT_STATUSES_TO_IGNORE)
        rule = MaintenanceWindowRule(
            name=payload.get("name") or request.title,
            description=payload.get("description"),
            cel_query=payload.get("cel_query") or "true",
            start_time=start_time,
            duration_seconds=duration,
            end_time=start_time + td(seconds=duration),
            suppress=payload.get("suppress", True),
            enabled=payload.get("enabled", True),
            ignore_statuses=ignore,
            priority=int(payload.get("priority") or 0),
            created_by=request.requested_by,
            tenant_id=self.tenant_id,
        )
        self.session.add(rule)
        self.session.flush()
        return {"id": rule.id, "name": rule.name}

    def _dispatch_run_workflow(self, request: ApprovalRequest) -> dict[str, Any]:
        from keep.api.models.alert import AlertDto
        from keep.api.models.incident import IncidentDto
        from keep.workflowmanager.workflowmanager import WorkflowManager

        payload = dict(request.payload_json or {})
        callback = request.callback_json or {}
        workflow_id = (
            payload.get("workflow_id")
            or callback.get("workflow_id")
            or request.resource_id
        )
        if not workflow_id:
            raise ValueError("workflow_id is required to run a workflow")
        event_payload = payload.get("event") or {}
        event_type = payload.get("event_type") or "alert"
        triggered_by = payload.get("triggered_by") or f"approval:{request.id}"
        event: AlertDto | IncidentDto
        if event_type == "incident":
            event = IncidentDto(**event_payload)
            event._tenant_id = self.tenant_id
        else:
            try:
                event = AlertDto(**event_payload)
            except TypeError:
                event = AlertDto(
                    **{
                        "name": event_payload.get("name") or request.title,
                        "source": event_payload.get("source") or ["keep"],
                        "lastReceived": event_payload.get("lastReceived")
                        or utc_now().isoformat(),
                        **{k: v for k, v in event_payload.items() if k not in ("source",)},
                    }
                )
        WorkflowManager.get_instance().enqueue_workflow(
            tenant_id=self.tenant_id,
            workflow_id=str(workflow_id),
            event=event,
            triggered_by=str(triggered_by),
        )
        return {"workflow_id": str(workflow_id), "enqueued": True}

    def _dispatch_delete_resource(self, request: ApprovalRequest) -> dict[str, Any]:
        resource_type = request.resource_type or (request.payload_json or {}).get(
            "resource_type"
        )
        resource_id = request.resource_id or (request.payload_json or {}).get(
            "resource_id"
        )
        extra = dict(request.payload_json or {})
        if not resource_type or resource_id is None:
            raise ValueError("delete_resource requires resource_type and resource_id")
        _execute_delete(self.session, self.tenant_id, str(resource_type), str(resource_id), extra)
        return {"deleted": True, "resource_type": resource_type, "resource_id": str(resource_id)}

    def _dispatch_temporal_signal(
        self, request: ApprovalRequest, approved: bool
    ) -> dict[str, Any]:
        callback = request.callback_json or {}
        payload = request.payload_json or {}
        workflow_id = callback.get("workflow_id") or payload.get("temporal_workflow_id")
        if not workflow_id:
            raise ValueError("temporal_signal callback requires workflow_id")
        signal_name = callback.get("signal_name") or "approve"
        run_id = callback.get("run_id")
        provider_id = callback.get("provider_id")
        signal_args = {
            "approved": approved,
            "decided_by": request.decided_by,
            "comment": request.decision_comment,
            "request_id": request.id,
            "status": request.status,
        }
        provider = _get_temporal_provider(self.tenant_id, self.session, provider_id)
        result = provider.notify(
            operation="signal_workflow",
            workflow_id=workflow_id,
            run_id=run_id,
            signal_name=signal_name,
            signal_args=signal_args,
        )
        return {"signaled": True, "result": result}

    def _dispatch_webhook(
        self, request: ApprovalRequest, approved: bool
    ) -> dict[str, Any]:
        import requests

        callback = request.callback_json or {}
        url = callback.get("url")
        if not url:
            raise ValueError("webhook callback requires url")
        headers = dict(callback.get("headers") or {})
        body = {
            "request_id": request.id,
            "status": request.status,
            "approved": approved,
            "decided_by": request.decided_by,
            "comment": request.decision_comment,
            "action_type": request.action_type,
            "payload": request.payload_json or {},
        }
        response = requests.post(url, json=body, headers=headers, timeout=15)
        return {"ok": response.status_code < 400, "http_status": response.status_code}


def _execute_delete(
    session: Session,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    extra: dict[str, Any],
) -> None:
    from fastapi import HTTPException as FastAPIHTTPException

    if resource_type == "workflow":
        from keep.workflowmanager.workflowstore import WorkflowStore

        WorkflowStore().delete_workflow(workflow_id=resource_id, tenant_id=tenant_id)
        return
    if resource_type == "maintenance":
        from keep.api.models.db.maintenance_window import MaintenanceWindowRule

        rule = session.exec(
            select(MaintenanceWindowRule).where(
                MaintenanceWindowRule.id == int(resource_id),
                MaintenanceWindowRule.tenant_id == tenant_id,
            )
        ).first()
        if rule is None:
            raise FastAPIHTTPException(status_code=404, detail="Maintenance rule not found")
        session.delete(rule)
        session.flush()
        return
    if resource_type == "provider":
        from keep.providers.providers_service import ProvidersService

        ProvidersService.delete_provider(tenant_id, resource_id, session)
        return
    if resource_type == "alert_catalog":
        from keep.api.models.db.alert_catalog import AlertCatalog

        entry = session.exec(
            select(AlertCatalog).where(
                AlertCatalog.id == int(resource_id),
                AlertCatalog.tenant_id == tenant_id,
            )
        ).first()
        if entry is None:
            raise FastAPIHTTPException(status_code=404, detail="Alert catalog entry not found")
        session.delete(entry)
        session.flush()
        return
    if resource_type == "temporal_catalog":
        from keep.api.models.db.temporal_workflow_catalog import TemporalWorkflowCatalog

        entry = session.exec(
            select(TemporalWorkflowCatalog).where(
                TemporalWorkflowCatalog.id == int(resource_id),
                TemporalWorkflowCatalog.tenant_id == tenant_id,
            )
        ).first()
        if entry is None:
            raise FastAPIHTTPException(
                status_code=404, detail="Temporal workflow catalog entry not found"
            )
        session.delete(entry)
        session.flush()
        return
    if resource_type == "correlation_rule":
        from keep.api.core.db import delete_rule as delete_rule_db

        if not delete_rule_db(tenant_id=tenant_id, rule_id=resource_id):
            raise FastAPIHTTPException(status_code=404, detail="Rule not found")
        return
    if resource_type == "mapping":
        from keep.api.models.db.mapping import MappingRule

        rule = (
            session.query(MappingRule)
            .filter(MappingRule.id == int(resource_id), MappingRule.tenant_id == tenant_id)
            .first()
        )
        if rule is None:
            raise FastAPIHTTPException(status_code=404, detail="Rule not found")
        if getattr(rule, "is_provisioned", False):
            raise FastAPIHTTPException(
                status_code=409, detail="Provisioned mapping rule cannot be deleted"
            )
        session.delete(rule)
        session.flush()
        return
    if resource_type == "extraction":
        from keep.api.models.db.extraction import ExtractionRule

        rule = (
            session.query(ExtractionRule)
            .filter(
                ExtractionRule.id == int(resource_id),
                ExtractionRule.tenant_id == tenant_id,
            )
            .first()
        )
        if rule is None:
            raise FastAPIHTTPException(status_code=404, detail="Extraction rule not found")
        session.delete(rule)
        session.flush()
        return
    if resource_type == "synthetic_check":
        from keep.api.models.db.synthetic_check import SyntheticCheck
        from keep.api.routes import synthetic_checks as synthetic_routes

        entry = synthetic_routes._get_entry(session, tenant_id, int(resource_id))
        try:
            provider = synthetic_routes._get_temporal_provider(
                tenant_id, entry.temporal_provider_id, session
            )
            synthetic_routes._delete_schedule(entry, provider)
        except Exception as exc:
            logger.warning(
                "Proceeding with synthetic check delete despite schedule cleanup error: %s",
                exc,
            )
        session.delete(entry)
        session.flush()
        return
    raise FastAPIHTTPException(
        status_code=400, detail=f"Unsupported delete resource_type '{resource_type}'"
    )


def _get_temporal_provider(tenant_id: str, session: Session, provider_id: str | None):
    from sqlalchemy.exc import NoResultFound

    from keep.api.models.db.provider import Provider
    from keep.contextmanager.contextmanager import ContextManager
    from keep.providers.providers_factory import ProvidersFactory
    from keep.secretmanager.secretmanagerfactory import SecretManagerFactory

    context_manager = ContextManager(tenant_id=tenant_id)
    secret_manager = SecretManagerFactory.get_secret_manager(context_manager)
    query = select(Provider).where(
        Provider.tenant_id == tenant_id, Provider.type == "temporal"
    )
    if provider_id:
        query = query.where(Provider.id == provider_id)
    try:
        provider_row = session.exec(query).first()
    except NoResultFound:
        provider_row = None
    if provider_row is None:
        raise HTTPException(status_code=400, detail="No Temporal provider installed")
    config = secret_manager.read_secret(
        secret_name=provider_row.id, is_json=True
    )
    return ProvidersFactory.get_provider(
        context_manager, provider_row.id, "temporal", config
    )
