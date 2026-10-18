"""Bounded automatic source-quality analysis and existing department handoff.

Reuses the current acquisition inbox, vertical Founder readers and department
work queue. Never creates a buyer/lead, proves damage, invokes a paid model,
sends messages, publishes content or expands business authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import fcntl
import json
import os
import re
from collections import Counter
from urllib.parse import urlsplit

from empire_os.permit_intelligence_runtime import (
    PERMIT_SOURCES,
    build_permit_intelligence_runtime,
)
from empire_os.vertical_intelligence_runtime import (
    build_property_intelligence_runtime,
    build_private_capital_intelligence_runtime,
)
from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.free_dataset_intelligence import inspect_free_commoncrawl_dataset
from empire_os.data_brokerage_product_catalog import (
    validate_internal_brokerage_catalog,
)
from empire_os.permit_project_intelligence import analyze_permit_project_intelligence


CANONICAL_ROOT = Path("/srv/empire_os")
SNAPSHOT = Path("runtime/departments/source_intelligence_latest.json")
STATE = Path("runtime/departments/source_intelligence_dispatch_state.json")
LOCK = Path("runtime/departments/.source_intelligence_handoff.lock")
STORM = Path("runtime/storm_opportunity/latest.json")
SCHEMA = "empire.source_intelligence.department_handoff.v1"

# One durable, meaningful review per lane. These IDs are EXISTING departments.
LANES: dict[str, tuple[str, str, int]] = {
    "permit": ("market_intelligence", "qualify_official_permit_projects_and_source_quality", 95),
    "property": ("product", "join_observed_permits_to_verified_property_entities", 91),
    "private_capital": ("strategy", "resolve_canonical_sponsor_portfolio_source_evidence", 66),
    "storm": ("data_quant", "refresh_primary_storm_observations_and_geo_evidence", 64),
    "warehouse": ("market_intelligence", "recover_evidence_backed_industrial_asset_source", 62),
    "historical_search_graph": ("marketing_growth", "review_free_commoncrawl_competitor_domain_graph", 60),
    "data_brokerage": ("strategy", "qualify_original_data_product_offers_and_source_licences", 76),
}


def _read(path: Path) -> dict[str, Any] | None:
    try:
        val = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return val if isinstance(val, dict) else None


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ts.astimezone(timezone.utc) if ts.utcoffset() is not None else None
    except (ValueError, OverflowError, TypeError):
        return None


def _write(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(dict(data), handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _permit_activity(root: Path, now: datetime) -> dict[str, Any]:
    """Read current acquisition evidence, never materialize customer details.

    First observed and last seen are distinct. A refreshed old record is NOT
    a newly discovered project.  The host count proves first-party portal
    domain shape only, not a buyer, damage or resolved real-world owner.
    """
    records = _read(root / "runtime/acquisition/signal_inbox.json") or {}
    result: dict[str, Any] = {
        "observed_or_refreshed_last_24h": 0,
        "first_recorded_last_24h": 0,
        "official_nyc_portal_source_count": 0,
    }
    observed_job_types: Counter[str] = Counter()
    newest_identities: list[tuple[str, str]] = []
    for raw in records.values():
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "").strip().lower()
        if source not in PERMIT_SOURCES and "permit" not in source:
            continue
        ident = raw.get("signal_id")
        created = raw.get("created_at")
        if (isinstance(ident, str) and
                len(ident) <= 128 and isinstance(created, str)
                and _time(created) is not None):
            newest_identities.append((created, ident))
        seen = _time(raw.get("last_seen_at") or raw.get("created_at"))
        first = _time(raw.get("created_at"))
        if seen and timedelta(0) <= now - seen <= timedelta(hours=24):
            result["observed_or_refreshed_last_24h"] += 1
        if first and timedelta(0) <= now - first <= timedelta(hours=24):
            result["first_recorded_last_24h"] += 1
            # Government filing class codes, not arbitrary descriptions,
            # individual names, addresses, numbers, contacts, or free text.
            raw_job_type = (raw.get("raw") or {}).get("job_type") if (
                isinstance(raw.get("raw"), dict)) else None
            if isinstance(raw_job_type, str):
                job_type = raw_job_type.strip().upper()
                if re.fullmatch(r"[A-Z0-9]{1,4}", job_type):
                    observed_job_types[job_type] += 1
        url = raw.get("url")
        if isinstance(url, str) and urlsplit(url).scheme == "https" and (
            urlsplit(url).hostname == "a810-biswebportal.nyc.gov"
        ):
            result["official_nyc_portal_source_count"] += 1
    result["new_filing_type_mix"] = ",".join(
        f"{name}:{count}" for name,count in sorted(
            observed_job_types.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    )
    # A stable rolling *newest ever seen* identity digest picks up new source
    # records without treating a 24-hour expiry as a new arrival.
    result["latest_record_identity_digest"] = sha256(
        json.dumps(sorted(newest_identities, reverse=True)[:8],
                   separators=(",", ":")).encode()
    ).hexdigest() if newest_identities else None
    return result


def _lane(name: str, *, status: str, counts: Mapping[str, Any],
          source: str, evidence_refs: list[str], warnings: list[str],
          observed_at: str | None) -> dict[str, Any]:
    owner, action, priority = LANES[name]
    # No contact details, owner names, addresses, company names, IPs or raw
    # provider payload are passed to the department queue.
    safe_counts = {str(k): v for k, v in counts.items()
                   if isinstance(v, (str, int, bool, type(None))) and
                   len(str(v)) <= 100}
    clean = {
        "lane": name,
        "department": owner,
        "next_internal_action": action,
        "priority": priority,
        "status": status,
        "observed_at": observed_at,
        "source": source,
        "counts": safe_counts,
        "evidence_refs": list(evidence_refs[:4]),
        "blockers": list(warnings[:8]),
        "first_pass_analysis": "DETERMINISTIC_SOURCE_QUALITY",
        "independent_buyer_intent_proven": False,
        "property_damage_proven": False,
        "sale_or_revenue_proven": False,
        "model_semantic_review_performed": False,
        "execution_authority": "none",
    }
    fingerprint_input = {
        k: clean[k] for k in ("lane", "status", "source", "evidence_refs", "blockers")
    }
    # Age is a display field, not a source change. Otherwise the timer would
    # create a new task every time source_age_hours rounds to another decimal.
    freshness_display_only = {
        "source_age_hours", "observed_or_refreshed_last_24h",
        "first_recorded_last_24h", "new_filing_type_mix",
        "new_underlying_permit_signals_last_24h",
        "newly_imported_actual_filing_or_issuance_last_30d",
        "newly_imported_historical_filing_or_issuance",
        "recent_actual_filing_or_issuance_unverified",
    }
    fingerprint_input["counts"] = {
        k: v for k, v in safe_counts.items()
        if k not in freshness_display_only
    }
    clean["evidence_fingerprint"] = sha256(
        json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return clean


def build_source_intelligence_handoffs(
    repo_root: Path, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Classify CURRENT source evidence; UNKNOWN stays UNKNOWN.

    Counts from the existing Permit and Property readers refer to the SAME
    underlying NYC signals and must never be summed as independent prospects.
    """
    root = Path(repo_root).resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    permit = build_permit_intelligence_runtime(root)
    activity = _permit_activity(root, now)
    permit_projects = analyze_permit_project_intelligence(root, now=now)
    project_cohort = permit_projects["cohort"]
    property_ = build_property_intelligence_runtime(root)
    three_agency=property_.get("three_agency_source_reference_review") or {}
    capital = build_private_capital_intelligence_runtime(root)
    storm = _read(root / STORM)
    permit_seen = _time(permit.get("latest_seen_at"))
    permit_age = (now - permit_seen).total_seconds() if permit_seen else None
    permit_recent = permit_age is not None and 0 <= permit_age <= 24 * 3600
    permit_count = int(permit.get("signal_count") or 0)
    resolved = int(permit.get("resolved_count") or 0)
    permit_status = "CURRENT_OBSERVED" if permit_recent and permit_count else (
        "STALE_SOURCE" if permit_count else "MISSING_SOURCE")
    perm_blockers = ["buyer_demand_and_contract_unverified"]
    if permit_count and int(permit.get("with_source_url") or 0) != permit_count:
        perm_blockers.append("some_primary_urls_missing")
    if permit_count and int(permit.get("with_raw_reference") or 0) != permit_count:
        perm_blockers.append("some_source_identifiers_missing")
    if (permit.get("by_source") or {}).get("permits_nyc") and (
        activity["official_nyc_portal_source_count"] <
        (permit.get("by_source") or {}).get("permits_nyc", 0)
    ):
        perm_blockers.append("non_official_nyc_portal_source_present")
    if permit_status != "CURRENT_OBSERVED":
        perm_blockers.append("fresh_official_permit_data_required")
    else:
        perm_blockers.append("source_rows_not_verified_company_decision_makers")
    if project_cohort["first_imported_last_24h"] and not project_cohort["recent_original_filing_or_issuance"]:
        perm_blockers.append("recent_imports_have_no_recent_filing_or_issuance")
    perm_blockers.append("project_event_date_distinct_from_source_run_date")
    markets = list((permit.get("by_metro") or {}).keys())
    permit_lane = _lane(
        "permit",
        status=permit_status,
        source=str(permit.get("source_store") or ""),
        evidence_refs=(["runtime:acquisition:signal_inbox"] if permit_count else []),
        counts={
            "signal_count": permit_count,
            "resolved_source_rows": resolved,
            "unresolved_source_rows": int(permit.get("unresolved_count") or 0),
            "with_primary_source_url": int(permit.get("with_source_url") or 0),
            "with_official_reference": int(permit.get("with_raw_reference") or 0),
            "official_nyc_portal_source_count": activity[
                "official_nyc_portal_source_count"],
            "observed_or_refreshed_last_24h": activity[
                "observed_or_refreshed_last_24h"],
            "first_recorded_last_24h": activity[
                "first_recorded_last_24h"],
            "new_filing_type_mix": activity["new_filing_type_mix"],
            "latest_record_identity_digest": activity["latest_record_identity_digest"],
            "official_project_source_semantics_digest": permit_projects["total_retained_source_semantics_digest"],
            "newly_imported_actual_filing_or_issuance_last_30d": project_cohort["recent_original_filing_or_issuance"],
            "newly_imported_historical_filing_or_issuance": project_cohort["historical_project_source_only"],
            "market_gps_context_state": permit_projects["market_gps"]["state"],
            "markets": ",".join(sorted(markets)[:5]),
            "source_age_hours": (round(permit_age / 3600, 1)
                                 if permit_age is not None and permit_age >= 0 else None),
        },
        warnings=perm_blockers,
        observed_at=permit.get("latest_seen_at"),
    )
    property_count = property_.get("physical_observation_count")
    property_lane = _lane(
        "property",
        status=permit_status if permit_recent else "MISSING_PROPERTY_IDENTITY_EVIDENCE",
        source="permit_and_existing_spatial_read_models",
        evidence_refs=(["runtime:acquisition:signal_inbox"]
                       if permit_count else []),
        counts={
            "underlying_permit_signal_count": permit_count,
            "underlying_resolved_permit_rows": resolved,
            "new_underlying_permit_signals_last_24h": activity[
                "first_recorded_last_24h"],
            "new_filing_type_mix": activity["new_filing_type_mix"],
            "latest_record_identity_digest": activity["latest_record_identity_digest"],
            "official_project_source_semantics_digest": permit_projects["total_retained_source_semantics_digest"],
            "recent_actual_filing_or_issuance_unverified": project_cohort["recent_original_filing_or_issuance"],
            "physical_observation_count": property_count,
            "volumetric_observation_count": property_.get("volumetric_observation_count"),
            "verified_property_opportunity_count": None,
            "three_agency_review_status": three_agency.get("status"),
            "full_issued_day_source_count_reconciled": (
                three_agency.get("source_day_count_reconciled")),
            "reviewed_official_permit_event_count": (
                three_agency.get("reviewed_permit_event_count")),
            "full_day_issued_source_row_count": (
                three_agency.get("official_source_row_count")),
            "tri_agency_bin_bbl_reference_match_count": (
                three_agency.get("three_agency_bin_bbl_reference_match_count")),
            "tri_agency_reference_conflict_count": (
                three_agency.get("building_tax_lot_reference_conflict_count")),
            "tri_agency_billing_lot_match_count": (
                three_agency.get("three_agency_billing_lot_reference_match_count")),
        },
        warnings=[
            "same_permit_source_as_permit_lane_not_additional_leads",
            "tri_agency_source_references_are_not_property_ownership_or_buyer_identity",
            "property_entity_binding_not_verified",
            "observed_storm_exposure_is_not_building_damage",
        ],
        observed_at=permit.get("latest_seen_at"),
    )
    cap_count = capital.get("canonical_signal_count")
    cap_age = _time(capital.get("snapshot_generated_at"))
    capital_state = ("CURRENT_OBSERVED" if (cap_count or 0) > 0 and cap_age
                     and timedelta(0) <= now - cap_age <= timedelta(hours=24)
                     else "MISSING_CANONICAL_EVIDENCE")
    capital_lane = _lane(
        "private_capital",
        status=capital_state,
        source="runtime/vertical_intelligence/private_capital_latest.json",
        evidence_refs=(["runtime:vertical_intelligence:private_capital_latest"]
                       if capital_state == "CURRENT_OBSERVED" else []),
        counts={
            "signal_count": cap_count,
            "fact_count": capital.get("canonical_fact_count"),
            "membership_count": capital.get("segment_membership_count"),
            "observed_deal_intent": False,
        },
        warnings=["canonical_empiredb_source_identity_not_proven",
                  "legacy_supabase_source_must_not_be_promoted",
                  "sponsor_or_portfolio_buyer_intent_unverified"],
        observed_at=capital.get("snapshot_generated_at"),
    )
    storm_at = _time((storm or {}).get("generated_at"))
    storm_age = (now - storm_at).total_seconds() if storm_at else None
    storm_current = (isinstance(storm, dict)
                     and storm.get("mode") == "OBSERVE"
                     and storm.get("execution_authority") == "none"
                     and storm_age is not None and 0 <= storm_age <= 24 * 3600)
    storm_lane = _lane(
        "storm",
        status="CURRENT_OBSERVED" if storm_current else "STALE_OR_UNTRUSTED_SOURCE",
        source=str(STORM),
        evidence_refs=(["runtime:storm_opportunity:latest"] if storm_current else []),
        counts={"source_candidate_count": (
            int(storm.get("candidate_count") or 0) if storm_current else None
        )},
        warnings=["official_current_weather_and_geographic_source_required",
                  "storm_alert_does_not_prove_building_damage"],
        observed_at=(storm or {}).get("generated_at"),
    )
    warehouse_lane = _lane(
        "warehouse",
        status="SOURCE_INTEGRATION_REQUIRED",
        source="existing_industrial_sniper_and_idle_asset_read_models",
        evidence_refs=[],
        counts={
            "verified_warehouse_opportunity_count": None,
            "industrial_manufacturing_lot_context_only_count": (
                three_agency.get("industrial_manufacturing_tax_lot_context_count")),
            "warehouse_operation_verified_count": 0,
            "full_issued_day_source_count_reconciled": (
                three_agency.get("source_day_count_reconciled")),
        },
        warnings=["original_warehouse_sniper_reuse_requires_primary_sources",
                  "industrial_landuse_is_not_operating_warehouse_evidence",
                  "old_paid_places_make_webhook_and_legacy_paths_not_authorized",
                  "owner_occupancy_and_damage_not_verified"],
        observed_at=None,
    )
    routes = [permit_lane, property_lane, capital_lane, storm_lane, warehouse_lane]
    # The catalogue must be a previously generated, immutable-scope,
    # rights-held internal preview. The existing department timer does not
    # open a protected database connection or sell/download source data.
    brokerage_file = root / "runtime/data_brokerage/internal_product_catalog_latest.json"
    brokerage_review = (
        _read(brokerage_file) if root == CANONICAL_ROOT else None
    )
    if brokerage_review is not None and not validate_internal_brokerage_catalog(
        brokerage_review
    ):
        brokerage_review = None
    if brokerage_review is not None:
        routes.append(_lane(
            "data_brokerage",
            status="INTERNAL_RIGHTS_AWARE_PRODUCT_CATALOG_REVIEW",
            source="existing_data_exchange_custody_and_free_source_catalog",
            evidence_refs=["runtime:data_brokerage:internal_product_catalog_latest"],
            counts={
                "catalog_evidence_sha256": brokerage_review["evidence_scope_sha256"],
                "internal_product_count": brokerage_review["product_count"],
                "founder_asset_origin_declaration_count": brokerage_review[
                    "registered_founder_owned_asset_count"],
                "approved_customer_data_exports": 0,
                "actual_brokerage_sales": 0,
            },
            warnings=[
                "third_party_raw_record_resale_not_authorized",
                "source_field_licences_and_attribution_required",
                "self_declared_founder_origin_is_not_independent_copyright_proof",
                "no_customer_export_or_outbound_activated",
            ],
            observed_at=brokerage_review["generated_at"],
        ))
    # Review only the already downloaded FREE graph metadata, never bulk-copy
    # the 9GB archive, treat historical edges as live links, or use paid APIs.
    graph_review = inspect_free_commoncrawl_dataset() if root == CANONICAL_ROOT else None
    if (graph_review and graph_review.get("status")
            == "REVIEWED_HISTORICAL_RESEARCH_AVAILABLE"):
        routes.append(_lane(
            "historical_search_graph",
            status="HISTORICAL_RESEARCH_REVIEW_READY",
            source="existing_free_commoncrawl_domain_graph_review",
            evidence_refs=["source:commoncrawl_2026_historical_domain_graph"],
            counts={
                "review_sha256": graph_review["review_sha256"],
                "historical_relationships": graph_review["historical_relation_count"],
                "distinct_source_domains": graph_review["distinct_source_domain_count"],
                "cross_target_source_domains": graph_review["cross_target_source_domain_count"],
                "confirmed_live_backlinks": 0,
                "target_count": len(graph_review["target_domains"]),
            },
            warnings=[
                "historical_domain_graph_edges_are_not_verified_live_backlinks",
                "no_page_level_anchor_proof",
                "human_review_required_for_all_candidate_domains",
                "no_automatic_outreach_or_commercial_promotion",
            ],
            observed_at=graph_review["reviewed_at_utc"],
        ))
    return {
        "schema_version": SCHEMA,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "routes": routes,
        "lane_count": len(routes),
        "current_evidence_lane_count": sum(
            x["status"] == "CURRENT_OBSERVED" for x in routes
        ),
        "unique_underlying_nyc_permit_signal_count": permit_count,
        "permit_project_intelligence": permit_projects,
        "free_dataset_brain_review": graph_review,
        "data_brokerage_internal_review": brokerage_review,
        "raw_customer_records_exported": False,
        "automatic_outreach_sent": False,
        "paid_model_invoked": False,
        "payments_executed": False,
        "recognized_revenue_proven": False,
        "execution_authority": "none",
    }


