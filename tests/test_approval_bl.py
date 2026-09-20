from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from keep.api.bl.alert_catalog_bl import AlertCatalogBl
from keep.api.bl.approval_bl import ApprovalBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.alert_catalog import AlertCatalog
from keep.api.models.db.approval import ApprovalPolicy, ApprovalRequest
from keep.parser.parser import Parser
from sqlmodel import select


def _policy(session, **overrides):
    body = {
        "tenant_id": SINGLE_TENANT_UUID,
        "name": "gate",
        "action_type": "create_maintenance",
        "enabled": True,
        "allow_self_approve": False,
        "approver_roles": ["admin"],
        "approver_emails": [],
        "priority": 1,
        "min_approvals": 1,
    }
    body.update(overrides)
    policy = ApprovalPolicy(**body)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def test_gate_without_policy_executes(db_session):
    bl = ApprovalBl(SINGLE_TENANT_UUID, db_session)
    result = bl.gate(
        action_type="create_maintenance",
        requested_by="alice@example.com",
        title="short window",
        payload={"duration_seconds": 60},
    )
    assert result.executed is True
    assert result.pending is False


def test_gate_matching_policy_is_pending_and_idempotent(db_session):
    _policy(db_session)
    bl = ApprovalBl(SINGLE_TENANT_UUID, db_session)
    first = bl.gate(
        action_type="create_maintenance",
        requested_by="alice@example.com",
        title="long window",
        payload={"duration_seconds": 7200},
        idempotency_key="maint:gpu-node-a03",
    )
    second = bl.gate(
        action_type="create_maintenance",
        requested_by="alice@example.com",
        title="long window again",
        payload={"duration_seconds": 7200},
        idempotency_key="maint:gpu-node-a03",
    )
    assert first.pending is True
    assert second.request.id == first.request.id
    pending = db_session.exec(
        select(ApprovalRequest).where(ApprovalRequest.status == "pending")
    ).all()
    assert len(pending) == 1


def test_self_approve_blocked_requester_may_reject(db_session):
    _policy(db_session, allow_self_approve=False)
    bl = ApprovalBl(SINGLE_TENANT_UUID, db_session)
    gated = bl.gate(
        action_type="create_maintenance",
        requested_by="alice@example.com",
        title="needs two people",
        payload={"duration_seconds": 7200},
    )
    try:
        bl.approve(gated.request.id, "alice@example.com", "admin")
        assert False, "self-approve should be blocked"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    rejected = bl.reject(gated.request.id, "alice@example.com", "admin")
    assert rejected.status == "rejected"


def test_catalog_approval_does_not_enqueue(db_session):
    db_session.add(
        AlertCatalog(
            tenant_id=SINGLE_TENANT_UUID,
            code="NVIDIA_GPU_THERMAL",
            name="NVIDIA GPU thermal",
            keep_workflow_id="mock-nvidia-gpu-remediate",
            auto_run_on="approval",
        )
    )
    db_session.commit()
    alert = AlertDto(
        name="NVIDIA GPU thermal",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.now(timezone.utc).isoformat(),
        source=["prometheus"],
        fingerprint="fp-gpu-1",
        labels={"code": "NVIDIA_GPU_THERMAL"},
    )
    with patch(
        "keep.workflowmanager.workflowmanager.WorkflowManager.get_instance"
    ) as mocked:
        AlertCatalogBl(SINGLE_TENANT_UUID, db_session).apply_to_alert(
            alert, persist=False
        )
        mocked.return_value.enqueue_workflow.assert_not_called()
    pending = db_session.exec(
        select(ApprovalRequest).where(
            ApprovalRequest.action_type == "run_workflow",
            ApprovalRequest.status == "pending",
        )
    ).all()
    assert len(pending) == 1
    assert pending[0].resource_id == "mock-nvidia-gpu-remediate"


def test_dispatch_temporal_signal_on_approve(db_session):
    bl = ApprovalBl(SINGLE_TENANT_UUID, db_session)
    request = bl.create_external_request(
        action_type="temporal_signal",
        requested_by="alice@example.com",
        title="Remediate GPU",
        callback={
            "kind": "temporal_signal",
            "workflow_id": "wf-1",
            "run_id": "run-1",
            "signal_name": "approve",
        },
    )
    provider = MagicMock()
    provider.notify.return_value = {"ok": True}
    with patch(
        "keep.api.bl.approval_bl._get_temporal_provider", return_value=provider
    ):
        decided = bl.approve(request.id, "bob@example.com", "admin")
    assert decided.status == "approved"
    provider.notify.assert_called_once()
    kwargs = provider.notify.call_args.kwargs
    assert kwargs["operation"] == "signal_workflow"
    assert kwargs["workflow_id"] == "wf-1"
    assert kwargs["signal_name"] == "approve"
    assert kwargs["signal_args"]["approved"] is True


def test_expire_pending_marks_expired(db_session):
    request = ApprovalRequest(
        tenant_id=SINGLE_TENANT_UUID,
        action_type="custom",
        status="pending",
        title="expired",
        requested_by="alice@example.com",
        requested_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        payload_json={},
        context_json={},
        callback_json={},
        result_json={},
    )
    db_session.add(request)
    db_session.commit()
    expired = ApprovalBl(SINGLE_TENANT_UUID, db_session).expire_pending()
    assert expired == 1
    db_session.refresh(request)
    assert request.status == "expired"


def test_parser_sets_require_approval(db_session):
    workflows = Parser().parse(
        SINGLE_TENANT_UUID,
        {
            "workflow": {
                "id": "needs-approval",
                "name": "Needs approval",
                "require_approval": True,
                "triggers": [{"type": "manual"}],
                "actions": [
                    {
                        "name": "echo",
                        "provider": {
                            "type": "console",
                            "with": {"message": "hi"},
                        },
                    }
                ],
            }
        },
    )
    assert workflows
    assert workflows[0].workflow_require_approval is True
