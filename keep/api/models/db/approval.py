from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field as PydanticField, validator
from sqlalchemy import Column, DateTime, Index, JSON
from sqlmodel import Field, SQLModel, func

APPROVAL_ACTION_TYPES = (
    "create_maintenance",
    "node_maintenance",
    "run_workflow",
    "delete_resource",
    "temporal_signal",
    "webhook",
    "custom",
)

ApprovalActionType = Literal[
    "create_maintenance",
    "node_maintenance",
    "run_workflow",
    "delete_resource",
    "temporal_signal",
    "webhook",
    "custom",
]

ApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "expired",
    "cancelled",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalPolicy(SQLModel, table=True):
    __tablename__ = "approvalpolicy"
    __table_args__ = (
        Index("ix_approvalpolicy_tenant_action", "tenant_id", "action_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    name: str = Field(max_length=255)
    action_type: str = Field(max_length=64)
    resource_type: Optional[str] = Field(default=None, max_length=64)
    cel: Optional[str] = Field(default=None, max_length=4096)
    enabled: bool = Field(default=True)
    approver_roles: list = Field(default_factory=list, sa_column=Column(JSON))
    approver_emails: list = Field(default_factory=list, sa_column=Column(JSON))
    allow_self_approve: bool = Field(default=False)
    timeout_seconds: Optional[int] = Field(default=None)
    priority: int = Field(default=0)
    min_approvals: int = Field(default=1)
    created_by: Optional[str] = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now)
    updated_by: Optional[str] = Field(default=None, max_length=255)
    updated_at: datetime = Field(default_factory=utc_now)


class ApprovalRequest(SQLModel, table=True):
    __tablename__ = "approvalrequest"
    __table_args__ = (
        Index("ix_approvalrequest_tenant_status", "tenant_id", "status"),
        Index(
            "ix_approvalrequest_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    policy_id: Optional[int] = Field(default=None, foreign_key="approvalpolicy.id")
    action_type: str = Field(max_length=64)
    status: str = Field(default="pending", max_length=32)
    title: str = Field(max_length=512)
    summary: Optional[str] = Field(default=None, max_length=2048)
    resource_type: Optional[str] = Field(default=None, max_length=64)
    resource_id: Optional[str] = Field(default=None, max_length=255)
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    callback_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    result_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    idempotency_key: Optional[str] = Field(default=None, max_length=512)
    requested_by: str = Field(max_length=255)
    requested_at: datetime = Field(default_factory=utc_now)
    decided_by: Optional[str] = Field(default=None, max_length=255)
    decided_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    decision_comment: Optional[str] = Field(default=None, max_length=2048)
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
        )
    )


def _not_blank(value: str) -> str:
    stripped = (value or "").strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _validate_action_type(value: str) -> str:
    if value not in APPROVAL_ACTION_TYPES:
        raise ValueError(f"action_type must be one of {sorted(APPROVAL_ACTION_TYPES)}")
    return value


class ApprovalPolicyDtoBase(BaseModel):
    name: str = PydanticField(..., min_length=1, max_length=255)
    action_type: ApprovalActionType
    resource_type: Optional[str] = None
    cel: Optional[str] = None
    enabled: bool = True
    approver_roles: list[str] = PydanticField(default_factory=list)
    approver_emails: list[str] = PydanticField(default_factory=list)
    allow_self_approve: bool = False
    timeout_seconds: Optional[int] = PydanticField(default=None, gt=0)
    priority: int = 0
    min_approvals: int = PydanticField(default=1, ge=1)

    @validator("name")
    def name_not_blank(cls, value: str) -> str:
        return _not_blank(value)

    @validator("action_type")
    def action_type_allowed(cls, value: str) -> str:
        return _validate_action_type(value)

    @validator("cel", "resource_type", pre=True)
    def empty_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @validator("approver_roles", "approver_emails", pre=True, always=True)
    def list_or_empty(cls, value):
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]


class ApprovalPolicyDtoIn(ApprovalPolicyDtoBase):
    pass


class ApprovalPolicyDtoOut(ApprovalPolicyDtoBase, extra="ignore"):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: datetime


class ApprovalCallbackDto(BaseModel):
    kind: Literal["keep_action", "temporal_signal", "webhook"] = "keep_action"
    workflow_id: Optional[str] = None
    provider_id: Optional[str] = None
    run_id: Optional[str] = None
    signal_name: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[dict[str, str]] = None


class ApprovalRequestCreateDto(BaseModel):
    action_type: ApprovalActionType
    title: str = PydanticField(..., min_length=1, max_length=512)
    summary: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    payload: dict[str, Any] = PydanticField(default_factory=dict)
    context: dict[str, Any] = PydanticField(default_factory=dict)
    callback: Optional[dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    force: bool = True

    @validator("title")
    def title_not_blank(cls, value: str) -> str:
        return _not_blank(value)

    @validator("action_type")
    def action_type_allowed(cls, value: str) -> str:
        return _validate_action_type(value)


class ApprovalRequestDtoOut(BaseModel, extra="ignore"):
    id: int
    policy_id: Optional[int] = None
    action_type: str
    status: str
    title: str
    summary: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    payload: dict[str, Any] = PydanticField(default_factory=dict)
    context: dict[str, Any] = PydanticField(default_factory=dict)
    callback: dict[str, Any] = PydanticField(default_factory=dict)
    result: dict[str, Any] = PydanticField(default_factory=dict)
    idempotency_key: Optional[str] = None
    requested_by: str
    requested_at: datetime
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_comment: Optional[str] = None
    expires_at: Optional[datetime] = None


class ApprovalDecisionDto(BaseModel):
    comment: Optional[str] = None


class ApprovalPendingResponse(BaseModel):
    status: Literal["pending"] = "pending"
    request_id: int
    approval: ApprovalRequestDtoOut
