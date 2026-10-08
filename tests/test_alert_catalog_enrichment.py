from datetime import datetime, timezone

from keep.api.bl.alert_catalog_bl import AlertCatalogBl
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.db.alert_catalog import AlertCatalog


def test_apply_to_alert_copies_domain_and_role(db_session):
    db_session.add(
        AlertCatalog(
            tenant_id=SINGLE_TENANT_UUID,
            code="DCGM_FI_DEV_GPU_TEMP",
            name="DCGM GPU temperature",
            runbook_url="https://wiki.example/gpu-thermal",
            domain="thermal",
            role="symptom",
            tags=["nvidia", "thermal"],
            auto_run_on="none",
        )
    )
    db_session.commit()

    alert = AlertDto(
        name="NVIDIA GPU thermal",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=datetime.now(timezone.utc).isoformat(),
        source=["prometheus"],
        fingerprint="fp-gpu-enrich-1",
        labels={"code": "DCGM_FI_DEV_GPU_TEMP"},
    )
    AlertCatalogBl(SINGLE_TENANT_UUID, db_session).apply_to_alert(
        alert, persist=False
    )

    assert alert.alert_catalog_code == "DCGM_FI_DEV_GPU_TEMP"
    assert alert.alert_catalog_name == "DCGM GPU temperature"
    assert alert.playbook_url == "https://wiki.example/gpu-thermal"
    assert alert.alert_catalog_domain == "thermal"
    assert alert.alert_catalog_role == "symptom"
