from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field as PydanticField, validator
from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, JSON, SQLModel

from keep.api.utils.alert_code import slugify_alert_code

AlertCatalogAutoRunOn = Literal["none", "alert", "incident", "both", "approval"]

AlertCatalogDomain = Literal[
    "thermal",
    "power",
    "memory",
    "reliability",
    "compute",
    "fabric",
    "pcie",
    "diagnostics",
    "software",
    "workload",
    "capacity",
    "security",
    "infrastructure",
]

AlertCatalogRole = Literal[
    "symptom",
    "root_cause",
    "capacity_signal",
    "informational",
    "performance",
]

ALERT_CATALOG_DOMAINS: frozenset[str] = frozenset(
    {
        "thermal",
        "power",
        "memory",
        "reliability",
        "compute",
        "fabric",
        "pcie",
        "diagnostics",
        "software",
        "workload",
        "capacity",
        "security",
        "infrastructure",
    }
)

ALERT_CATALOG_ROLES: frozenset[str] = frozenset(
    {
        "symptom",
        "root_cause",
        "capacity_signal",
        "informational",
        "performance",
    }
)


def normalize_alert_catalog_tags(value) -> list[str]:
    """Trim, lowercase, and dedupe catalog tags."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, (list, tuple)):
        raise ValueError("tags must be a list of strings")
    seen: set[str] = set()
    tags: list[str] = []
    for item in value:
        if item is None:
            continue
        if not isinstance(item, str):
            raise ValueError("tags must be a list of strings")
        tag = item.strip().lower()
        if not tag or tag in seen:
            continue
        if len(tag) > 64:
            raise ValueError("each tag must be at most 64 characters")
        seen.add(tag)
        tags.append(tag)
    return tags


def normalize_alert_catalog_domain(value) -> Optional[str]:
    """Normalize optional catalog domain to a controlled value."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("domain must be a string")
    domain = value.strip().lower()
    if not domain:
        return None
    if domain not in ALERT_CATALOG_DOMAINS:
        raise ValueError(
            f"domain must be one of {sorted(ALERT_CATALOG_DOMAINS)}"
        )
    return domain


def normalize_alert_catalog_role(value) -> Optional[str]:
    """Normalize optional catalog role to a controlled value."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("role must be a string")
    role = value.strip().lower()
    if not role:
        return None
    if role not in ALERT_CATALOG_ROLES:
        raise ValueError(f"role must be one of {sorted(ALERT_CATALOG_ROLES)}")
    return role


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
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    # Subsystem taxonomy (orthogonal to role). See ALERT_CATALOG_DOMAINS.
    domain: Optional[str] = Field(max_length=64, default=None)
    # Diagnostic / triage role (orthogonal to domain). See ALERT_CATALOG_ROLES.
    role: Optional[str] = Field(max_length=64, default=None)
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
    tags: List[str] = PydanticField(default_factory=list)
    domain: Optional[AlertCatalogDomain] = None
    role: Optional[AlertCatalogRole] = None

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

    @validator("tags", pre=True, always=True)
    def normalize_tags(cls, value):
        return normalize_alert_catalog_tags(value)

    @validator("domain", pre=True, always=True)
    def normalize_domain(cls, value):
        return normalize_alert_catalog_domain(value)

    @validator("role", pre=True, always=True)
    def normalize_role(cls, value):
        return normalize_alert_catalog_role(value)


class AlertCatalogDtoOut(AlertCatalogDtoBase, extra="ignore"):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_by: Optional[str] = None
    updated_at: datetime

    @validator("tags", pre=True, always=True)
    def normalize_tags_out(cls, value):
        return normalize_alert_catalog_tags(value)


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
