"""N-1 resilience and blast-radius analysis for Empire outbound fleets.

The model asks a simple production question: if one transport, domain, or IP pool fails,
how much currently eligible capacity survives? It is read-only and never provisions,
moves, or sends anything.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable, Mapping

from empire_os.outbound_infrastructure_concentration import evaluate_concentration


def _eligible_sender(row: Mapping[str, Any]) -> bool:
    return (
        row.get("enabled") is True
        and str(row.get("health") or "").upper() == "GREEN"
        and int(row.get("remaining_capacity") or 0) > 0
    )


def _capacity(rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(
        max(0, int(dict(row).get("remaining_capacity") or 0))
        for row in rows
    )


def _n_minus_one(
    rows: list[dict[str, Any]],
    *,
    field: str,
) -> dict[str, Any]:
    total = _capacity(rows)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(row.get(field) or "unknown")
        groups[key].append(row)

    scenarios: list[dict[str, Any]] = []
    for key in sorted(groups):
        removed_capacity = _capacity(groups[key])
        surviving = max(0, total - removed_capacity)
        survival_rate = surviving / total if total else 0.0
        scenarios.append({
            "failed_asset": key,
            "failed_capacity": removed_capacity,
            "surviving_capacity": surviving,
            "survival_rate": round(survival_rate, 6),
        })

    worst = min(
        (row["survival_rate"] for row in scenarios),
        default=0.0,
    )
    return {
        "dimension": field,
        "asset_count": len(groups),
        "total_capacity": total,
        "worst_case_survival_rate": round(worst, 6),
        "scenarios": scenarios,
    }


def evaluate_fleet_resilience(
    senders: Iterable[Mapping[str, Any]],
    *,
    estate_reconciliation: Mapping[str, Any] | None = None,
    verified_seed_families: Iterable[str] = (),
    failover_benchmark: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    sender_rows = [
        dict(row)
        for row in senders
        if _eligible_sender(row)
    ]
    reconciliation = dict(estate_reconciliation or {})
    seed_families = sorted({
        str(value or "").strip().upper()
        for value in verified_seed_families
        if str(value or "").strip()
    })
    benchmark = dict(failover_benchmark or {})

    total_capacity = _capacity(sender_rows)
    blockers: list[str] = []
    warnings: list[str] = []

    if not sender_rows or total_capacity <= 0:
        blockers.append("no_eligible_sender_capacity")

    estate_status = str(reconciliation.get("status") or "UNKNOWN").upper()
    if estate_status == "HOLD":
        blockers.append("sender_estate_integrity_hold")
    elif estate_status == "DEGRADED":
        warnings.append("sender_estate_degraded")
    elif estate_status == "UNKNOWN":
        warnings.append("sender_estate_reconciliation_unavailable")

    transport = _n_minus_one(sender_rows, field="transport_key")
    domain = _n_minus_one(sender_rows, field="domain")
    ip_pool = _n_minus_one(sender_rows, field="ip_pool_key")

    for result, reason in (
        (transport, "single_transport_blast_radius"),
        (domain, "single_domain_blast_radius"),
        (ip_pool, "single_ip_pool_blast_radius"),
    ):
        if total_capacity and result["worst_case_survival_rate"] < 0.50:
            warnings.append(reason)

    if len(seed_families) < 2:
        warnings.append("seed_provider_coverage_thin")

    benchmark_results = benchmark.get("results")
    if isinstance(benchmark_results, list) and len(benchmark_results) >= 2:
        failover_evidence = "BENCHMARKED"
    elif benchmark:
        failover_evidence = "INSUFFICIENT"
        warnings.append("failover_benchmark_insufficient")
    else:
        failover_evidence = "UNMEASURED"
        warnings.append("failover_transport_unmeasured")

    concentration = evaluate_concentration(sender_rows)

    # Score is an operational readiness summary, not send authority.
    score = 100.0
    if blockers:
        score -= 50.0
    if estate_status != "CONVERGED":
        score -= 10.0

    for result in (transport, domain, ip_pool):
        survival = float(result["worst_case_survival_rate"])
        if total_capacity:
            score -= max(0.0, 0.75 - survival) * 20.0

    if len(seed_families) < 2:
        score -= 10.0
    if failover_evidence == "UNMEASURED":
        score -= 10.0
    elif failover_evidence == "INSUFFICIENT":
        score -= 5.0

    score = max(0.0, min(100.0, score))

    if blockers:
        posture = "HOLD"
    elif score >= 85 and not warnings:
        posture = "RESILIENT"
    elif score >= 65:
        posture = "LIMITED"
    else:
        posture = "FRAGILE"

    material = {
        "posture": posture,
        "score": round(score, 2),
        "total_eligible_capacity": total_capacity,
        "transport": transport,
        "domain": domain,
        "ip_pool": ip_pool,
        "concentration": concentration,
        "verified_seed_families": seed_families,
        "failover_evidence": failover_evidence,
        "estate_status": estate_status,
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
