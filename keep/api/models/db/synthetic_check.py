"""Synthetic check definitions (blackbox-style probes driven by Temporal)."""

from datetime import datetime, timezone
from typing import Any, Literal, Optional
import re
import uuid

from pydantic import BaseModel, Field as PydanticField, validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

ProberType = Literal["http", "tcp", "dns"]
ALLOWED_PROBERS = ("http", "tcp", "dns")

DEFAULT_TASK_QUEUE = "keep-synth"
DEFAULT_INTERVAL_SECONDS = 60


def slugify_check_key(value: str) -> str:
    """Build a stable check key from a display name."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or f"check-{uuid.uuid4().hex[:8]}"


class SyntheticCheck(SQLModel, table=True):
    """Keep-managed synthetic check (Mode 1: API + Temporal Schedule)."""

    __tablename__ = "syntheticcheck"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "check_key",
            name="uq_syntheticcheck_tenant_key",
        ),
    )

    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    check_key: str = Field(max_length=255, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(max_length=2048, default=None)
    prober: str = Field(max_length=32, nullable=False)
    module_config: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    targets: Optional[list] = Field(default_factory=list, sa_column=Column(JSON))
    interval_seconds: int = Field(default=DEFAULT_INTERVAL_SECONDS)
    labels: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    task_queue: str = Field(max_length=255, default=DEFAULT_TASK_QUEUE)
    temporal_provider_id: str = Field(max_length=255, nullable=False, index=True)
    schedule_id: Optional[str] = Field(max_length=255, default=None)
    last_results: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    enabled: bool = Field(default=True)
    created_by: Optional[str] = Field(max_length=255, default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    updated_by: Optional[str] = Field(max_length=255, default=None)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class SyntheticCheckDtoBase(BaseModel):
    check_key: Optional[str] = PydanticField(
        default=None,
        max_length=255,
        description="Stable slug unique per tenant (auto-generated from name if omitted)",
    )
    name: str = PydanticField(..., min_length=1, max_length=255)
    description: Optional[str] = None
    prober: str = PydanticField(..., min_length=1, max_length=32)
    module_config: Optional[dict[str, Any]] = None
    targets: list[str] = PydanticField(default_factory=list)
    interval_seconds: int = PydanticField(
        default=DEFAULT_INTERVAL_SECONDS, ge=10, le=86400
    )
    labels: Optional[dict[str, str]] = None
    task_queue: str = PydanticField(default=DEFAULT_TASK_QUEUE, min_length=1, max_length=255)
    temporal_provider_id: str = PydanticField(..., min_length=1, max_length=255)
    enabled: bool = True

    @validator("check_key", pre=True)
    def empty_check_key_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("prober")
    def validate_prober(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in ALLOWED_PROBERS:
            raise ValueError(f"prober must be one of {ALLOWED_PROBERS}")
        return normalized

    @validator("targets", pre=True)
    def normalize_targets(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise ValueError("targets must be a list of strings")

    @validator("task_queue", pre=True, always=True)
    def default_task_queue(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_TASK_QUEUE
        return value


class SyntheticCheckDtoOut(SyntheticCheckDtoBase, extra="ignore"):
    id: int
    check_key: str
    schedule_id: Optional[str] = None
    last_results: Optional[dict[str, Any]] = None
    provider_name: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: datetime


class SyntheticCheckDtoIn(SyntheticCheckDtoBase):
    pass


class SyntheticCheckUpdateDtoIn(SyntheticCheckDtoBase):
    pass


class SyntheticCheckRunResult(BaseModel):
    workflow_id: str
    run_id: Optional[str] = None
    task_queue: str
    workflow_type: str
    namespace: Optional[str] = None
    check_id: int
    check_key: str
