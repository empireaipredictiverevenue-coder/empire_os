"""Proposal-only capacity provisioning recommendations for Empire outbound.

Transforms a Fleet Readiness Certificate into explicit missing-capability requests. It
does not choose deceptive domain names, register assets, mutate DNS, provision mailboxes,
or increase live send authority.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def build_fleet_provisioning_proposal(
    certificate: Mapping[str, Any],
    *,
    current_transport_keys: Iterable[str] = (),
    current_ip_pool_keys: Iterable[str] = (),
    verified_seed_families: Iterable[str] = (),
    desired_seed_families: Iterable[str] = (
        "GOOGLE",
        "MICROSOFT",
        "YAHOO",
        "APPLE",
    ),
    minimum_transport_count: int = 2,
    minimum_ip_pool_count: int = 2,
) -> dict[str, Any]:
    cert = dict(certificate or {})
    capacity = dict(cert.get("capacity") or {})
    requirement = dict(capacity.get("requirement") or {})
    plan = dict(capacity.get("plan") or {})

    required_domains = max(0, int(requirement.get("domains_needed") or 0))
    required_mailboxes = max(0, int(requirement.get("mailboxes_needed") or 0))
    eligible_domains = len(plan.get("eligible_domains") or [])
    eligible_mailboxes = max(
        0,
        int(plan.get("eligible_mailbox_count") or 0),
    )
    capacity_gap = max(0, int(plan.get("capacity_gap") or 0))

    transports = sorted({
        str(value or "").strip()
        for value in current_transport_keys
        if str(value or "").strip()
    })
    ip_pools = sorted({
        str(value or "").strip()
        for value in current_ip_pool_keys
        if str(value or "").strip()
    })
    seeds = sorted({
        str(value or "").strip().upper()
        for value in verified_seed_families
        if str(value or "").strip()
    })
    desired_seeds = sorted({
        str(value or "").strip().upper()
        for value in desired_seed_families
        if str(value or "").strip()
    })

    actions: list[dict[str, Any]] = []

    missing_domains = max(0, required_domains - eligible_domains)
    if missing_domains:
        actions.append({
            "action": "PROPOSE_OUTREACH_DOMAINS",
            "count": missing_domains,
            "constraints": [
                "empire_owned",
                "registrar_controlled",
                "brand_safe",
                "not_primary_brand",
                "non_deceptive",
                "prospecting_purpose",
            ],
            "approval_required": True,
        })

    missing_mailboxes = max(0, required_mailboxes - eligible_mailboxes)
    if missing_mailboxes or capacity_gap:
        actions.append({
            "action": "PROPOSE_MAILBOX_CAPACITY",
            "minimum_new_mailboxes": missing_mailboxes,
            "unserved_daily_capacity": capacity_gap,
            "constraints": [
                "verified_identity",
                "stable_sender",
                "bounded_daily_cap",
                "healthy_domain_only",
            ],
            "approval_required": True,
        })

    transport_target = max(1, int(minimum_transport_count))
    if len(transports) < transport_target:
        actions.append({
            "action": "BENCHMARK_ADDITIONAL_TRANSPORT",
            "minimum_additional_transports": transport_target - len(transports),
            "constraints": [
                "provider_policy_compatible",
                "seed_benchmark_before_production",
                "no_automatic_failover",
            ],
            "approval_required": True,
        })

    ip_target = max(1, int(minimum_ip_pool_count))
    if len(ip_pools) < ip_target:
        actions.append({
            "action": "REDUCE_IP_POOL_CONCENTRATION",
            "minimum_additional_ip_pools": ip_target - len(ip_pools),
            "constraints": [
                "stable_reputation",
                "no_ip_churn",
                "transport_supported",
            ],
            "approval_required": True,
        })

    missing_seeds = sorted(set(desired_seeds) - set(seeds))
    if missing_seeds:
        actions.append({
            "action": "ADD_OWNED_SEED_COVERAGE",
            "mx_families": missing_seeds,
            "constraints": [
                "empire_controlled_mailboxes",
                "measurement_only",
                "no_synthetic_engagement",
            ],
            "approval_required": True,
        })

    if not actions:
        posture = "NO_PROVISIONING_GAP"
    elif cert.get("status") == "HOLD":
        posture = "PROPOSAL_REQUIRED"
    else:
        posture = "RESILIENCE_IMPROVEMENT_PROPOSED"

    return {
        "posture": posture,
        "certificate_fingerprint": cert.get("certificate_fingerprint"),
        "required_domains": required_domains,
        "eligible_domains": eligible_domains,
        "required_mailboxes": required_mailboxes,
        "eligible_mailboxes": eligible_mailboxes,
        "capacity_gap": capacity_gap,
        "transport_count": len(transports),
        "ip_pool_count": len(ip_pools),
        "verified_seed_families": seeds,
        "actions": actions,
        "provisioning_authorized": False,
        "dns_mutation_authorized": False,
        "send_authorized": False,
    }
