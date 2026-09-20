import json
import logging

import celpy
from sqlmodel import Session

from keep.api.consts import KEEP_CORRELATION_ENABLED, MAINTENANCE_WINDOW_ALERT_STRATEGY
from opentelemetry import trace
from keep.api.core.db import (
    add_audit,
    get_alert_by_event_id,
    get_alerts_by_status,
    get_all_presets_dtos,
    get_last_alert_by_fingerprint,
    get_maintenance_windows_started,
    get_session_sync,
    recover_prev_alert_status,
    set_maintenance_windows_trace,
)
from keep.api.core.dependencies import get_pusher_client
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.alert import Alert, AlertAudit
from keep.api.models.db.maintenance_window import (
    MaintenanceWindowRule,
    as_utc,
    utc_now,
)
from keep.api.tasks.notification_cache import get_notification_cache
from keep.api.utils.cel_utils import preprocess_cel_expression
from keep.rulesengine.rulesengine import RulesEngine
from keep.workflowmanager.workflowmanager import WorkflowManager

tracer = trace.get_tracer(__name__)


def normalize_source(source):
    """Flatten alert source for CEL without mutating the original payload."""
    if source is None:
        return ""
    if isinstance(source, list):
        if len(source) == 0:
            return ""
        if len(source) == 1:
            item = source[0]
            return item if isinstance(item, str) else str(item)
        return [s if isinstance(s, str) else str(s) for s in source]
    if isinstance(source, str):
        return source
    return str(source)


