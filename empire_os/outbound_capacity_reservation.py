"""Append-only outbound capacity reservation and crash-recovery logic.

Reservations are logical leases over mailbox capacity. The functions in this module are
deterministic planners/replayers only: they do not write EmpireDB or authorize sending.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def plan_capacity_reservation(
    *,
    mailbox_key: str,
    domain: str,
    transport_key: str | None,
    units: int,
    remaining_capacity: int,
    reservation_key: str,
    idempotency_key: str,
    now: datetime,
    ttl_seconds: int = 900,
) -> dict[str, Any]:
    mailbox = str(mailbox_key or "").strip()
    reservation = str(reservation_key or "").strip()
    idempotency = str(idempotency_key or "").strip()
    requested = int(units)
    remaining = int(remaining_capacity)

    blockers: list[str] = []
    if not mailbox:
        blockers.append("mailbox_key_missing")
    if not reservation:
        blockers.append("reservation_key_missing")
    if not idempotency:
        blockers.append("idempotency_key_missing")
    if requested <= 0:
        blockers.append("reservation_units_must_be_positive")
    if requested > remaining:
        blockers.append("insufficient_remaining_capacity")

    if blockers:
        return {
            "status": "HOLD",
            "blockers": blockers,
            "event": None,
            "mutation_authorized": False,
        }

    ttl = max(60, min(int(ttl_seconds), 3600))
    timestamp = now.astimezone(timezone.utc)
    return {
        "status": "READY_TO_RESERVE",
        "blockers": [],
        "event": {
            "mailbox_key": mailbox,
            "domain": str(domain or ""),
            "transport_key": (
                str(transport_key).strip()
                if transport_key is not None
                else None
            ),
            "event_type": "RESERVE",
            "units": requested,
            "capacity_limit": None,
            "reservation_key": reservation,
            "idempotency_key": idempotency,
            "lease_expires_at": (
                timestamp + timedelta(seconds=ttl)
            ).isoformat(),
            "reason": "bounded_sender_capacity_reservation",
            "recorded_at": timestamp.isoformat(),
        },
        "mutation_authorized": False,
    }


def replay_capacity_reservations(
    events: Iterable[Mapping[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    timestamp = now.astimezone(timezone.utc)
    ordered = sorted(
        (dict(row) for row in events),
        key=lambda row: (
            str(row.get("recorded_at") or ""),
            str(row.get("id") or ""),
        ),
    )

    seen_idempotency: set[str] = set()
    states: dict[str, dict[str, Any]] = {}
    anomalies: list[str] = []

    for row in ordered:
        event_type = str(row.get("event_type") or "").upper()
        if event_type not in {"RESERVE", "CONSUME", "RELEASE"}:
            continue

        reservation_key = str(row.get("reservation_key") or "").strip()
        idempotency_key = str(row.get("idempotency_key") or "").strip()
        units = max(0, int(row.get("units") or 0))

        if not reservation_key:
            anomalies.append("reservation_event_missing_reservation_key")
            continue
        if not idempotency_key:
            anomalies.append("reservation_event_missing_idempotency_key")
            continue
        if idempotency_key in seen_idempotency:
            # Exact retry is ignored during replay; uniqueness should also be
            # enforced in EmpireDB once migration 036 is activated.
            continue
        seen_idempotency.add(idempotency_key)

        state = states.setdefault(
            reservation_key,
            {
                "reservation_key": reservation_key,
                "mailbox_key": row.get("mailbox_key"),
                "reserved": 0,
                "consumed": 0,
                "released": 0,
                "lease_expires_at": None,
                "terminal": False,
            },
        )

        if (
            state.get("mailbox_key")
            and row.get("mailbox_key")
            and row.get("mailbox_key") != state.get("mailbox_key")
        ):
            anomalies.append("reservation_mailbox_identity_changed")

        if event_type == "RESERVE":
            if state["reserved"] > 0:
                anomalies.append("reservation_key_reused")
                continue
            if units <= 0:
                anomalies.append("reserve_units_must_be_positive")
                continue
            expires = _parse_ts(row.get("lease_expires_at"))
            if expires is None:
                anomalies.append("reservation_lease_expiry_missing_or_invalid")
                continue
            state["reserved"] = units
            state["lease_expires_at"] = expires.isoformat()

        elif event_type == "CONSUME":
            if state["reserved"] <= 0:
                anomalies.append("consume_without_reservation")
                continue
            if state["terminal"]:
                anomalies.append("consume_after_terminal_event")
                continue
            available = state["reserved"] - state["consumed"] - state["released"]
            if units > available:
                anomalies.append("consume_exceeds_reserved_units")
                continue
            state["consumed"] += units
            if state["consumed"] + state["released"] == state["reserved"]:
                state["terminal"] = True

        elif event_type == "RELEASE":
            if state["reserved"] <= 0:
                anomalies.append("release_without_reservation")
                continue
            if state["terminal"]:
                anomalies.append("release_after_terminal_event")
                continue
            available = state["reserved"] - state["consumed"] - state["released"]
            if units > available:
                anomalies.append("release_exceeds_reserved_units")
                continue
            state["released"] += units
            if state["consumed"] + state["released"] == state["reserved"]:
                state["terminal"] = True

    recovery_actions: list[dict[str, Any]] = []
    active_reserved = 0
    expired_reserved = 0

    for reservation_key, state in sorted(states.items()):
        remaining = max(
            0,
            int(state["reserved"])
            - int(state["consumed"])
            - int(state["released"]),
        )
        expires = _parse_ts(state.get("lease_expires_at"))
        expired = (
            remaining > 0
            and expires is not None
            and expires <= timestamp
        )

        state["remaining_reserved"] = remaining
        state["expired"] = expired

        if remaining > 0 and not expired:
            active_reserved += remaining
        elif expired:
            expired_reserved += remaining
            recovery_actions.append({
                "action": "APPEND_RELEASE",
                "reservation_key": reservation_key,
                "mailbox_key": state.get("mailbox_key"),
                "units": remaining,
                "reason": "expired_capacity_lease_recovery",
                "mutation_authorized": False,
            })

    unique_anomalies = list(dict.fromkeys(anomalies))
    status = "HOLD" if unique_anomalies else (
        "RECOVERY_REQUIRED" if recovery_actions else "CONVERGED"
    )

    return {
        "status": status,
        "reservations": states,
        "active_reserved_units": active_reserved,
        "expired_reserved_units": expired_reserved,
        "recovery_actions": recovery_actions,
        "anomalies": unique_anomalies,
        "mutation_authorized": False,
        "send_authorized": False,
    }
