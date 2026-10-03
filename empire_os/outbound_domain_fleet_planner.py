"""Capacity and resilience planning for Empire-owned outbound domain fleets.

The planner allocates only already-approved, brand-safe, sovereign, healthy sender
identities. It never creates domains, changes DNS, expands safety caps, or authorizes
sending. Capacity gaps are reported explicitly rather than bypassed with rotation.
"""
from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any, Iterable, Mapping


def estimate_fleet_requirement(
    *,
    approved_daily_volume: int,
    per_mailbox_cap: int,
    max_mailboxes_per_domain: int,
    minimum_domains: int = 2,
) -> dict[str, Any]:
    volume = max(0, int(approved_daily_volume))
    mailbox_cap = max(1, int(per_mailbox_cap))
    mailbox_per_domain = max(1, int(max_mailboxes_per_domain))
    min_domains = max(1, int(minimum_domains))

    mailboxes_needed = ceil(volume / mailbox_cap) if volume else 0
    domains_for_mailboxes = (
        ceil(mailboxes_needed / mailbox_per_domain)
        if mailboxes_needed
        else 0
    )
    domains_needed = (
        max(min_domains, domains_for_mailboxes)
        if volume
        else 0
    )

    return {
        "approved_daily_volume": volume,
        "per_mailbox_cap": mailbox_cap,
        "max_mailboxes_per_domain": mailbox_per_domain,
        "mailboxes_needed": mailboxes_needed,
        "domains_needed": domains_needed,
        "calculation_only": True,
        "provisioning_authorized": False,
        "send_authorized": False,
    }


def plan_existing_fleet_capacity(
    domains: Iterable[Mapping[str, Any]],
    mailboxes: Iterable[Mapping[str, Any]],
    *,
    approved_daily_volume: int,
    max_domain_share: float = 0.50,
) -> dict[str, Any]:
    target = max(0, int(approved_daily_volume))
    share = float(max_domain_share)
    if not 0 < share <= 1:
        raise ValueError("max_domain_share_must_be_between_zero_and_one")

    domain_rows = [dict(row) for row in domains]
    mailbox_rows = [dict(row) for row in mailboxes]

    eligible_domains = {
        str(row.get("domain") or "").strip(): row
        for row in domain_rows
        if str(row.get("domain") or "").strip()
        and row.get("empire_owned") is True
        and row.get("brand_safe") is True
        and row.get("sovereign") is True
        and str(row.get("health") or "").upper() == "GREEN"
        and str(row.get("purpose") or "").lower() == "prospecting"
        and row.get("primary_brand") is not True
    }

    eligible_mailboxes: list[dict[str, Any]] = []
    rejected_mailboxes: list[dict[str, Any]] = []
    for raw in mailbox_rows:
        row = dict(raw)
        domain = str(row.get("domain") or "").strip()
        remaining = max(0, int(row.get("remaining_capacity") or 0))
        reasons: list[str] = []

        if domain not in eligible_domains:
            reasons.append("domain_not_eligible")
        if str(row.get("health") or "").upper() != "GREEN":
            reasons.append("mailbox_not_green")
        if row.get("enabled") is not True:
            reasons.append("mailbox_not_enabled")
        if remaining <= 0:
            reasons.append("mailbox_capacity_exhausted")

        if reasons:
            rejected_mailboxes.append({
                "mailbox_key": row.get("mailbox_key") or row.get("sender_id"),
                "domain": domain,
                "reasons": reasons,
            })
        else:
            eligible_mailboxes.append({
                **row,
                "remaining_capacity": remaining,
            })

    if target == 0:
        return {
            "posture": "NOOP",
            "target": 0,
            "allocations": [],
            "allocated": 0,
            "capacity_gap": 0,
            "eligible_domains": sorted(eligible_domains),
            "eligible_mailbox_count": len(eligible_mailboxes),
            "rejected_mailboxes": rejected_mailboxes,
            "provisioning_authorized": False,
            "send_authorized": False,
        }

    max_per_domain = max(1, ceil(target * share))
    used_by_domain: dict[str, int] = defaultdict(int)
    allocations: list[dict[str, Any]] = []
    remaining_target = target

    # Prefer higher reputation credit and available capacity while retaining a
    # deterministic tie-break. Domain-share policy still limits concentration.
    eligible_mailboxes.sort(
        key=lambda row: (
            -int(row.get("reputation_credit") or 0),
            -int(row.get("remaining_capacity") or 0),
            str(row.get("mailbox_key") or row.get("sender_id") or ""),
        )
    )

    progress = True
    while remaining_target > 0 and progress:
        progress = False
        for row in eligible_mailboxes:
            if remaining_target <= 0:
                break
            domain = str(row.get("domain") or "")
            domain_room = max_per_domain - used_by_domain[domain]
            mailbox_remaining = int(row.get("remaining_capacity") or 0)
            already = next(
                (
                    item for item in allocations
                    if item["mailbox_key"]
                    == str(row.get("mailbox_key") or row.get("sender_id") or "")
                ),
                None,
            )
            allocated_to_mailbox = int(already["units"]) if already else 0
            mailbox_room = max(0, mailbox_remaining - allocated_to_mailbox)
            units = min(
                remaining_target,
                domain_room,
                mailbox_room,
            )
            if units <= 0:
                continue

            mailbox_key = str(
                row.get("mailbox_key") or row.get("sender_id") or ""
            )
            if already:
                already["units"] += units
            else:
                allocations.append({
                    "mailbox_key": mailbox_key,
                    "domain": domain,
                    "transport_key": row.get("transport_key"),
                    "units": units,
                })
            used_by_domain[domain] += units
            remaining_target -= units
            progress = True

    allocated = target - remaining_target
    posture = "PLANNED" if remaining_target == 0 else "CAPACITY_GAP"

    return {
        "posture": posture,
        "target": target,
        "allocated": allocated,
        "capacity_gap": remaining_target,
        "max_domain_share": share,
        "max_units_per_domain": max_per_domain,
        "allocations": allocations,
        "domain_usage": dict(sorted(used_by_domain.items())),
        "eligible_domains": sorted(eligible_domains),
        "eligible_mailbox_count": len(eligible_mailboxes),
        "rejected_mailboxes": rejected_mailboxes,
        "provisioning_authorized": False,
        "send_authorized": False,
        "principle": "capacity_gap_is_reported_not_bypassed_by_rotation",
    }