class MaintenanceWindowsBl:

    def __init__(self, tenant_id: str, session: Session | None) -> None:
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.session = session if session else get_session_sync()
        now = utc_now()
        rules = (
            self.session.query(MaintenanceWindowRule)
            .filter(MaintenanceWindowRule.tenant_id == tenant_id)
            .filter(MaintenanceWindowRule.enabled == True)
            .filter(MaintenanceWindowRule.end_time >= now)
            .filter(MaintenanceWindowRule.start_time <= now)
            .all()
        )
        # Sort in Python so mocked query chains in tests stay compatible.
        self.maintenance_rules: list[MaintenanceWindowRule] = sorted(
            rules,
            key=lambda rule: (-(rule.priority or 0), rule.id or 0),
        )

    def check_if_alert_in_maintenance_windows(self, alert: AlertDto) -> bool:
        extra = {"tenant_id": self.tenant_id, "fingerprint": alert.fingerprint}

        if not self.maintenance_rules:
            self.logger.debug(
                "No maintenance window rules for this tenant",
                extra={"tenant_id": self.tenant_id},
            )
            return False

        self.logger.info("Checking maintenance window for alert", extra=extra)
        env = celpy.Environment()

        for maintenance_rule in self.maintenance_rules:
            ignore_statuses = maintenance_rule.ignore_statuses or []
            if alert.status in ignore_statuses:
                self.logger.debug(
                    "Alert status is set to be ignored, ignoring maintenance windows",
                    extra={"tenant_id": self.tenant_id},
                )
                continue

            if as_utc(maintenance_rule.end_time) <= utc_now():
                self.logger.error(
                    "Fetched maintenance window which already ended by mistake, should not happen!"
                )
                continue

            cel_result = MaintenanceWindowsBl.evaluate_cel(
                maintenance_rule, alert, env, self.logger, extra
            )

            if cel_result:
                self.logger.info(
                    "Alert is in maintenance window",
                    extra={**extra, "maintenance_rule_id": maintenance_rule.id},
                )

                try:
                    audit = AlertAudit(
                        tenant_id=self.tenant_id,
                        fingerprint=alert.fingerprint,
                        user_id="Keep",
                        action=ActionType.MAINTENANCE.value,
                        description=(
                            f"Alert in maintenance due to rule `{maintenance_rule.name}`"
                            if not maintenance_rule.suppress
                            else f"Alert suppressed due to maintenance rule `{maintenance_rule.name}`"
                        ),
                    )
                    self.session.add(audit)
                    self.session.commit()
                except Exception:
                    self.logger.exception(
                        "Failed to write audit for alert maintenance window",
                        extra={
                            "tenant_id": self.tenant_id,
                            "fingerprint": alert.fingerprint,
                        },
                    )

                if maintenance_rule.suppress:
                    # If user chose to suppress the alert, let it in but override the status.
                    if MAINTENANCE_WINDOW_ALERT_STRATEGY == "recover_previous_status":
                        alert.previous_status = alert.status
                        alert.status = AlertStatus.MAINTENANCE.value
                    else:
                        alert.status = AlertStatus.SUPPRESSED.value
                    return False

                return True
        self.logger.info("Alert is not in maintenance window", extra=extra)
        return False

    @staticmethod
    def evaluate_cel(
        maintenance_window: MaintenanceWindowRule,
        alert: AlertDto | Alert,
        environment: celpy.Environment,
        logger,
        logger_extra_info: dict,
    ) -> bool:

        cel = preprocess_cel_expression(maintenance_window.cel_query)
        try:
            ast = environment.compile(cel)
            prgm = environment.program(ast)
        except Exception as e:
            logger.error(
                f"Failed to compile maintenance window CEL: {str(e)}",
                extra={
                    **logger_extra_info,
                    "maintenance_rule_id": maintenance_window.id,
                },
            )
            return False

        if isinstance(alert, AlertDto):
            payload = alert.dict()
        else:
            payload = dict(alert.event or {})
        payload["source"] = normalize_source(payload.get("source"))

        activation = celpy.json_to_cel(json.loads(json.dumps(payload, default=str)))

        try:
            cel_result = prgm.evaluate(activation)
            return True if cel_result else False
        except celpy.evaluation.CELEvalError as e:
            error_msg = str(e).lower()
            if "no such member" in error_msg or "undeclared reference" in error_msg:
                logger.debug(
                    f"Skipping maintenance window rule due to missing field: {str(e)}",
                    extra={
                        **logger_extra_info,
                        "maintenance_rule_id": maintenance_window.id,
                    },
                )
                return False
            logger.error(
                f"Unexpected CEL evaluation error: {str(e)}",
                extra={
                    **logger_extra_info,
                    "maintenance_rule_id": maintenance_window.id,
                },
            )
            return False

    @staticmethod
    def recover_strategy(
        logger: logging.Logger,
        session: Session | None = None,
    ):
        """
        Recover the previous status of alerts that were in maintenance windows
        once the window has expired (end time passed) or been disabled.
        """
        logger.info("Starting recover strategy for maintenance windows review.")
        env = celpy.Environment()
        _owns_session = session is None
        if session is None:
            session = get_session_sync()
        try:
            windows = get_maintenance_windows_started(session)
            alerts_in_maint = get_alerts_by_status(AlertStatus.MAINTENANCE, session)
            fingerprints_to_check: set = set()
            now = utc_now()
            for alert in alerts_in_maint:
                active = False
                for window in windows:
                    if window.tenant_id != alert.tenant_id:
                        continue
                    w_start = as_utc(window.start_time)
                    w_end = as_utc(window.end_time)
                    alert_ts = as_utc(alert.timestamp)
                    is_enable = window.enabled
                    # Still active when the window covers the alert and has not expired.
                    if (
                        w_start < alert_ts
                        and alert_ts < w_end
                        and w_end > now
                        and is_enable
                    ):
                        logger.info(
                            "Checking alert %s in maintenance window %s",
                            alert.id,
                            window.id,
                        )
                        is_in_cel = MaintenanceWindowsBl.evaluate_cel(
                            window,
                            alert,
                            env,
                            logger,
                            {"tenant_id": alert.tenant_id, "alert_id": alert.id},
                        )
                        if is_in_cel:
                            active = True
                            set_maintenance_windows_trace(alert, window, session)
                            logger.info(
                                "Alert %s is blocked due to the maintenance window: %s.",
                                alert.id,
                                window.id,
                            )
                            break
                if not active:
                    recover_prev_alert_status(alert, session)
                    fingerprints_to_check.add((alert.tenant_id, alert.fingerprint))
                    add_audit(
                        tenant_id=alert.tenant_id,
                        fingerprint=alert.fingerprint,
                        user_id="system",
                        action=ActionType.MAINTENANCE_EXPIRED,
                        description=(
                            f"Alert {alert.id} has recover its previous status, "
                            f"from {alert.event.get('previous_status')} to {alert.event.get('status')}"
                        ),
                    )

            for (tenant, fp) in fingerprints_to_check:
                last_alert = get_last_alert_by_fingerprint(tenant, fp, session)
                alert = get_alert_by_event_id(tenant, str(last_alert.alert_id), session)
                if "previous_status" not in alert.event:
                    logger.info(
                        f"Alert {alert.id} does not have previous status, cannot proceed with recover strategy",
                        extra={
                            "tenant_id": tenant,
                            "fingerprint": fp,
                            "alert_id": alert.id,
                            "alert.status": alert.event.get("status"),
                        },
                    )
                    continue
                source = alert.event.get("source")
                if not isinstance(source, list):
                    alert.event["source"] = [source] if source else []
                alert_dto = AlertDto(**alert.event)
                with tracer.start_as_current_span("mw_recover_strategy_push_to_workflows"):
                    try:
                        workflow_manager = WorkflowManager.get_instance()
                        logger.info("Adding event to the workflow manager queue")
                        workflow_manager.insert_events(tenant, [alert_dto])
                        logger.info("Added event to the workflow manager queue")
                    except Exception:
                        logger.exception(
                            "Failed to run workflows based on alerts",
                            extra={
                                "provider_type": alert_dto.providerType,
                                "provider_id": alert_dto.providerId,
                                "tenant_id": tenant,
                            },
                        )

                with tracer.start_as_current_span("mw_recover_strategy_run_rules_engine"):
                    if KEEP_CORRELATION_ENABLED:
                        incidents = []
                        try:
                            rules_engine = RulesEngine(tenant_id=tenant)
                            incidents = rules_engine.run_rules(
                                [alert_dto], session=session
                            )
                        except Exception:
                            logger.exception(
                                "Failed to run rules engine",
                                extra={
                                    "provider_type": alert_dto.providerType,
                                    "provider_id": alert_dto.providerId,
                                    "tenant_id": tenant,
                                },
                            )
                        pusher_cache = get_notification_cache()
                        if incidents and pusher_cache.should_notify(tenant, "incident-change"):
                            pusher_client = get_pusher_client()
                            try:
                                pusher_client.trigger(
                                    f"private-{tenant}",
                                    "incident-change",
                                    {},
                                )
                            except Exception:
                                logger.exception("Failed to tell the client to pull incidents")

                    try:
                        presets = get_all_presets_dtos(tenant)
                        rules_engine = RulesEngine(tenant_id=tenant)
                        presets_do_update = []
                        for preset_dto in presets:
                            filtered_alerts = rules_engine.filter_alerts(
                                [alert_dto], preset_dto.cel_query
                            )
                            if not filtered_alerts:
                                continue
                            presets_do_update.append(preset_dto)
                        if pusher_cache.should_notify(tenant, "poll-presets"):
                            try:
                                pusher_client.trigger(
                                    f"private-{tenant}",
                                    "poll-presets",
                                    json.dumps(
                                        [p.name.lower() for p in presets_do_update],
                                        default=str,
                                    ),
                                )
                            except Exception:
                                logger.exception("Failed to send presets via pusher")
                    except Exception:
                        logger.exception(
                            "Failed to send presets via pusher",
                            extra={
                                "provider_type": alert_dto.providerType,
                                "provider_id": alert_dto.providerId,
                                "tenant_id": tenant,
                            },
                        )
            logger.info("Finished recover strategy for maintenance windows review.")
        finally:
            if _owns_session:
                session.close()