def dispatch_source_intelligence_handoffs(
    repo_root: str | Path, *, now: datetime | None = None,
    max_jobs: int = 3, allow_noncanonical_test: bool = False,
) -> dict[str, Any]:
    """Deliver meaningful source changes to the EXISTING department work queue.

    At most one new task per lane per UTC hour and at most max_jobs per cycle.
    Source fingerprints exclude heartbeat timestamps to avoid resending the
    same 7,726 permit rows each cycle. No new bus/scheduler/DB.
    """
    root = Path(repo_root).resolve()
    if root != CANONICAL_ROOT and not allow_noncanonical_test:
        return {"status": "NOT_CANONICAL_RUNTIME", "handoffs_enqueued": 0,
                "execution_authority": "none"}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not 1 <= max_jobs <= 5:
        raise ValueError("max_jobs must be 1-5")
    payload = build_source_intelligence_handoffs(root, now=now)
    lock_path = root / LOCK
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    os.chmod(lock_path, 0o600)
    enqueued = 0
    unchanged = 0
    rate_held = 0
    hour = now.strftime("%Y%m%d%H")
    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state_path = root / STATE
        prev = _read(state_path)
        if state_path.exists() and prev is None:
            raise ValueError("existing_handoff_state_unreadable")
        state = dict((prev or {}).get("lanes") or {})
        # Publish a complete, sanitized source truth BEFORE any queue item can
        # be consumed; update after enqueue to include delivery receipts.
        _write(root / SNAPSHOT, payload)
        queue = DepartmentWorkQueue(root)
        for row in sorted(payload["routes"], key=lambda r: -r["priority"]):
            lane = row["lane"]
            old = dict(state.get(lane) or {})
            if row["evidence_fingerprint"] == old.get("fingerprint"):
                row["delivery_status"] = "UNCHANGED"
                if isinstance(old.get("work_id"), str):
                    row["department_work_id"] = old["work_id"]
                unchanged += 1
                continue
            if enqueued >= max_jobs or old.get("last_hour") == hour:
                row["delivery_status"] = "BOUNDED_RETRY_NEXT_CYCLE"
                rate_held += 1
                continue
            step = {
                "step_id": f"{lane}_{hour}",
                "goal_key": "interpret_new_canonical_source_evidence",
                "department_keys": [row["department"]],
                "target_component": "source_intelligence_review",
                "action": row["next_internal_action"],
                "authority": "observe",
                "evidence_refs": list(row["evidence_refs"]),
                "rationale": "Bounded observed source change, not a qualified lead",
                "success_condition": "Internal source analysis receipt, not buyer or revenue",
                "intelligence_request": {
                    "source_intelligence_review": {
                        "lane": lane,
                        "evidence_fingerprint": row["evidence_fingerprint"],
                    },
                    # Resource-usage budgets are a separate authority.
                    # The canonical department token allocation is currently
                    # UNCONFIGURED. No model usage in automatic source intake;
                    # safe deterministic handoffs must not be blocked.
                    "budget": {
                        "requested_model_tokens": 0,
                        "requested_external_cost_cents": 0,
                    },
                },
            }
            work, created = queue.enqueue_step(
                plan_id="source_intelligence_review_v1",
                step=step,
                priority=row["priority"],
            )
            row["delivery_status"] = "QUEUED" if created else "ALREADY_QUEUED"
            row["department_work_id"] = work.id
            state[lane] = {
                "fingerprint": row["evidence_fingerprint"],
                "last_hour": hour,
                "work_id": work.id,
            }
            enqueued += int(created)
        _write(root / SNAPSHOT, payload)
        _write(state_path, {"schema_version": SCHEMA,
                             "updated_at": now.isoformat(), "lanes": state})
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return {
        "status": "ROUTED_TO_EXISTING_DEPARTMENTS",
        "mode": "OBSERVE",
        "handoffs_enqueued": enqueued,
        "handoffs_unchanged": unchanged,
        "handoffs_rate_held": rate_held,
        "current_evidence_lane_count": payload["current_evidence_lane_count"],
        "source_lane_count": payload["lane_count"],
        "unique_underlying_nyc_permit_signal_count": payload[
            "unique_underlying_nyc_permit_signal_count"
        ],
        "source_snapshot_ref": "runtime:departments:source_intelligence_latest",
        "paid_model_invoked": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


# Closed, source-verifiable next steps. The local model may only select one
# option. It may NOT compose factual allegations, prospects or new actions.
_SHADOW_ACTIONS: dict[str, tuple[str, ...]] = {
    "permit": (
        "verify_recent_project_scope_at_official_portal",
        "validate_permittee_business_identity_using_primary_source",
        "compare_new_filing_types_against_historical_source_baseline",
    ),
    "property": (
        "resolve_property_bin_bbl_to_primary_records",
        "verify_shared_permit_property_reference_without_double_count",
        "collect_independent_site_condition_evidence",
    ),
}


def _local_semantic_source_review(
    review: Mapping[str, Any], *, client: Any = None,
) -> dict[str, Any]:
    """Shadow-only local LLM selection of an evidence-validation next step.

    Uses ONLY already aggregated fixed source metrics. Output is a constrained
    index into a reviewed research-action catalogue and cannot be promoted
    to a verified sale, claim, forecast or customer identity.
    """
    lane = str(review.get("lane") or "")
    metrics = review.get("source_quality_summary")
    metrics = metrics if isinstance(metrics, dict) else {}
    new_count = metrics.get(
        "first_recorded_last_24h" if lane == "permit"
        else "new_underlying_permit_signals_last_24h")
    basis = {
        "mode": "SHADOW_ONLY",
        "provider": "existing_local_llama_cpp",
        "model": "qwen2.5-coder:1.5b",
        "model_inference_performed": False,
        "model_output_review_status": "NOT_ELIGIBLE",
        "suggested_next_action": None,
        "source_facts_reinterpreted_as_sales": False,
        "action_execution_authorized": False,
        "execution_authority": "none",
    }
    if (lane not in _SHADOW_ACTIONS
            or review.get("observed_source_status") != "CURRENT_OBSERVED"
            or type(new_count) is not int or not 0 < new_count <= 100000):
        return basis
    options = _SHADOW_ACTIONS[lane]
    # Do not send raw file, free-text record, owner, site address, contact
    # detail or URL to a model (even local). It selects RESEARCH only.
    safe_input = {
        "source_lane": lane,
        "recent_new_record_count": new_count,
        "recent_filing_type_mix": metrics.get("new_filing_type_mix") or "",
        "research_choices": list(options),
        "source_identity_verified": False,
        "sales_or_revenue_verified": False,
    }
    user = json.dumps(safe_input, sort_keys=True)
    system = (
        "You are a read-only Empire AI research assistant. Select the single "
        "most useful NEXT EVIDENCE-VERIFICATION action from the supplied "
        "research_choices. Return ONLY JSON {\"action_index\":0} with an "
        "integer index in range. Do not invent evidence, contacts, damage, "
        "buying intent, risk, payment or actions. No explanation or markdown."
    )
    if client is None:
        from empire_os.coder.llama_cpp_provider import LlamaCppProvider
        client = LlamaCppProvider(
            base_url="http://127.0.0.1:11435",
            timeout_seconds=20,
            model="qwen2.5-coder:1.5b",
        )
    try:
        raw = client.chat(
            [{"role": "user", "content": user}],
            system=system, temperature=0.0, max_tokens=64,
        )
    except (OSError, RuntimeError, ValueError, TimeoutError):
        return {**basis, "model_inference_performed": False,
                "model_output_review_status": "HOLD_LOCAL_MODEL_FAILED"}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = None
    if (not isinstance(parsed, dict)
            or set(parsed) != {"action_index"}
            or type(parsed["action_index"]) is not int
            or not 0 <= parsed["action_index"] < len(options)):
        return {**basis, "model_inference_performed": True,
                "model_output_review_status": "HOLD_UNTRUSTED_MODEL_RESPONSE"}
    return {
        **basis,
        "model_inference_performed": True,
        "model_output_review_status": "VALIDATED_SHADOW_RESEARCH_CHOICE",
        "suggested_next_action": options[parsed["action_index"]],
    }


def deliver_source_intelligence_review(
    repo_root: Path, *, lane: str, fingerprint: str,
    department: str, allow_local_model: bool = False,
    model_client: Any = None,
) -> dict[str, Any]:
    """Complete a source-quality review RECEIPT for an existing queued team."""
    if lane not in LANES or LANES[lane][0] != department:
        raise ValueError("unknown_or_wrong_department_source_lane")
    payload = _read(Path(repo_root).resolve() / SNAPSHOT)
    if not payload or payload.get("schema_version") != SCHEMA:
        raise ValueError("canonical_source_handoff_snapshot_missing")
    row = next((v for v in payload.get("routes", [])
                if isinstance(v, dict) and v.get("lane") == lane), None)
    if row is None or row.get("evidence_fingerprint") != fingerprint:
        raise ValueError("source_handoff_evidence_superseded")
    reviewed = payload.get("permit_project_intelligence")
    reviewed = reviewed if isinstance(reviewed, dict) else {}
    brokerage_catalog = payload.get("data_brokerage_internal_review")
    brokerage_catalog = (brokerage_catalog if isinstance(brokerage_catalog, dict) else {})
    free_graph_review = payload.get("free_dataset_brain_review")
    free_graph_review = (
        free_graph_review if isinstance(free_graph_review, dict) else {}
    )
    result = {
        "adapter": "existing_department_source_analysis_receipt",
        "lane": lane,
        "department": department,
        "observed_source_status": row["status"],
        "first_pass_analysis_completed": True,
        "source_signal_batch_references": list(row["evidence_refs"]),
        "source_quality_summary": dict(row["counts"]),
        "followup_evidence_requirements": list(row["blockers"]),
        "next_internal_action": row["next_internal_action"],
        "data_brokerage_internal_review": (
            {
                "product_count": brokerage_catalog.get("product_count"),
                "evidence_scope_sha256": brokerage_catalog.get("evidence_scope_sha256"),
                "products": [
                    {
                        "product_id": p.get("product_id"),
                        "source_state": p.get("internal_source_state"),
                        "origin_class": p.get("source_origin_class"),
                        "licence_state": p.get("source_licence_state"),
                        "buyer_verified": False,
                        "customer_delivery_enabled": False,
                    }
                    for p in brokerage_catalog.get("products", [])
                ],
                "customer_distribution_authorized": False,
                "actual_revenue_verified": False,
            } if lane == "data_brokerage" else None
        ),
        "historical_free_dataset_brain_review": (
            free_graph_review if lane == "historical_search_graph" else None
        ),
        "project_intelligence_review": (
            {
                "schema_version": reviewed.get("schema_version"),
                "market_gps": reviewed.get("market_gps"),
                "cohort": reviewed.get("cohort"),
                "review_work_state": reviewed.get("review_work_state"),
                "review_dossiers": list((reviewed.get("review_dossiers") or [])[:3])
                    if lane == "permit" else [],
                "same_underlying_permit_source": lane == "property",
                "real_business_buyer_or_property_identity_verified": False,
            } if lane in ("permit", "property") else None
        ),
        "semantic_model_review_performed": False,
        "payable_buyer_verified": False,
        "outbound_sent": False,
        "recognized_revenue_proven": False,
        "execution_authority": "none",
    }
    if allow_local_model:
        result["model_shadow"] = _local_semantic_source_review(
            result, client=model_client,
        )
        result["semantic_model_review_performed"] = (
            result["model_shadow"]["model_output_review_status"]
            == "VALIDATED_SHADOW_RESEARCH_CHOICE"
        )
    return result
