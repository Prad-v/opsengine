"""Unit tests for synthetic check probers (no Temporal required)."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import dns.resolver
import httpx
import pytest

# Import probers from the worker package on PYTHONPATH-style layout.
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1] / "backend" / "services" / "synthetic-checks"
sys.path.insert(0, str(WORKER_ROOT))

from app.probers.dns import probe_dns  # noqa: E402
from app.probers.http import probe_http  # noqa: E402
from app.probers.tcp import probe_tcp  # noqa: E402


def test_probe_http_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = mock_response

    with patch("app.probers.http.httpx.Client", return_value=mock_client):
        result = probe_http(
            "https://example.com/health",
            {"valid_status_codes": [200], "timeout_seconds": 2},
        )

    assert result["success"] is True
    assert result["prober"] == "http"
    assert result["status_code"] == 200
    assert result["duration_seconds"] >= 0


def test_probe_http_bad_status():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "error"
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.return_value = mock_response

    with patch("app.probers.http.httpx.Client", return_value=mock_client):
        result = probe_http("https://example.com/health", {"valid_status_codes": [200]})

    assert result["success"] is False
    assert "500" in (result["error"] or "")


def test_probe_http_timeout():
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.request.side_effect = httpx.TimeoutException("timeout")

    with patch("app.probers.http.httpx.Client", return_value=mock_client):
        result = probe_http("https://example.com/health", {})

    assert result["success"] is False
    assert result["error"]


def test_probe_tcp_success():
    mock_sock = MagicMock()
    mock_sock.__enter__.return_value = mock_sock
    with patch("app.probers.tcp.socket.create_connection", return_value=mock_sock):
        result = probe_tcp("example.com:443", {"timeout_seconds": 1})

    assert result["success"] is True
    assert result["prober"] == "tcp"
    assert result["port"] == 443


def test_probe_tcp_failure():
    with patch(
        "app.probers.tcp.socket.create_connection",
        side_effect=socket.timeout("timed out"),
    ):
        result = probe_tcp("example.com:443", {})

    assert result["success"] is False
    assert result["error"]


def test_probe_dns_success():
    rdata = MagicMock()
    rdata.to_text.return_value = "1.2.3.4"
    answer = [rdata]
    with patch("app.probers.dns.dns.resolver.Resolver") as resolver_cls:
        resolver = resolver_cls.return_value
        resolver.resolve.return_value = answer
        result = probe_dns("example.com", {"query_type": "A"})

    assert result["success"] is True
    assert result["records"] == ["1.2.3.4"]


def test_probe_dns_nxdomain():
    with patch("app.probers.dns.dns.resolver.Resolver") as resolver_cls:
        resolver = resolver_cls.return_value
        resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
        result = probe_dns("missing.example", {"query_type": "A"})

    assert result["success"] is False
    assert result["error"]
