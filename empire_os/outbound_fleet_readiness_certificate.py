"""Unified fleet readiness certificate for Empire outbound.

Combines safe capacity and resilience evidence into a single audit-friendly read model.
A READY certificate is evidence that the estate can support the supplied approved volume
under the configured constraints; it is never itself send or provisioning authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from empire_os.outbound_fleet_capacity_certificate import (
    build_fleet_capacity_certificate,
)
from empire_os.outbound_fleet_resilience import evaluate_fleet_resilience


def build_fleet_readiness_certificate(
    *,
    approved_daily_volume: int,
    per_mailbox_cap: int,
    max_mailboxes_per_domain: int,
    domains: Iterable[Mapping[str, Any]],
    mailboxes: Iterable[Mapping[str, Any]],
    estate_reconciliation: Mapping[str, Any] | None = None,
    verified_seed_families: Iterable[str] = (),
    failover_benchmark: Mapping[str, Any] | None = None,
    max_domain_share: float = 0.50,
    minimum_domains: int = 2,
) -> dict[str, Any]:
    domain_rows = [dict(row) for row in domains]
    mailbox_rows = [dict(row) for row in mailboxes]

    capacity = build_fleet_capacity_certificate(
        approved_daily_volume=approved_daily_volume,
        per_mailbox_cap=per_mailbox_cap,
        max_mailboxes_per_domain=max_mailboxes_per_domain,
        domains=domain_rows,
        mailboxes=mailbox_rows,
        estate_reconciliation=estate_reconciliation,
        max_domain_share=max_domain_share,
        minimum_domains=minimum_domains,
    )
    resilience = evaluate_fleet_resilience(
        mailbox_rows,
        estate_reconciliation=estate_reconciliation,
        verified_seed_families=verified_seed_families,
        failover_benchmark=failover_benchmark,
    )

    blockers: list[str] = []
    warnings: list[str] = []

    if capacity["status"] == "HOLD":
        blockers.extend(capacity["blockers"])
    elif capacity["status"] == "LIMITED":
        warnings.extend(capacity["warnings"])

    if resilience["posture"] == "HOLD":
        blockers.extend(resilience["blockers"])
    elif resilience["posture"] in {"LIMITED", "FRAGILE"}:
        warnings.extend(resilience["warnings"])

    if blockers:
        status = "HOLD"
    elif warnings:
        status = "LIMITED"
    else:
        status = "READY"

    material = {
        "status": status,
        "approved_daily_volume": int(approved_daily_volume),
        "capacity": capacity,
        "resilience": resilience,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    return {
        **material,
        "certificate_fingerprint": fingerprint,
        "mutation_authorized": False,
        "provisioning_authorized": False,
        "send_authorized": False,
    }
