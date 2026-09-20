"""Apply the reserved-code alert catalog: enrich + optional Keep workflow auto-run."""

from __future__ import annotations

import logging
from typing import Iterable, Literal

from sqlmodel import Session, select

from keep.api.core.db import get_enrichment, get_workflow_by_id
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert_catalog import AlertCatalog
from keep.api.models.incident import IncidentDto
from keep.api.utils.alert_code import (
    collect_codes,
    get_alert_code,
    merge_incident_codes,
    normalize_alert_code,
)

logger = logging.getLogger(__name__)

Context = Literal["alert", "incident"]


def get_catalog_by_code(
    session: Session, tenant_id: str, code: str
) -> AlertCatalog | None:
    return session.exec(
        select(AlertCatalog).where(
            AlertCatalog.tenant_id == tenant_id,
            AlertCatalog.code == code,
        )
    ).first()


class AlertCatalogBl:
    def __init__(self, tenant_id: str, session: Session | None = None):
        self.tenant_id = tenant_id
        self.session = session

    def apply_to_alert(self, alert: AlertDto, persist: bool = True) -> AlertDto:
        normalize_alert_code(alert)
        code = get_alert_code(alert)
        if not code or self.session is None:
            return alert
        entry = get_catalog_by_code(self.session, self.tenant_id, code)
        if entry is None or entry.disabled:
            return alert

        enrichments: dict = {
            "alert_catalog_code": entry.code,
            "alert_catalog_name": entry.name,
        }
        if entry.runbook_url:
            enrichments["playbook_url"] = entry.runbook_url

        for key, value in enrichments.items():
            setattr(alert, key, value)

        if persist:
            from keep.api.bl.enrichments_bl import EnrichmentsBl

            EnrichmentsBl(self.tenant_id, self.session).enrich_entity(
                fingerprint=alert.fingerprint,
                enrichments=enrichments,
                action_type=ActionType.ALERT_CATALOG_ENRICH,
                action_callee="system",
                action_description=f"Alert enriched from catalog code `{entry.code}`",
                should_exist=False,
            )

        self._maybe_auto_run("alert", entry, alert)
        return alert

    def apply_to_incident(
        self,
        incident: IncidentDto,
        alerts: Iterable[AlertDto] | None = None,
        persist: bool = True,
        trigger: str = "updated",
    ) -> IncidentDto:
        new_codes = collect_codes(alerts or [])
        existing = getattr(incident, "codes", None) or []
        if not existing and incident.enrichments:
            existing = incident.enrichments.get("codes") or []
        existing_primary = getattr(incident, "code", None)
        if not existing_primary and incident.enrichments:
            existing_primary = incident.enrichments.get("code")
        primary, codes = merge_incident_codes(existing, new_codes, existing_primary)
        incident.code = primary
        incident.codes = codes

        enrichments = {"code": primary, "codes": codes}
        if persist and (primary or codes):
            from keep.api.bl.enrichments_bl import EnrichmentsBl

            EnrichmentsBl(self.tenant_id, self.session).enrich_entity(
                fingerprint=str(incident.id),
                enrichments=enrichments,
                action_type=ActionType.INCIDENT_ENRICH,
                action_callee="system",
                action_description="Incident enriched with reserved alert codes",
                force=True,
            )
            if incident.enrichments is None:
                incident.enrichments = {}
            incident.enrichments.update(enrichments)

        already_run = set()
        if incident.enrichments:
            already_run = set(incident.enrichments.get("alert_catalog_auto_runs") or [])

        if self.session is None:
            return incident

        newly_run: list[str] = []
        for code in codes:
            entry = get_catalog_by_code(self.session, self.tenant_id, code)
            if entry is None or entry.disabled:
                continue
            if trigger == "created" or code not in already_run:
                self._maybe_auto_run("incident", entry, incident)
                newly_run.append(code)

        if persist and newly_run:
            next_runs = sorted(already_run.union(newly_run))
            from keep.api.bl.enrichments_bl import EnrichmentsBl

            EnrichmentsBl(self.tenant_id, self.session).enrich_entity(
                fingerprint=str(incident.id),
                enrichments={"alert_catalog_auto_runs": next_runs},
                action_type=ActionType.INCIDENT_ENRICH,
                action_callee="system",
                action_description="Recorded alert-catalog auto-runs for incident",
                force=True,
            )
            if incident.enrichments is None:
                incident.enrichments = {}
            incident.enrichments["alert_catalog_auto_runs"] = next_runs

        return incident

    def _maybe_auto_run(
        self, context: Context, entry: AlertCatalog, event: AlertDto | IncidentDto
    ) -> None:
        if not entry.keep_workflow_id:
            return
        if entry.auto_run_on == "approval":
            self._propose_approval_run(context, entry, event)
            return
        if entry.auto_run_on not in (context, "both"):
            return
        workflow = get_workflow_by_id(self.tenant_id, entry.keep_workflow_id)
        if workflow is None or workflow.is_disabled:
            logger.warning(
                "Alert catalog workflow missing or disabled",
                extra={
                    "tenant_id": self.tenant_id,
                    "code": entry.code,
                    "keep_workflow_id": entry.keep_workflow_id,
                },
            )
            return
        from keep.workflowmanager.workflowmanager import WorkflowManager

        WorkflowManager.get_instance().enqueue_workflow(
            tenant_id=self.tenant_id,
            workflow_id=entry.keep_workflow_id,
            event=event,
            triggered_by=f"alert-catalog:{context}:{entry.code}",
        )

    def _propose_approval_run(
        self, context: Context, entry: AlertCatalog, event: AlertDto | IncidentDto
    ) -> None:
        from keep.api.bl.approval_bl import ApprovalBl

        fingerprint = getattr(event, "fingerprint", None) or str(
            getattr(event, "id", "") or ""
        )
        try:
            event_payload = event.dict()
        except Exception:
            event_payload = {}
        bl = ApprovalBl(self.tenant_id, self.session)
        try:
            bl.gate(
                action_type="run_workflow",
                requested_by="alert-catalog",
                title=f"Run {entry.keep_workflow_id} for {entry.code}",
                summary=f"Catalog auto-run is set to approval ({context})",
                payload={
                    "workflow_id": entry.keep_workflow_id,
                    "event_type": context,
                    "event": event_payload,
                    "triggered_by": f"approval:alert-catalog:{context}:{entry.code}",
                },
                context={"code": entry.code, "context": context},
                resource_type="workflow",
                resource_id=entry.keep_workflow_id,
                callback={
                    "kind": "keep_action",
                    "workflow_id": entry.keep_workflow_id,
                },
                idempotency_key=f"alert-catalog:{context}:{entry.code}:{fingerprint}",
                force=True,
            )
        finally:
            bl.close()
