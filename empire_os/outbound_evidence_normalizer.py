"""Normalize heterogeneous deliverability evidence into Empire canonical observations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            dt = datetime.now(timezone.utc)
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def normalize_evidence(
    source: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source = str(source or "").strip().lower()
    row = dict(payload)
    observed_at = _iso(row.get("observed_at"))
    domain = row.get("domain")
    mailbox_key = row.get("mailbox_key")
    transport_key = row.get("transport_key")
    recipient_mx = row.get("recipient_mx")

    metrics: dict[str, Any] = {}

    if source == "resend":
        for key in (
            "sent","delivered","bounced","bounced_permanent",
            "bounced_transient","complained","suppressed",
            "failed","delivery_delayed",
        ):
            if key in row:
                metrics[key] = row[key]

    elif source == "gmail_postmaster":
        mapping = {
            "spam_rate": "gmail_spam_rate",
            "spf_success_rate": "spf_success_rate",
            "dkim_success_rate": "dkim_success_rate",
            "dmarc_success_rate": "dmarc_success_rate",
            "delivery_error_rate": "gmail_delivery_error_rate",
        }
        for key, metric in mapping.items():
            if key in row:
                metrics[metric] = row[key]

    elif source == "dmarc":
        for key in (
            "messages","spf_aligned","dkim_aligned",
            "dmarc_passed","dmarc_failed",
        ):
            if key in row:
                metrics[key] = row[key]

    elif source == "seed_placement":
        for key in ("inbox","spam","missing","latency_ms"):
            if key in row:
                metrics[f"placement_{key}"] = row[key]

    elif source == "auth_observer":
        for key in (
            "spf_aligned","dkim_aligned","dmarc_valid",
            "tls_ready","dnssec_valid","mta_sts_valid",
        ):
            if key in row:
                metrics[key] = 1 if row[key] is True else 0

    else:
        raise ValueError("unsupported_deliverability_evidence_source")

    return [
        {
            "source": source,
            "observed_at": observed_at,
            "domain": domain,
            "mailbox_key": mailbox_key,
            "transport_key": transport_key,
            "recipient_mx": recipient_mx,
            "metric_name": metric,
            "metric_value": value,
            "unit": "milliseconds" if metric.endswith("latency_ms") else "count",
            "evidence": row,
        }
        for metric, value in metrics.items()
    ]
