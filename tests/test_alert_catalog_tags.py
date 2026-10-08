import pytest

from keep.api.models.db.alert_catalog import (
    normalize_alert_catalog_domain,
    normalize_alert_catalog_role,
    normalize_alert_catalog_tags,
)


def test_normalize_alert_catalog_tags_dedupes_and_lowercases():
    assert normalize_alert_catalog_tags(None) == []
    assert normalize_alert_catalog_tags("nvidia, Thermal, nvidia") == [
        "nvidia",
        "thermal",
    ]
    assert normalize_alert_catalog_tags(["ECC", " ecc ", "", "memory"]) == [
        "ecc",
        "memory",
    ]


def test_normalize_alert_catalog_domain():
    assert normalize_alert_catalog_domain(None) is None
    assert normalize_alert_catalog_domain("") is None
    assert normalize_alert_catalog_domain("  Thermal ") == "thermal"
    with pytest.raises(ValueError):
        normalize_alert_catalog_domain("not-a-domain")


def test_normalize_alert_catalog_role():
    assert normalize_alert_catalog_role(None) is None
    assert normalize_alert_catalog_role("") is None
    assert normalize_alert_catalog_role("Root_Cause") == "root_cause"
    with pytest.raises(ValueError):
        normalize_alert_catalog_role("not-a-role")
