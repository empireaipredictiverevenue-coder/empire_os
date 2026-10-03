"""Materialize a bounded sender estate from canonical inventory and capacity evidence."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from empire_os.outbound_capacity_accounting import replay_capacity_events


def build_sender_estate(
    mailboxes: Iterable[Mapping[str, Any]],
    capacity_events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    events_by_mailbox: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in capacity_events:
        row = dict(raw)
        key = str(row.get("mailbox_key") or "").strip()
        if key:
            events_by_mailbox[key].append(row)

    senders: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for raw in mailboxes:
        row = dict(raw)
        mailbox_key = str(row.get("mailbox_key") or "").strip()
        if not mailbox_key:
            continue

        capacity = replay_capacity_events(
            events_by_mailbox.get(mailbox_key, [])
        )

        reasons: list[str] = []
        if str(row.get("mailbox_state") or row.get("state") or "").upper() != "ACTIVE":
            reasons.append("mailbox_not_active")
        if str(row.get("domain_state") or "").upper() != "ACTIVE":
            reasons.append("domain_not_active")
        if row.get("transport_key") and str(row.get("transport_state") or "").upper() != "ACTIVE":
            reasons.append("transport_not_active")
        if row.get("transport_key") and row.get("transport_policy_compatible") is not True:
            reasons.append("transport_policy_not_compatible")
        if capacity["state"] != "READY":
            reasons.append("capacity_not_ready")
        if capacity["remaining"] <= 0:
            reasons.append("capacity_exhausted")

        record = {
            "sender_id": mailbox_key,
            "mailbox_key": mailbox_key,
            "email_address": row.get("email_address"),
            "domain": row.get("domain"),
            "transport_key": row.get("transport_key"),
            "health": "GREEN" if not reasons else "HOLD",
            "enabled": not reasons,
            "remaining_capacity": capacity["remaining"],
            "reputation_credit": int(row.get("reputation_credit") or 0),
            "capacity": capacity,
            "blockers": reasons,
        }

        if reasons:
            blocked.append(record)
        else:
            senders.append(record)

    senders.sort(
        key=lambda item: (
            -int(item["reputation_credit"]),
            -int(item["remaining_capacity"]),
            str(item["sender_id"]),
        )
    )

    return {
        "eligible_senders": senders,
        "blocked_senders": blocked,
        "eligible_count": len(senders),
        "blocked_count": len(blocked),
        "send_authorized": False,
    }
