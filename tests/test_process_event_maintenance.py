from datetime import datetime, timedelta, timezone

import importlib

import keep.api.bl.maintenance_windows_bl
import keep.api.consts
from keep.api.core.db import get_last_alerts
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertStatus


def _use_default_strategy(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_WINDOW_STRATEGY", "default")
    importlib.reload(keep.api.consts)
    importlib.reload(keep.api.bl.maintenance_windows_bl)


def test_process_event_suppress_keeps_alert(
    db_session, create_alert, create_window_maintenance_active, monkeypatch
):
    _use_default_strategy(monkeypatch)
    now = datetime.now(timezone.utc)
    create_window_maintenance_active(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        cel='source == "test-source"',
        suppress=True,
    )
    create_alert(
        "fp-suppress",
        AlertStatus.FIRING,
        now,
        {"source": ["test-source"]},
    )
    alerts = get_last_alerts(SINGLE_TENANT_UUID)
    matching = [alert for alert in alerts if alert.fingerprint == "fp-suppress"]
    assert len(matching) == 1
    assert matching[0].event["status"] == AlertStatus.SUPPRESSED.value


def test_process_event_hide_does_not_persist(
    db_session, create_alert, create_window_maintenance_active, monkeypatch
):
    _use_default_strategy(monkeypatch)
    now = datetime.now(timezone.utc)
    create_window_maintenance_active(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        cel='source == "test-source"',
        suppress=False,
    )
    create_alert(
        "fp-hidden",
        AlertStatus.FIRING,
        now,
        {"source": ["test-source"]},
    )
    alerts = get_last_alerts(SINGLE_TENANT_UUID)
    matching = [alert for alert in alerts if alert.fingerprint == "fp-hidden"]
    assert matching == []


def test_process_event_resolved_bypasses_window(
    db_session, create_alert, create_window_maintenance_active, monkeypatch
):
    _use_default_strategy(monkeypatch)
    now = datetime.now(timezone.utc)
    create_window_maintenance_active(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
        cel='source == "test-source"',
        suppress=True,
    )
    create_alert(
        "fp-resolved",
        AlertStatus.RESOLVED,
        now,
        {"source": ["test-source"]},
    )
    alerts = get_last_alerts(SINGLE_TENANT_UUID)
    matching = [alert for alert in alerts if alert.fingerprint == "fp-resolved"]
    assert len(matching) == 1
    assert matching[0].event["status"] == AlertStatus.RESOLVED.value
