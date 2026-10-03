"""Founder/Ringleader fleet capacity certificate.

Combines demand, current safe fleet capacity, estate convergence and concentration risk
into one read-only scaling certificate. It never provisions domains/mailboxes and never
authorizes sends.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from empire_os.outbound_domain_fleet_planner import (
    estimate_fleet_requirement,
    plan_existing_fleet_capacity,
)
from empire_os.outbound_infrastructure_concentration import (
    evaluate_concentration,
)


def build_fleet_capacity_certificate(
    *,
    approved_daily_volume: int,
    per_mailbox_cap: int,
    max_mailboxes_per_domain: int,
    domains: Iterable[Mapping[str, Any]],
    mailboxes: Iterable[Mapping[str, Any]],
    estate_reconciliation: Mapping[str, Any] | None = None,
    max_domain_share: float = 0.50,
    minimum_domains: int = 2,
) -> dict[str, Any]:
    domain_rows = [dict(row) for row in domains]
    mailbox_rows = [dict(row) for row in mailboxes]
    reconciliation = dict(estate_reconciliation or {})

    requirement = estimate_fleet_requirement(
        approved_daily_volume=approved_daily_volume,
        per_mailbox_cap=per_mailbox_cap,
        max_mailboxes_per_domain=max_mailboxes_per_domain,
        minimum_domains=minimum_domains,
    )
    plan = plan_existing_fleet_capacity(
        domain_rows,
        mailbox_rows,
        approved_daily_volume=approved_daily_volume,
        max_domain_share=max_domain_share,
    )
    concentration = evaluate_concentration(mailbox_rows)

    blockers: list[str] = []
    warnings: list[str] = []

    estate_status = str(reconciliation.get("status") or "UNKNOWN").upper()
    if estate_status == "HOLD":
        blockers.append("sender_estate_not_converged")
    elif estate_status == "DEGRADED":
        warnings.append("sender_estate_degraded")
    elif estate_status == "UNKNOWN":
        warnings.append("sender_estate_reconciliation_unavailable")

    if plan["posture"] == "CAPACITY_GAP":
        blockers.append("safe_sender_capacity_gap")

    if concentration["posture"] == "HIGH_CONCENTRATION":
        warnings.append("sender_infrastructure_concentration_high")
    elif concentration["posture"] == "MODERATE_CONCENTRATION":
        warnings.append("sender_infrastructure_concentration_moderate")

    eligible_domain_count = len(plan["eligible_domains"])
    required_domain_count = int(requirement["domains_needed"])
    if (
        required_domain_count > 0
        and eligible_domain_count < required_domain_count
    ):
        warnings.append("eligible_domain_count_below_requirement")

    if blockers:
        status = "HOLD"
    elif warnings:
        status = "LIMITED"
    else:
        status = "READY"

    certificate_material = {
        "status": status,
        "approved_daily_volume": int(approved_daily_volume),
        "requirement": requirement,
        "plan": plan,
        "concentration": concentration,
        "estate_status": estate_status,
        "blockers": blockers,
        "warnings": warnings,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            certificate_material,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    return {
        **certificate_material,
        "certificate_fingerprint": fingerprint,
        "provisioning_authorized": False,
        "send_authorized": False,
        "mutation_authorized": False,
    }
