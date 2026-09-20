"""Reserved alert `code` — stable identity for catalogs, runbooks, and workflows.

Name and description are free-form display text. `code` is the join key.
Canonical storage is both `alert.code` and `alert.labels.code`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

RESERVED_ALERT_CODE_LABEL = "code"


def slugify_alert_code(value: str | None) -> str:
    """Normalize a code to UPPER_SNAKE (splits camelCase)."""
    if not value or not str(value).strip():
        return ""
    raw = str(value).strip()
    # Already UPPER_SNAKE (or all-caps with digits) — do not split 5XX → 5_XX.
    if re.fullmatch(r"[A-Z0-9_]+", raw):
        return re.sub(r"_+", "_", raw).strip("_")
    split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", split_camel).strip("_")
    return slug.upper()


def _labels_dict(alert: Any) -> dict:
    labels = getattr(alert, "labels", None)
    if labels is None and isinstance(alert, dict):
        labels = alert.get("labels")
    if not isinstance(labels, dict):
        return {}
    return labels


def get_alert_code(alert: Any) -> str | None:
    """Read the reserved code from an alert DTO or dict (either field)."""
    if alert is None:
        return None
    top = getattr(alert, "code", None)
    if top is None and isinstance(alert, dict):
        top = alert.get("code")
    labels = _labels_dict(alert)
    label_code = labels.get(RESERVED_ALERT_CODE_LABEL)
    raw = top or label_code
    code = slugify_alert_code(raw if isinstance(raw, str) else None)
    return code or None


def normalize_alert_code(alert: Any) -> str | None:
    """Mirror code onto both `alert.code` and `alert.labels.code`.

    Returns the normalized code, or None if the alert has no code.
    Does not invent a code from name/description.
    """
    if alert is None:
        return None
    code = get_alert_code(alert)
    labels = _labels_dict(alert)
    if labels is None:
        labels = {}
    if code:
        if hasattr(alert, "code"):
            alert.code = code
        elif isinstance(alert, dict):
            alert["code"] = code
        labels[RESERVED_ALERT_CODE_LABEL] = code
    if hasattr(alert, "labels"):
        alert.labels = labels
    elif isinstance(alert, dict):
        alert["labels"] = labels
    return code


def collect_codes(alerts: Iterable[Any]) -> list[str]:
    """Unique reserved codes from a sequence of alerts, stable order."""
    seen: list[str] = []
    for alert in alerts or []:
        code = get_alert_code(alert)
        if code and code not in seen:
            seen.append(code)
    return seen


def merge_incident_codes(
    existing_codes: Iterable[str] | None,
    new_codes: Iterable[str] | None,
    existing_primary: str | None = None,
) -> tuple[str | None, list[str]]:
    """Union codes onto an incident. Primary is the sole code, else kept if still present."""
    merged: list[str] = []
    for value in list(existing_codes or []) + list(new_codes or []):
        code = slugify_alert_code(value if isinstance(value, str) else None)
        if code and code not in merged:
            merged.append(code)
    primary = slugify_alert_code(existing_primary) or None
    if len(merged) == 1:
        primary = merged[0]
    elif primary and primary not in merged:
        primary = merged[0] if merged else None
    elif not primary and merged:
        primary = merged[0]
    return primary, merged
