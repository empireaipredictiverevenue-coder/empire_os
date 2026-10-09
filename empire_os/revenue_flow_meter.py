"""Read-only EmpireOS flow observability, without invented funnel conversion.

Only exact same-run company-domain joins may claim cohort coverage. Other
department receipts have different populations and are reported as such.
No database access, sending, approval or scheduling is performed here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import json
import os

OUTPUT = Path("runtime/buyer_acquisition/flow_meter_latest.json")
HISTORY = Path("runtime/buyer_acquisition/flow_meter_history.json")
MAX_HISTORY = 96
RECEIPTS = {
    "scout": "runtime/buyer_acquisition/scout_latest.json",
    "reconciliation": "runtime/buyer_acquisition/reconciliation_latest.json",
    "persistence": "runtime/buyer_acquisition/persistence_latest.json",
    "review": "runtime/buyer_acquisition/review_readiness_latest.json",
    "quality": "runtime/buyer_acquisition/evidence_quality_latest.json",
    "astra": "runtime/astra/executive_latest.json",
    "commercial_funnel": "runtime/commercial_funnel/latest.json",
    "revenue_pulse": "runtime/revenue_pulse/latest.json",
}
MAX_AGE_MINUTES = {
    "scout": 90, "reconciliation": 90, "persistence": 90,
    "review": 90, "quality": 90, "astra": 35,
    "commercial_funnel": 1440, "revenue_pulse": 35,
}
SOURCE_SCHEMAS = {
    "scout": "empire.buyer_acquisition_scout.v1",
    "reconciliation": "empire.buyer_scout_reconciliation.v1",
    "persistence": "empire.buyer_scout_persistence.v1",
    "review": "empire.buyer_scout_review_readiness.v1",
    "quality": "empire.buyer_evidence_quality.v1",
    "astra": "empire.astra.executive.v2",
    "commercial_funnel": "empire.founder_commercial_funnel.v1",
    "revenue_pulse": "empire.revenue-pulse.v3",
}


def _timestamp(raw: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _amount(raw: Any) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return raw


def _host(raw: Any) -> str:
    try:
        if not isinstance(raw, str):
            return ""
        uri = urlsplit(raw)
        if uri.scheme not in ("https", "http") or uri.username or uri.password:
            return ""
        host = (uri.hostname or "").lower().rstrip(".").removeprefix("www.")
        if uri.query or uri.fragment or uri.port not in (None, 80, 443):
            return ""
        return host if "." in host and ".." not in host and len(host) <= 250 else ""
    except ValueError:
        return ""


def _domain(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    clean = raw.casefold().rstrip(".").removeprefix("www.")
    return clean if "." in clean and ".." not in clean and "/" not in clean and "@" not in clean else ""


def source_health(
    receipts: Mapping[str, Mapping[str, Any] | None],
    *,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for name in RECEIPTS:
        value = receipts.get(name)
        if not isinstance(value, Mapping):
            states[name] = {
                "status": "unavailable", "generated_at": None,
                "age_minutes": None,
            }
            continue
        observed = _timestamp(value.get("generated_at") or value.get("observed_at"))
        same_schema = value.get("schema_version") == SOURCE_SCHEMAS[name]
        age = (now - observed).total_seconds() / 60 if observed else None
        if not same_schema:
            state = "schema_mismatch"
        elif age is None:
            state = "timestamp_missing"
        elif age < -5:
            state = "future_dated"
        elif age > MAX_AGE_MINUTES[name]:
            state = "stale"
        else:
            state = "fresh"
        states[name] = {
            "status": state,
            "generated_at": observed.isoformat() if observed else None,
            "age_minutes": round(age, 2) if age is not None else None,
        }
    return states


def _metric(
    source: str,
    value: int | None,
    scope: str,
    state: Mapping[str, Mapping[str, Any]],
    *,
    unit: str = "records",
) -> dict[str, Any]:
    health = state[source]["status"]
    return {
        "source": source, "scope": scope, "unit": unit,
        "observed_count": value,
        "current_count": value if health == "fresh" else None,
        "source_status": health,
        "authority": "observation_only",
    }


def _domain_join(scout: Mapping[str, Any], recon: Mapping[str, Any]) -> dict[str, Any]:
    scout_rows = scout.get("candidates")
    recon_rows = recon.get("results")
    if not isinstance(scout_rows, list) or not isinstance(recon_rows, list):
        return {"status": "lineage_not_available", "joined_count": None}
    lhs: list[str] = []
    for row in scout_rows:
        if not isinstance(row, Mapping):
            return {"status": "invalid_scout_candidate", "joined_count": None}
        domain = _domain(row.get("domain"))
        if not domain or domain != _host(row.get("website")):
            return {"status": "invalid_scout_domain", "joined_count": None}
        lhs.append(domain)
    rhs: list[str] = []
    for row in recon_rows:
        if not isinstance(row, Mapping):
            return {"status": "invalid_reconciliation_candidate", "joined_count": None}
        domain = _domain(row.get("domain"))
        if not domain:
            return {"status": "invalid_reconciliation_domain", "joined_count": None}
        rhs.append(domain)
    if len(set(lhs)) != len(lhs) or len(set(rhs)) != len(rhs):
        return {"status": "duplicate_domain_conflict", "joined_count": None}
    if (
        _amount(scout.get("candidate_count")) != len(lhs)
        or _amount(recon.get("candidate_count")) != len(rhs)
    ):
        return {"status": "count_and_records_mismatch", "joined_count": None}
    return {
        "status": "exact_domain_same_cycle",
        "joined_count": len(set(lhs) & set(rhs)),
        "scout_domains": len(lhs),
        "reconciliation_domains": len(rhs),
        "unmatched_scout_domains": len(set(lhs) - set(rhs)),
        "new_reconciliation_domains": len(set(rhs) - set(lhs)),
        "joining_key": "exact_company_domain",
    }


def build_flow_meter(
    receipts: Mapping[str, Mapping[str, Any] | None],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("flow meter clock must be timezone aware")
    current = current.astimezone(timezone.utc)
    health = source_health(receipts, now=current)
    data = {
        key: (value if isinstance(value, Mapping) else {})
        for key, value in receipts.items()
    }
    scout = data.get("scout", {})
    recon = data.get("reconciliation", {})
    persistence = data.get("persistence", {})
    quality = data.get("quality", {})
    review = data.get("review", {})
    astra = data.get("astra", {})
    commercial = data.get("commercial_funnel", {})
    pulse = data.get("revenue_pulse", {})

    scout_count = _amount(scout.get("candidate_count"))
    recon_count = _amount(recon.get("candidate_count"))
    persisted = _amount(persistence.get("persisted_candidate_count"))
    reviewed = _amount(review.get("candidate_count"))
    review_ready = _amount(review.get("review_ready_count"))
    quality_source_aligned = quality.get("stage_receipts_time_aligned") is True
    quality_fresh = quality.get("scout_receipt_fresh") is True
    quality_refs = quality.get("source_generated_at")
    quality_refs = quality_refs if isinstance(quality_refs, Mapping) else {}
    expected_quality_sources = {
        "scout": scout, "reconciliation": recon,
        "persistence": persistence, "holding_review": review,
    }
    quality_uses_exact_inputs = all(
        _timestamp(quality_refs.get(name)) is not None
        and _timestamp(quality_refs.get(name)) == _timestamp(source.get("generated_at"))
        for name, source in expected_quality_sources.items()
    )
    quality_usable = (
        health["quality"]["status"] == "fresh"
        and health["scout"]["status"] == "fresh"
        and quality_source_aligned and quality_fresh
        and quality_uses_exact_inputs
    )
    direct_buyer_proof = (
        _amount(quality.get("candidate_with_valid_direct_purchase_receipt"))
        if quality_usable else None
    )
    named_email_binding = (
        _amount(quality.get("candidate_with_strict_named_person_email_binding"))
        if quality_usable else None
    )
    scout_rows = scout.get("candidates")
    canonical_count = None
    if isinstance(scout_rows, list):
        canonical_count = sum(
            isinstance(row, Mapping)
            and row.get("canonical_identity_verified") is True
            and row.get("canonical_seed_identity_corroborated") is True
            and bool(row.get("canonical_seed_prospect_id"))
            and bool(row.get("canonical_seed_website"))
            for row in scout_rows
        )
    commercial_counts = commercial.get("counts")
    commercial_counts = commercial_counts if isinstance(commercial_counts, Mapping) else {}
    actual_revenue = pulse.get("recognized_revenue_truth")
    actual_revenue = actual_revenue if isinstance(actual_revenue, Mapping) else {}

    stages = {
        "discovered": _metric("scout", scout_count, "scout_run", health),
        "sites_probed": _metric(
            "scout", _amount(scout.get("probed_domain_count")),
            "scout_run", health,
        ),
        "first_party_source_receipts": _metric(
            "scout", _amount(scout.get("observed_first_party_buyer_claim_receipt_count")),
            "scout_run_raw_source_receipts_not_buyer_proof", health,
        ),
        "reconciled": _metric("reconciliation", recon_count, "scout_run", health),
        "holding_persisted": _metric("persistence", persisted, "scout_run_aggregate_only", health),
        "verified_purchasing_statements": _metric(
            "quality", direct_buyer_proof, "scout_run_first_party", health,
        ),
        "strict_named_email_bindings": _metric(
            "quality", named_email_binding, "scout_run_first_party", health,
        ),
        "corroborated_canonical_candidates": _metric(
            "scout", canonical_count, "scout_run_provisional_identity", health,
        ),
        "holding_review_scanned": _metric(
            "review", reviewed, "accumulated_pending_inventory", health,
        ),
        "holding_review_ready_transitions": _metric(
            "review", review_ready, "accumulated_pending_inventory", health,
        ),
        "astra_canonical_bindings": _metric(
            "astra", _amount(astra.get("canonical_company_binding_count")),
            "independent_astra_plan", health,
        ),
        "outbound_delivered": _metric(
            "commercial_funnel", _amount(commercial_counts.get("outbound_delivered")),
            "historic_cumulative_commercial", health,
        ),
        "commercial_replies": _metric(
            "commercial_funnel", _amount(commercial_counts.get("commercial_replies")),
            "historic_cumulative_commercial", health,
        ),
        "recognized_revenue_events": _metric(
            "commercial_funnel",
            _amount(commercial_counts.get("recognized_revenue_events")),
            "historic_cumulative_commercial", health,
        ),
        "recognized_revenue_cents": _metric(
            "revenue_pulse", _amount(actual_revenue.get("recognized_revenue_cents")),
            "recognized_accounting_truth", health, unit="GBP_pence",
        ),
    }
    scout_time = _timestamp(scout.get("generated_at"))
    recon_time = _timestamp(recon.get("generated_at"))
    is_joinable = bool(
        health["scout"]["status"] == "fresh"
        and health["reconciliation"]["status"] == "fresh"
        and scout_time and recon_time
        and timedelta(minutes=-2) <= recon_time - scout_time <= timedelta(minutes=15)
    )
    join = _domain_join(scout, recon) if is_joinable else {
        "status": "source_stale_or_not_same_run", "joined_count": None,
    }
    same_run_coverage = None
    if join["status"] == "exact_domain_same_cycle" and join["scout_domains"]:
        same_run_coverage = round(
            join["joined_count"] / join["scout_domains"], 4,
        )
    edges = {
        "scout_to_reconciliation": {
            **join, "coverage_ratio": same_run_coverage,
            "causal_conversion_rate": None,
            "comparison": "exact_domain_correlation_only",
        },
        "reconciliation_to_holding": {
            "status": "aggregate_only_no_per_record_join",
            "aggregate_persisted": stages["holding_persisted"]["current_count"],
            "causal_conversion_rate": None,
        },
        "holding_to_review": {
            "status": "different_populations_no_cohort_join",
            "causal_conversion_rate": None,
        },
        "review_to_astra": {
            "status": "no_canonical_record_lineage",
            "causal_conversion_rate": None,
        },
        "astra_to_outbound_and_revenue": {
            "status": "no_cross_system_prospect_event_lineage",
            "causal_conversion_rate": None,
        },
    }
    blockers = review.get("blocked_reason_counts")
    if not isinstance(blockers, Mapping):
        blockers = {}
    blocker_rows = [
        {"reason": key, "count": count}
        for key, raw in blockers.items()
        if isinstance(key, str) and (count := _amount(raw)) is not None
    ]
    blocker_rows.sort(key=lambda item: (-item["count"], item["reason"]))
    for name in ("commercial_funnel", "scout", "review", "quality", "astra"):
        if health[name]["status"] != "fresh":
            blocker_rows.append({
                "reason": "untrusted_" + name + "_snapshot",
                "count": None,
                "source_status": health[name]["status"],
            })
    if (
        health["scout"]["status"] == "fresh" and scout_count
        and canonical_count == 0
    ):
        blocker_rows.append({
            "reason": "no_canonical_company_domain_handoff_in_current_scout",
            "count": scout_count,
            "source_status": "fresh",
        })
    if (
        quality_usable and scout_count and direct_buyer_proof == 0
    ):
        blocker_rows.append({
            "reason": "no_first_party_purchasing_statements_in_current_scout",
            "count": scout_count,
            "source_status": "fresh",
        })

    identity_run = ""
    if scout_time and isinstance(scout_rows, list):
        domains = sorted(_domain(r.get("domain")) for r in scout_rows if isinstance(r, Mapping))
        identity_run = sha256((
            scout_time.isoformat() + "|" + "|".join(domains)
        ).encode("utf-8")).hexdigest()[:20]
    healthy = {
        "scout_fresh": health["scout"]["status"] == "fresh",
        "scout_to_reconciliation_verified": join["status"] == "exact_domain_same_cycle",
        "evidence_quality_aligned": quality_usable,
        "review_fresh": health["review"]["status"] == "fresh",
        "commercial_truth_fresh": health["commercial_funnel"]["status"] == "fresh",
        "revenue_truth_fresh": health["revenue_pulse"]["status"] == "fresh",
    }
    return {
        "schema_version": "empire.revenue_flow_meter.v1",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "scout_run_id": identity_run or None,
        "source_health": health,
        "stages": stages,
        "handoffs": edges,
        "blockers": blocker_rows[:15],
        "health_checks": healthy,
        "all_sources_current": all(s["status"] == "fresh" for s in health.values()),
        "verified_end_to_end_conversion_rate": None,
        "recognized_revenue_verified": (
            stages["recognized_revenue_cents"]["current_count"] is not None
        ),
        "limitations": [
            "Only same-run Scout->Reconciliation exact-domain coverage is measured.",
            "Persistence and review inventory counts have no record-level lineage.",
            "Historic cumulative commercial funnel is not this Scout cohort.",
            "No absent, stale or mismatched receipt is represented as a fresh zero.",
            "Recognized revenue is accounting truth, not projected intent.",
        ],
        "database_read_performed": False,
        "database_write_performed": False,
        "outbound_sent": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def _load_receipts(root: Path) -> dict[str, Mapping[str, Any] | None]:
    values: dict[str, Mapping[str, Any] | None] = {}
    for name, rel in RECEIPTS.items():
        try:
            raw = json.loads((root / rel).read_text(encoding="utf-8"))
            values[name] = raw if isinstance(raw, Mapping) else None
        except (OSError, ValueError, TypeError):
            values[name] = None
    return values


def _atomic_private_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".tmp")
    with staging.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
    os.chmod(staging, 0o600)
    staging.replace(path)
    os.chmod(path, 0o600)


def write_flow_meter(
    repo_root: Path,
    report: Mapping[str, Any],
    *,
    keep_history: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    _atomic_private_json(root / OUTPUT, report)
    if not keep_history:
        return {"history_count": None}
    previous = []
    path = root / HISTORY
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping) or not isinstance(data.get("samples"), list):
            raise ValueError("invalid_flow_history")
        previous = data["samples"][-MAX_HISTORY:]
    record = {
        "scout_run_id": report.get("scout_run_id"),
        "scout_generated_at": report.get("source_health", {}).get("scout", {}).get("generated_at"),
        "meter_generated_at": report.get("generated_at"),
        "scout_current": report.get("health_checks", {}).get("scout_fresh"),
        "discovered": report.get("stages", {}).get("discovered", {}).get("current_count"),
        "joined_by_exact_domain": report.get("handoffs", {}).get(
            "scout_to_reconciliation", {}
        ).get("joined_count"),
        "verified_purchase_statement_count": report.get("stages", {}).get(
            "verified_purchasing_statements", {}
        ).get("current_count"),
        "canonical_candidate_count": report.get("stages", {}).get(
            "corroborated_canonical_candidates", {}
        ).get("current_count"),
        "review_ready_transitions_different_population": report.get("stages", {}).get(
            "holding_review_ready_transitions", {}
        ).get("current_count"),
        "commercial_funnel_fresh": report.get("health_checks", {}).get(
            "commercial_truth_fresh"
        ),
        "recognized_revenue_cents": report.get("stages", {}).get(
            "recognized_revenue_cents", {}
        ).get("current_count"),
    }
    if record["scout_run_id"] and record["scout_current"]:
        samples = [
            sample for sample in previous
            if isinstance(sample, Mapping)
            and sample.get("scout_run_id") != record["scout_run_id"]
        ]
        samples.append(record)
        samples = sorted(
            samples,
            key=lambda item: str(item.get("scout_generated_at") or ""),
        )[-MAX_HISTORY:]
        _atomic_private_json(path, {
            "schema_version": "empire.revenue_flow_history.v1",
            "mode": "OBSERVE",
            "samples": samples,
            "sample_count": len(samples),
            "source": "bounded_read_only_flow_meter",
        })
        return {"history_count": len(samples)}
    return {"history_count": len(previous), "history_unchanged": True}


def refresh_flow_meter(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
    keep_history: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    payload = build_flow_meter(_load_receipts(root), now=now)
    tracking = write_flow_meter(root, payload, keep_history=keep_history)
    return {**payload, "tracking": tracking}
