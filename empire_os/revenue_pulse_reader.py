"""Canonical Revenue Pulse reader.

Reads Supabase/PostgREST-style rows through an injected read-only reader.
No writes, revenue recognition, payment confirmation or accounting mutation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from empire_os.revenue_pulse import RevenuePulseWindow


Reader = Callable[[str, dict[str, str]], Any]


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("pulse timestamps require timezone")
    return value.astimezone(timezone.utc).isoformat()


def _rows(
    reader: Reader,
    path: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    value = reader(path, params)
    if not isinstance(value, list):
        raise ValueError(f"invalid canonical rows for {path}")
    return [row for row in value if isinstance(row, dict)]


def _commercial_reply(row: dict[str, Any]) -> bool:
    return str(row.get("classification") or "").strip().lower() in {
        "positive",
        "question",
        "objection",
    }


def _outreach_ready_review(row: dict[str, Any]) -> bool:
    if str(row.get("status") or "").lower() != "approved":
        return False
    evidence = row.get("evidence")
    if not isinstance(evidence, dict):
        return False
    if evidence.get("outreach_ready") is not True:
        return False
    contacts = evidence.get("verified_contacts")
    if not isinstance(contacts, list):
        return False
    return any(
        isinstance(contact, dict)
        and contact.get("bound_to_decision_maker") is True
        and contact.get("is_valid") is True
        and bool(str(contact.get("email") or "").strip())
        for contact in contacts
    )


def fetch_revenue_pulse_window(
    reader: Reader,
    *,
    label: str,
    start: datetime,
    end: datetime,
) -> RevenuePulseWindow:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("pulse window timestamps require timezone")
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if end <= start:
        raise ValueError("pulse window end must be after start")

    start_iso = _iso(start)
    end_iso = _iso(end)
    common_limit = "2000"

    def window_filter(column: str) -> str:
        return f"({column}.gte.{start_iso},{column}.lt.{end_iso})"

    acquisitions = _rows(
        reader,
        "/rest/v1/prospect_acquisitions",
        {
            "select": "id",
            "and": window_filter("created_at"),
            "limit": common_limit,
        },
    )
    qualifications = _rows(
        reader,
        "/rest/v1/prospect_qualifications",
        {
            "select": "id,status",
            "status": "eq.scored",
            "and": window_filter("scored_at"),
            "limit": common_limit,
        },
    )
    reviews = _rows(
        reader,
        "/rest/v1/buyer_candidate_reviews",
        {
            "select": "id,status,evidence",
            "status": "eq.approved",
            "and": window_filter("reviewed_at"),
            "limit": common_limit,
        },
    )
    outbound_events = _rows(
        reader,
        "/rest/v1/outbound_events",
        {
            "select": "id,event_type",
            "event_type": "eq.delivered",
            "and": window_filter("occurred_at"),
            "limit": common_limit,
        },
    )
    replies = _rows(
        reader,
        "/rest/v1/outbound_replies",
        {
            "select": "id,classification",
            "and": window_filter("received_at"),
            "limit": common_limit,
        },
    )
    terms = _rows(
        reader,
        "/rest/v1/commercial_terms_reviews",
        {
            "select": "id,status",
            "and": window_filter("proposed_at"),
            "limit": common_limit,
        },
    )
    payments = _rows(
        reader,
        "/rest/v1/bsc_payment_evidence",
        {
            "select": "id,verified_at",
            "and": window_filter("verified_at"),
            "limit": common_limit,
        },
    )
    fulfilments = _rows(
        reader,
        "/rest/v1/fulfilment_orders",
        {
            "select": "id,delivered_at",
            "and": window_filter("delivered_at"),
            "limit": common_limit,
        },
    )
    revenue_events = _rows(
        reader,
        "/rest/v1/commercial_events",
        {
            "select": "id,amount_cents,margin_cents",
            "event_type": "eq.revenue_recognized",
            "and": window_filter("occurred_at"),
            "limit": common_limit,
        },
    )

    revenue_cents = sum(
        int(row.get("amount_cents") or 0)
        for row in revenue_events
    )
    margin_values = [
        int(row["margin_cents"])
        for row in revenue_events
        if row.get("margin_cents") is not None
    ]

    evidence_refs = (
        f"canonical:prospect_acquisitions:{label}",
        f"canonical:prospect_qualifications:scored:{label}",
        f"canonical:buyer_candidate_reviews:approved_outreach_ready:{label}",
        f"canonical:outbound_events:delivered:{label}",
        f"canonical:outbound_replies:commercial:{label}",
        f"canonical:commercial_terms_reviews:{label}",
        f"canonical:bsc_payment_evidence:{label}",
        f"canonical:fulfilment_orders:delivered:{label}",
        f"canonical:commercial_events:revenue_recognized:{label}",
    )
    return RevenuePulseWindow(
        label=label,
        hours=max(1, round((end - start).total_seconds() / 3600)),
        acquisitions=len(acquisitions),
        qualified=len(qualifications),
        buyer_reviews=sum(
            1 for row in reviews if _outreach_ready_review(row)
        ),
        delivered_outreach=len(outbound_events),
        commercial_replies=sum(
            1 for row in replies if _commercial_reply(row)
        ),
        commercial_terms=len(terms),
        verified_payments=len(payments),
        fulfilments=len(fulfilments),
        recognized_revenue_cents=revenue_cents,
        realized_gp_cents=(
            sum(margin_values)
            if margin_values
            else 0
        ),
        evidence_refs=evidence_refs,
    )


def fetch_current_and_previous_windows(
    reader: Reader,
    *,
    now: datetime,
    hours: int = 24,
) -> tuple[RevenuePulseWindow, RevenuePulseWindow]:
    if hours < 1:
        raise ValueError("pulse window hours must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    end = now.astimezone(timezone.utc)
    current_start = end - timedelta(hours=hours)
    previous_start = current_start - timedelta(hours=hours)
    current = fetch_revenue_pulse_window(
        reader,
        label=f"current_{hours}h",
        start=current_start,
        end=end,
    )
    previous = fetch_revenue_pulse_window(
        reader,
        label=f"previous_{hours}h",
        start=previous_start,
        end=current_start,
    )
    return current, previous
