"""Restricted local health probes for outbound telemetry sources.

Only loopback HTTP endpoints are allowed. This prevents telemetry configuration from
becoming a generic network request or SSRF surface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
from typing import Any
from urllib.parse import urlparse

import requests


def _loopback_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise ValueError("telemetry_probe_requires_http_loopback")
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("telemetry_probe_host_required")

    if host == "localhost":
        return url

    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("telemetry_probe_must_use_loopback_host") from exc

    if not address.is_loopback:
        raise ValueError("telemetry_probe_must_use_loopback_host")
    return url


def probe_loopback_health(
    source: str,
    url: str,
    *,
    now: datetime | None = None,
    timeout_s: float = 2.0,
    request_get=None,
) -> dict[str, Any]:
    source_key = str(source or "").strip()
    if not source_key:
        raise ValueError("telemetry_probe_source_required")
    safe_url = _loopback_url(url)
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    getter = request_get or requests.get

    try:
        response = getter(
            safe_url,
            timeout=max(0.2, min(float(timeout_s), 5.0)),
            headers={"Accept": "application/json"},
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        payload = response.json() if status_code == 200 else {}
        if not isinstance(payload, dict):
            payload = {}
    except Exception as exc:
        return {
            "source": source_key,
            "observed_at": timestamp.isoformat(),
            "success": False,
            "coverage": False,
            "details": {
                "probe": "loopback_http",
                "error": type(exc).__name__,
            },
        }

    ready = payload.get("ready")
    if ready is None:
        ready = payload.get("ok") is True

    return {
        "source": source_key,
        "observed_at": timestamp.isoformat(),
        "success": status_code == 200 and payload.get("ok") is True,
        "coverage": bool(ready),
        "details": {
            "probe": "loopback_http",
            "status_code": status_code,
            "provider": payload.get("provider"),
            "mode": payload.get("mode"),
            "ingest_transport": payload.get("ingest_transport"),
            "signature_verification_configured": payload.get(
                "signature_verification_configured"
            ),
            "reply_receiving_ready": payload.get("reply_receiving_ready"),
        },
    }
