"""Deterministic reconciliation for the canonical Empire outbound sender estate.

Rebuilds runtime sender eligibility from EmpireDB-style inventory plus the append-only
capacity ledger. Reconciliation is observational: it reports drift and blockers but never
modifies inventory, capacity, DNS, transports, or send authority.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from empire_os.outbound_sender_estate import build_sender_estate


def reconcile_sender_estate(
    *,
    transports: Iterable[Mapping[str, Any]],
    domains: Iterable[Mapping[str, Any]],
    mailboxes: Iterable[Mapping[str, Any]],
    pools: Iterable[Mapping[str, Any]],
    pool_members: Iterable[Mapping[str, Any]],
    capacity_events: Iterable[Mapping[str, Any]],
    seed_mailboxes: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    transport_rows = [dict(row) for row in transports]
    domain_rows = [dict(row) for row in domains]
    mailbox_rows = [dict(row) for row in mailboxes]
    pool_rows = [dict(row) for row in pools]
    member_rows = [dict(row) for row in pool_members]
    capacity_rows = [dict(row) for row in capacity_events]
    seed_rows = [dict(row) for row in seed_mailboxes]

    transport_by_id = {
        str(row.get("id")): row
        for row in transport_rows
        if row.get("id") is not None
    }
    domain_by_id = {
        str(row.get("id")): row
        for row in domain_rows
        if row.get("id") is not None
    }
    mailbox_by_key = {
        str(row.get("mailbox_key") or "").strip(): row
        for row in mailbox_rows
        if str(row.get("mailbox_key") or "").strip()
    }
    pool_by_id = {
        str(row.get("id")): row
        for row in pool_rows
        if row.get("id") is not None
    }

    hard_holds: list[str] = []
    warnings: list[str] = []
    issues: list[dict[str, Any]] = []

    enriched_mailboxes: list[dict[str, Any]] = []
    for mailbox in mailbox_rows:
        mailbox_key = str(mailbox.get("mailbox_key") or "").strip()
        if not mailbox_key:
            hard_holds.append("mailbox_key_missing")
            issues.append({"kind": "mailbox_key_missing"})
            continue

        domain_id = str(mailbox.get("domain_id") or "")
        domain = domain_by_id.get(domain_id)
        if domain is None:
            hard_holds.append("mailbox_domain_missing")
            issues.append({
                "kind": "mailbox_domain_missing",
                "mailbox_key": mailbox_key,
                "domain_id": domain_id,
            })

        transport_id = str(mailbox.get("transport_id") or "")
        transport = transport_by_id.get(transport_id) if transport_id else None
        if transport_id and transport is None:
            hard_holds.append("mailbox_transport_missing")
            issues.append({
                "kind": "mailbox_transport_missing",
                "mailbox_key": mailbox_key,
                "transport_id": transport_id,
            })

        domain_state = (
            str(domain.get("lifecycle_state") or "").upper()
            if domain is not None
            else "MISSING"
        )
        transport_state = (
            str(transport.get("state") or "").upper()
            if transport is not None
            else ("UNASSIGNED" if not transport_id else "MISSING")
        )
        transport_key = (
            str(transport.get("transport_key") or "")
            if transport is not None
            else None
        )

        enriched_mailboxes.append({
            **mailbox,
            "domain": domain.get("domain") if domain else None,
            "domain_state": domain_state,
            "transport_key": transport_key,
            "transport_state": transport_state,
            "transport_policy_compatible": (
                transport.get("policy_compatible") is True
                if transport is not None
                else False
            ),
            "mailbox_state": mailbox.get("state"),
        })

    known_mailboxes = set(mailbox_by_key)
    for event in capacity_rows:
        mailbox_key = str(event.get("mailbox_key") or "").strip()
        if mailbox_key not in known_mailboxes:
            hard_holds.append("capacity_event_unknown_mailbox")
            issues.append({
                "kind": "capacity_event_unknown_mailbox",
                "mailbox_key": mailbox_key,
                "event_id": event.get("id"),
            })
            continue

        mailbox = mailbox_by_key[mailbox_key]
        domain = domain_by_id.get(str(mailbox.get("domain_id") or ""))
        canonical_domain = str(domain.get("domain") or "") if domain else ""
        event_domain = str(event.get("domain") or "")
        if canonical_domain and event_domain and event_domain != canonical_domain:
            hard_holds.append("capacity_event_domain_mismatch")
            issues.append({
                "kind": "capacity_event_domain_mismatch",
                "mailbox_key": mailbox_key,
                "canonical_domain": canonical_domain,
                "event_domain": event_domain,
            })

        transport = transport_by_id.get(str(mailbox.get("transport_id") or ""))
        canonical_transport = (
            str(transport.get("transport_key") or "")
            if transport is not None
            else ""
        )
        event_transport = str(event.get("transport_key") or "")
        if canonical_transport and event_transport and event_transport != canonical_transport:
            hard_holds.append("capacity_event_transport_mismatch")
            issues.append({
                "kind": "capacity_event_transport_mismatch",
                "mailbox_key": mailbox_key,
                "canonical_transport": canonical_transport,
                "event_transport": event_transport,
            })

    asset_keys: dict[str, set[str]] = {
        "DOMAIN": {
            str(row.get("domain") or "")
            for row in domain_rows
            if str(row.get("domain") or "")
        },
        "MAILBOX": set(known_mailboxes),
        "TRANSPORT": {
            str(row.get("transport_key") or "")
            for row in transport_rows
            if str(row.get("transport_key") or "")
        },
        "SEED": {
            str(row.get("seed_key") or "")
            for row in seed_rows
            if str(row.get("seed_key") or "")
        },
        "RECIPIENT_MX": set(),
    }

    active_members_by_pool: dict[str, int] = defaultdict(int)
    for member in member_rows:
        pool_id = str(member.get("pool_id") or "")
        pool = pool_by_id.get(pool_id)
        if pool is None:
            hard_holds.append("pool_member_orphaned_pool")
            issues.append({
                "kind": "pool_member_orphaned_pool",
                "pool_id": pool_id,
                "member_key": member.get("member_key"),
            })
            continue

        if member.get("active") is not True:
            continue

        active_members_by_pool[pool_id] += 1
        member_type = str(member.get("member_type") or "").upper()
        member_key = str(member.get("member_key") or "").strip()
        if member_type not in asset_keys:
            hard_holds.append("pool_member_unknown_type")
            issues.append({
                "kind": "pool_member_unknown_type",
                "pool_id": pool_id,
                "member_type": member_type,
                "member_key": member_key,
            })
        elif member_type != "RECIPIENT_MX" and member_key not in asset_keys[member_type]:
            hard_holds.append("pool_member_orphaned_asset")
            issues.append({
                "kind": "pool_member_orphaned_asset",
                "pool_id": pool_id,
                "member_type": member_type,
                "member_key": member_key,
            })

    for pool in pool_rows:
        pool_id = str(pool.get("id") or "")
        state = str(pool.get("state") or "").upper()
        if state == "ACTIVE" and active_members_by_pool.get(pool_id, 0) == 0:
            warnings.append("active_pool_has_no_members")
            issues.append({
                "kind": "active_pool_has_no_members",
                "pool_key": pool.get("pool_key"),
            })

    sender_estate = build_sender_estate(
        enriched_mailboxes,
        capacity_rows,
    )

    if mailbox_rows and sender_estate["eligible_count"] == 0:
        warnings.append("no_eligible_senders")

    active_verified_seeds = [
        row for row in seed_rows
        if row.get("active") is True and row.get("ownership_verified") is True
    ]
    if seed_rows and not active_verified_seeds:
        warnings.append("no_active_verified_seed_mailboxes")

    hard_holds = list(dict.fromkeys(hard_holds))
    warnings = list(dict.fromkeys(warnings))

    if hard_holds:
        status = "HOLD"
    elif warnings:
        status = "DEGRADED"
    else:
        status = "CONVERGED"

    return {
        "status": status,
        "hard_holds": hard_holds,
        "warnings": warnings,
        "issues": issues,
        "sender_estate": sender_estate,
        "inventory": {
            "transports": len(transport_rows),
            "domains": len(domain_rows),
            "mailboxes": len(mailbox_rows),
            "pools": len(pool_rows),
            "pool_members": len(member_rows),
            "capacity_events": len(capacity_rows),
            "seed_mailboxes": len(seed_rows),
        },
        "mutation_authorized": False,
        "send_authorized": False,
    }
