from keep.api.models.db.alert_catalog import normalize_alert_catalog_tags


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
