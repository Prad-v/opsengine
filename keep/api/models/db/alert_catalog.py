from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field as PydanticField, validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from keep.api.utils.alert_code import slugify_alert_code

AlertCatalogAutoRunOn = Literal["none", "alert", "incident", "both", "approval"]


class AlertCatalog(SQLModel, table=True):
    """Keep-managed registry of alert codes and the workflows they auto-run."""

    __tablename__ = "alertcatalog"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_alertcatalog_tenant_code",
        ),
    )

    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    code: str = Field(max_length=255, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(max_length=2048, default=None)
    runbook_url: Optional[str] = Field(max_length=2048, default=None)
    keep_workflow_id: Optional[str] = Field(max_length=255, default=None)
    auto_run_on: str = Field(max_length=32, default="none")
    disabled: bool = Field(default=False)
    created_by: Optional[str] = Field(max_length=255, default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    updated_by: Optional[str] = Field(max_length=255, default=None)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class AlertCatalogDtoBase(BaseModel):
    code: str = PydanticField(..., min_length=1, max_length=255)
    name: str = PydanticField(..., min_length=1, max_length=255)
    description: Optional[str] = None
    runbook_url: Optional[str] = None
    keep_workflow_id: Optional[str] = None
    auto_run_on: AlertCatalogAutoRunOn = "none"
    disabled: bool = False

    @validator("code", pre=True)
    def normalize_code(cls, value):
        code = slugify_alert_code(value if isinstance(value, str) else None)
        if not code:
            raise ValueError("code is required")
        return code

    @validator("keep_workflow_id", pre=True)
    def empty_workflow_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("runbook_url", pre=True)
    def empty_runbook_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("auto_run_on", pre=True, always=True)
    def default_auto_run(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return "none"
        allowed = {"none", "alert", "incident", "both", "approval"}
        if value not in allowed:
            raise ValueError(f"auto_run_on must be one of {sorted(allowed)}")
        return value


class AlertCatalogDtoOut(AlertCatalogDtoBase, extra="ignore"):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: datetime


class AlertCatalogDtoIn(AlertCatalogDtoBase):
    pass


class AlertCatalogUpdateDtoIn(AlertCatalogDtoBase):
    pass


class EnhanceAlertCatalogDescriptionDtoIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    runbook_url: Optional[str] = None
    keep_workflow_id: Optional[str] = None


class EnhanceAlertCatalogDescriptionDtoOut(BaseModel):
    description: str
    model: Optional[str] = None
