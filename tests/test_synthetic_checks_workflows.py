"""Unit tests for synthetic-check activities (no Temporal worker required)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

WORKER_ROOT = Path(__file__).resolve().parents[1] / "backend" / "services" / "synthetic-checks"
sys.path.insert(0, str(WORKER_ROOT))

from app.activities import notify_keep_alert, probe_target  # noqa: E402


def test_probe_target_http_activity():
    mock_probe = MagicMock(
        return_value={
            "success": True,
            "duration_seconds": 0.1,
            "prober": "http",
            "target": "https://example.com",
            "error": None,
            "status_code": 200,
        }
    )
    with patch.dict("app.activities.PROBERS", {"http": mock_probe}):
        with patch("app.activities.record_probe_metrics") as mock_metrics:
            result = probe_target(
                {
                    "target": "https://example.com",
                    "prober": "http",
                    "module_config": {},
                    "check_key": "demo",
                    "labels": {"env": "test"},
                }
            )

    assert result["success"] is True
    assert result["check_key"] == "demo"
    mock_probe.assert_called_once()
    mock_metrics.assert_called_once()


def test_notify_keep_alert_posts_firing():
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.raise_for_status = MagicMock()

    with patch.dict(
        "os.environ",
        {"KEEP_API_URL": "http://keep:8080", "KEEP_API_KEY": "key"},
        clear=False,
    ):
        with patch("app.activities.httpx.post", return_value=mock_response) as post:
            out = notify_keep_alert(
                {
                    "check_key": "demo",
                    "check_name": "Demo",
                    "result": {
                        "success": False,
                        "prober": "http",
                        "target": "https://example.com",
                        "duration_seconds": 1.2,
                        "error": "timeout",
                    },
                    "labels": {"code": "SYNTH_NVIDIA_INFERENCE_GATEWAY", "service": "gpu-inference"},
                }
            )

    assert out["posted"] is True
    assert out["alert_status"] == "firing"
    assert out["fingerprint"] == "synth:demo:http:https://example.com"
    args, kwargs = post.call_args
    assert args[0] == "http://keep:8080/alerts/event"
    assert kwargs["json"]["status"] == "firing"
    assert kwargs["json"]["source"] == ["synthetic-checks"]
    assert kwargs["json"]["code"] == "SYNTH_NVIDIA_INFERENCE_GATEWAY"
    assert kwargs["json"]["labels"]["code"] == "SYNTH_NVIDIA_INFERENCE_GATEWAY"


def test_notify_keep_alert_skips_without_config():
    with patch.dict("os.environ", {"KEEP_API_URL": "", "KEEP_API_KEY": ""}, clear=False):
        out = notify_keep_alert(
            {
                "result": {
                    "success": True,
                    "prober": "tcp",
                    "target": "example.com:443",
                }
            }
        )
    assert out.get("skipped") is True
