# builtins
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field as PydanticField, validator
from sqlalchemy import DateTime, JSON

# third-parties
from sqlmodel import Column, Field, Index, SQLModel, func

from keep.api.models.alert import AlertStatus

DEFAULT_ALERT_STATUSES_TO_IGNORE = [
    AlertStatus.RESOLVED.value,
    AlertStatus.ACKNOWLEDGED.value,
]

MaintenanceRuleStatus = Literal["upcoming", "active", "expired", "disabled"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def rule_lifecycle(
    rule: "MaintenanceWindowRule", now: Optional[datetime] = None
) -> MaintenanceRuleStatus:
    current = as_utc(now or utc_now())
    if not rule.enabled:
        return "disabled"
    start = as_utc(rule.start_time)
    end = as_utc(rule.end_time)
    if current < start:
        return "upcoming"
    if current > end:
        return "expired"
    return "active"


class MaintenanceWindowRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    tenant_id: str = Field(foreign_key="tenant.id")
    description: Optional[str] = None
    created_by: str
    cel_query: str
    start_time: datetime
    end_time: datetime
    duration_seconds: Optional[int] = None
    updated_at: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True),
            name="updated_at",
            onupdate=func.now(),
            server_default=func.now(),
        )
    )
    suppress: bool = True
    enabled: bool = True
    ignore_statuses: list = Field(
        sa_column=Column(JSON),
        default_factory=lambda: list(DEFAULT_ALERT_STATUSES_TO_IGNORE),
    )
    priority: int = Field(default=0)

    __table_args__ = (
        Index("ix_maintenance_rule_tenant_id", "tenant_id"),
        Index("ix_maintenance_rule_tenant_id_end_time", "tenant_id", "end_time"),
    )


class MaintenanceRuleCreate(BaseModel):
    name: str = PydanticField(..., min_length=1)
    description: Optional[str] = None
    cel_query: str = PydanticField(..., min_length=1)
    start_time: datetime
    duration_seconds: int = PydanticField(..., gt=0)
    suppress: bool = True
    enabled: bool = True
    ignore_statuses: list[str] = DEFAULT_ALERT_STATUSES_TO_IGNORE
    priority: int = 0
    topology_service_id: Optional[str] = None
    topology_category: Optional[str] = None
    topology_reason: Optional[str] = None

    @validator("name", "cel_query")
    def not_blank(cls, value: str) -> str:
        stripped = (value or "").strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class MaintenanceRuleRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_by: str
    cel_query: str
    start_time: datetime
    end_time: datetime
    duration_seconds: Optional[int]
    updated_at: Optional[datetime]
    suppress: bool = True
    enabled: bool = True
    ignore_statuses: list[str] = DEFAULT_ALERT_STATUSES_TO_IGNORE
    priority: int = 0
    status: MaintenanceRuleStatus = "active"


class MaintenancePreviewRequest(BaseModel):
    cel_query: str = PydanticField(..., min_length=1)

    @validator("cel_query")
    def preview_cel_not_blank(cls, value: str) -> str:
        stripped = (value or "").strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class MaintenancePreviewSample(BaseModel):
    fingerprint: Optional[str] = None
    name: Optional[str] = None
    source: Optional[Any] = None
    status: Optional[str] = None


class MaintenancePreviewResponse(BaseModel):
    count: int
    sample: list[MaintenancePreviewSample]


class MaintenanceExtendRequest(BaseModel):
    duration_seconds: int = PydanticField(..., gt=0)
