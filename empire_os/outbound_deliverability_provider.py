"""Provider adapters for outbound deliverability telemetry.

Empire owns the health model. External providers are evidence sources only.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import requests

DEFAULT_OUTBOUND_ENV = Path("/srv/empire_os/runtime/secrets/outbound.env")


class DeliverabilityMetricsProvider(Protocol):
    def metrics(
        self,
        *,
        start: datetime,
        end: datetime,
        granularity: str = "daily",
    ) -> dict[str, Any]:
        ...


def _read_env_key(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


class ResendMetricsProvider:
    """Read-only adapter for Resend's metrics API."""

    METRICS = (
        "sent",
        "delivered",
        "bounced",
        "bounced_transient",
        "bounced_permanent",
        "bounced_undetermined",
        "complained",
        "suppressed",
        "failed",
        "delivery_delayed",
    )

    def __init__(
        self,
        api_key: str | None = None,
        *,
        secret_env_path: Path = DEFAULT_OUTBOUND_ENV,
        timeout_s: float = 10.0,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("RESEND_API_KEY", "").strip()
            or _read_env_key(secret_env_path, "RESEND_API_KEY")
        )
        self.timeout_s = timeout_s

    def metrics(
        self,
        *,
        start: datetime,
        end: datetime,
        granularity: str = "daily",
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("resend_api_key_missing")
        response = requests.get(
            "https://api.resend.com/emails/metrics",
            params={
                "start_date": start.astimezone(timezone.utc).isoformat(),
                "end_date": end.astimezone(timezone.utc).isoformat(),
                "granularity": granularity,
                "metrics": ",".join(self.METRICS),
                "dimensions": "period,domain",
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("resend_metrics_invalid_payload")
        return payload


def rolling_windows(
    provider: DeliverabilityMetricsProvider,
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    result: dict[str, dict[str, Any]] = {}
    for label, days in (("1d", 1), ("7d", 7), ("30d", 30)):
        result[label] = provider.metrics(
            start=now - timedelta(days=days),
            end=now,
            granularity="daily",
        )
    return result
