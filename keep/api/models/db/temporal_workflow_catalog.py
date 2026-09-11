from datetime import datetime, timezone
from typing import Optional
import re
import uuid

from pydantic import BaseModel, Field as PydanticField, validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

DEFAULT_WORKFLOW_ID_TEMPLATE = "incident-{{incident.id}}-{{catalog.id}}"


def slugify_catalog_key(value: str) -> str:
    """Build a stable catalog key from a display name."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or f"workflow-{uuid.uuid4().hex[:8]}"


class TemporalWorkflowCatalog(SQLModel, table=True):
    """Keep-managed registry of Temporal workflows available to start from incidents."""

    __tablename__ = "temporalworkflowcatalog"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "catalog_key",
            name="uq_temporalworkflowcatalog_tenant_key",
        ),
    )

    id: Optional[int] = Field(primary_key=True, default=None)
    tenant_id: str = Field(foreign_key="tenant.id", index=True)
    # Stable slug used in templates / incident links (unique per tenant)
    catalog_key: str = Field(max_length=255, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(max_length=2048, default=None)
    workflow_type: str = Field(max_length=255, nullable=False)
    task_queue: str = Field(max_length=255, nullable=False)
    workflow_id_template: Optional[str] = Field(
        max_length=1024,
        default=DEFAULT_WORKFLOW_ID_TEMPLATE,
    )
    input_mapping: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    provider_id: str = Field(max_length=255, nullable=False, index=True)
    disabled: bool = Field(default=False)
    created_by: Optional[str] = Field(max_length=255, default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    updated_by: Optional[str] = Field(max_length=255, default=None)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class TemporalWorkflowCatalogDtoBase(BaseModel):
    # Optional on create — server generates from name when omitted
    catalog_key: Optional[str] = PydanticField(
        default=None,
        max_length=255,
        description="Stable catalog id / slug unique per tenant (auto-generated from name if omitted)",
    )
    name: str = PydanticField(..., min_length=1, max_length=255)
    description: Optional[str] = None
    workflow_type: str = PydanticField(..., min_length=1, max_length=255)
    task_queue: str = PydanticField(..., min_length=1, max_length=255)
    workflow_id_template: Optional[str] = DEFAULT_WORKFLOW_ID_TEMPLATE
    input_mapping: Optional[dict[str, str]] = None
    provider_id: str = PydanticField(..., min_length=1, max_length=255)
    disabled: bool = False

    @validator("catalog_key", pre=True)
    def empty_catalog_key_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @validator("workflow_id_template", pre=True, always=True)
    def default_workflow_id_template(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_WORKFLOW_ID_TEMPLATE
        return value


class TemporalWorkflowCatalogDtoOut(TemporalWorkflowCatalogDtoBase, extra="ignore"):
    id: int
    catalog_key: str
    provider_name: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: datetime


class TemporalWorkflowCatalogDtoIn(TemporalWorkflowCatalogDtoBase):
    pass


class TemporalWorkflowCatalogUpdateDtoIn(TemporalWorkflowCatalogDtoBase):
    pass


class StartTemporalWorkflowRequest(BaseModel):
    incident_id: str
