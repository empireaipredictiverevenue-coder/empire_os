"""National Storm Hub scoped Revenue Pulse alert rules.

Pure read-only rules. Reuse canonical EmpireOS Revenue Pulse V3 as an
organisation-wide diagnostic, never as a National Storm Hub tenant ledger.
Emits candidate alerts only; sends nothing and modifies no customer state.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA = "nsh.revenue_pulse_alerts.v1"
TENANT = "national-storm-hub"
VALID_KINDS = frozenset({"contractor_enquiry", "payment_verified", "revenue_recognized"})
FRESH_MINUTES = 20


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def _dedupe_key(kind: str, evidence: str) -> str:
    return "nsh:" + hashlib.sha256(f"{kind}|{evidence}".encode()).hexdigest()[:22]


def _verified_event(row: Mapping[str, Any], now: datetime) -> dict[str, Any] | None:
    """Fail closed on tenant scope, trusted source, time, consent and receipts."""
    event_id = row.get("event_id")
    kind = row.get("kind")
    occurred = _time(row.get("occurred_at"))
    if (
        row.get("tenant_id") != TENANT
        or kind not in VALID_KINDS
        or not isinstance(event_id, str) or not event_id.strip()
        or not isinstance(row.get("evidence_ref"), str) or not row["evidence_ref"].strip()
        or row.get("source") != "canonical_empiredb_postgres"
        or row.get("verified") is not True
        or occurred is None or occurred > now
        or now - occurred > __import__("datetime").timedelta(days=31)
    ):
        return None

    if kind == "contractor_enquiry":
        if (row.get("purpose_consent") != "contractor_connection"
            or row.get("consent_verified") is not True
            or row.get("homeowner_initiated") is not True):
            return None
        label = "Verified, consented homeowner service enquiry"
        severity = "high"
    elif kind == "payment_verified":
        amount = row.get("amount_minor")
        if (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0
            or row.get("currency") not in ("USD", "GBP", "USDT")
            or not isinstance(row.get("settlement_ref"), str)
            or not row["settlement_ref"].strip()):
            return None
        label = "Verified National Storm Hub payment receipt"
        severity = "high"
    else:
        amount = row.get("amount_minor")
        if (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0
            or row.get("currency") not in ("USD", "GBP", "USDT")
            or not isinstance(row.get("accounting_ref"), str)
            or not row["accounting_ref"].strip()):
            return None
        label = "Recognized National Storm Hub revenue"
        severity = "high"

    return {
        "key": _dedupe_key(kind, row["evidence_ref"]),
        "kind": kind,
        "severity": severity,
        "title": label,
        "evidence_ref": row["evidence_ref"],
        "occurred_at": occurred.isoformat(),
        "tenant_id": TENANT,
        "action": "founder_review",
        "send_authority": "none",
    }


def review_nsh_revenue_alerts(
    *,
    now: datetime,
    site_probe: Mapping[str, Any] | None,
    current_revenue_pulse: Mapping[str, Any] | None,
    tenant_events: list[dict[str, Any]] | None = None,
    previously_seen_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Candidate alert report; unknown stays unknown until scoped evidence arrives."""
    if now.utcoffset() is None:
        raise ValueError("now must have timezone")
    now = now.astimezone(timezone.utc)
    seen = previously_seen_keys or set()
    alerts = []
    health_state = "NOT_CHECKED"
    if site_probe is not None:
        home = site_probe.get("homepage_http")
        api = site_probe.get("weather_api_http")
        health_state = "AVAILABLE" if home == 200 and api == 200 else "DEGRADED"
        if home != 200:
            alerts.append({
                "key": _dedupe_key("site_unavailable", "nationalstormhub.com"),
                "kind": "site_unavailable", "severity": "critical",
                "title": "National Storm Hub homepage availability needs checking",
                "evidence_ref": "probe:https://nationalstormhub.com/",
                "action": "founder_review", "send_authority": "none",
            })
        if api != 200:
            alerts.append({
                "key": _dedupe_key("weather_feed_unavailable", "nsh_api_alerts"),
                "kind": "weather_feed_unavailable", "severity": "warn",
                "title": "National Storm Hub public weather feed needs checking",
                "evidence_ref": "probe:https://nationalstormhub.com/api/alerts?state=TX",
                "action": "founder_review", "send_authority": "none",
            })
    pulse_status = "NOT_CONNECTED"
    if current_revenue_pulse is not None:
        generated = _time(current_revenue_pulse.get("generated_at"))
        if current_revenue_pulse.get("schema_version") == "empire.revenue-pulse.v3" and generated:
            age = (now - generated).total_seconds()
            pulse_status = "FRESH_ORGANISATION_WIDE" if 0 <= age <= FRESH_MINUTES * 60 else "STALE_OR_FUTURE"
            if pulse_status != "FRESH_ORGANISATION_WIDE":
                alerts.append({
                    "key": _dedupe_key("pulse_stale", "empire_v3"),
                    "kind": "pulse_stale", "severity": "warn",
                    "title": "EmpireOS canonical Revenue Pulse snapshot is stale",
                    "evidence_ref": "runtime/revenue_pulse/latest.json",
                    "action": "founder_review", "send_authority": "none",
                })
        else:
            pulse_status = "INVALID_CANONICAL_SNAPSHOT"
    events_state = "UNCONNECTED"
    valid = {}
    rejected = 0
    if tenant_events is not None:
        events_state = "SCOPED_EVIDENCE_RECEIVED"
        for row in tenant_events:
            e = _verified_event(row, now) if isinstance(row, Mapping) else None
            if not e:
                rejected += 1
                continue
            identity = e["key"]
            if identity in valid and valid[identity] != e:
                valid.pop(identity, None)
                rejected += 1
            elif identity not in valid:
                valid[identity] = e
    alerts.extend(valid.values())
    candidates = sorted(alerts, key=lambda a:(a["kind"], a["key"]))
    return {
        "schema_version": SCHEMA,
        "site": "nationalstormhub.com",
        "tenant_id": TENANT,
        "checked_at": now.isoformat(),
        "mode": "OBSERVE",
        "site_state": health_state,
        "empire_pulse_state": pulse_status,
        "empire_pulse_scope": "ORGANISATION_WIDE_NOT_NSH",
        "nsh_commercial_events_state": events_state,
        "nsh_verified_commercial_event_count": len(valid) if tenant_events is not None else None,
        "nsh_enquiries": sum(a["kind"] == "contractor_enquiry" for a in valid.values()) if tenant_events is not None else None,
        "nsh_payments_verified": sum(a["kind"] == "payment_verified" for a in valid.values()) if tenant_events is not None else None,
        "nsh_recognized_revenue": None,
        "web_traffic": None,
        "registration_count": None,
        "rejected_unverified_events": rejected,
        "alerts": candidates,
        "new_alerts": [a for a in candidates if a["key"] not in seen],
        "notification_sent": False,
        "customer_contact_authorized": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }
