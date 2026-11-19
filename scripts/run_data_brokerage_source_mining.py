#!/usr/bin/env python3
"""Use the EXISTING EmpireOS department heartbeat for bounded source mining.

One private state and lock, minimum twelve hours between actual network
refreshes. --read-only is for operator verification and does not write.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import fcntl
import json
import os
import zipfile

from empire_os.data_brokerage_source_mining import (
    build_brokerage_source_mining, due_source_cycle,
    load_verified_cycle, persist_source_cycle, DISCOVERY_QUERIES,
)
from empire_os.data_brokerage_us_construction_product import (
    persist_private_market_product, validate_private_market_product,
)

LOCK = Path("runtime/data_brokerage/.source_mining.lock")


def run_due_brokerage_source_mining(
    root: Path, *, now: datetime | None = None,
    persist: bool = True, search=None, fetch=None, catalog_fetch=None, recent_fetch=None,
    texas_research_runner=None,
) -> dict:
    root = Path(root).resolve()
    current = now or datetime.now(timezone.utc)
    if current.utcoffset() is None:
        raise ValueError("CLOCK_NOT_UTC_AWARE")
    lock = root / LOCK
    if persist:
        lock.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(lock.parent, 0o700)
        if lock.is_symlink():
            raise ValueError("UNTRUSTED_BROKERAGE_LOCK")
        lock.touch(exist_ok=True)
        os.chmod(lock, 0o600)
    # Nonpersisting inspections can run without a persistent lock.
    def _cycle() -> dict:
        previous = load_verified_cycle(root)
        # Scoped scientific and multi-niche evidence uses THIS existing
        # brokerage owner's lock/heartbeat and a separate 24h source budget.
        scientific_evidence = {"status": "NONCANONICAL_OR_READONLY",
                               "external_requests": 0}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.data_brokerage_scientific_evidence import (
                    run_original_broker_scientific_evidence,
                )
                scientific_evidence = run_original_broker_scientific_evidence(
                    root, now=current,
                )
            except (OSError, ValueError, TypeError, KeyError, TimeoutError, RuntimeError) as exc:
                scientific_evidence = {"status": "SCIENTIFIC_SOURCE_OWNER_HELD",
                    "error_class": type(exc).__name__, "external_requests": 0,
                    "customer_distribution_authorized": False}
        # Professional multi-niche source refresh uses this SAME source-owner
        # lock and department heartbeat, with per-publisher frequency budgets.
        professional_feed = {"status": "NONCANONICAL_OR_READONLY", "network_requests": 0}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.data_brokerage_enterprise_feed import run_due as professional_due
                professional_feed = professional_due(root, now=current)
            except (OSError, ValueError, TypeError, KeyError, TimeoutError, RuntimeError) as exc:
                professional_feed = {
                    "status": "PROFESSIONAL_FEED_SOURCE_OWNER_HELD",
                    "error_class": type(exc).__name__, "network_requests": 0,
                    "customer_delivery_authorized": False,
                }
        # Materialize downstream professional product views using the same
        # original owner, source receipts and lock (no network, no new timer).
        professional_views = {"status": "NONCANONICAL_OR_READONLY", "view_writes": 0}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.data_brokerage_enterprise_packaging import run_due as product_views_due
                professional_views = product_views_due(root, now=current)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                professional_views = {
                    "status": "PROFESSIONAL_PRODUCT_VIEW_QUALITY_HOLD",
                    "error_class": type(exc).__name__, "view_writes": 0,
                    "products_authorized_for_sale": 0,
                }
        private_research_bundles = {"status": "NONCANONICAL_OR_READONLY", "bundles_built": 0}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.data_brokerage_enterprise_private_bundles import run_due as bundle_due
                private_research_bundles = bundle_due(root, now=current)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
                private_research_bundles = {
                    "status": "PRIVATE_RESEARCH_BUNDLE_QUALITY_HOLD",
                    "error_class": type(exc).__name__, "bundles_built": 0,
                    "customer_downloads_enabled": False,
                }
        # Hand verified originals and derived research to the EXISTING
        # Predictive Cloud private research lane, under this same source-owner
        # lock and timer. No forecasts, tenant exposure, training or sales.
        predictive_cloud_research = {"status": "NONCANONICAL_OR_READONLY",
                                     "source_datasets_admitted": 0,
                                     "derived_views_admitted": 0}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.predictive_cloud_brokerage_research import (
                    import_brokerage_research_inputs,
                )
                predictive_cloud_research = import_brokerage_research_inputs(
                    root, now=current,
                )
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                predictive_cloud_research = {
                    "status": "PREDICTIVE_CLOUD_RESEARCH_INPUT_HOLD",
                    "error_class": type(exc).__name__,
                    "source_datasets_admitted": 0,
                    "derived_views_admitted": 0,
                    "production_training_samples_admitted": 0,
                    "customer_downloads_authorized": False,
                    "execution_authority": "none",
                }
        # Expose safe analytical observations to the ORIGINAL Predictive
        # Fabric bridge after the private Cloud research intake has passed.
        # The pinned customer forecast materializer remains untouched.
        predictive_fabric_research_features = {
            "status": "PRIVATE_CLOUD_RESEARCH_IMPORT_NOT_VERIFIED",
            "feature_segments": 0, "model_training_authorized": False,
        }
        if (persist and root == Path("/srv/empire_os")
                and predictive_cloud_research.get("status")
                    == "VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL"):
            try:
                from empire_os.predictive_cloud_brokerage_feature_adapter import (
                    refresh_internal_brokerage_features,
                )
                predictive_fabric_research_features = (
                    refresh_internal_brokerage_features(root, now=current)
                )
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                predictive_fabric_research_features = {
                    "status": "PREDICTIVE_FABRIC_RESEARCH_FEATURE_HOLD",
                    "error_class": type(exc).__name__,
                    "feature_segments": 0,
                    "model_training_authorized": False,
                    "tenant_exposure_authorized": False,
                    "execution_authority": "none",
                }
        # Research-only temporal pilot: archive-pinned publisher-stage labels,
        # under this same brokerage owner lock and existing department timer.
        # NEVER admit customer outcomes, production forecasts or training.
        temporal_research_pilot = {
            "status": "RESEARCH_FEATURES_NOT_VERIFIED_HOLD",
            "forecast_predictions_produced": 0,
            "production_model_training_authorized": False,
        }
        if (persist and root == Path("/srv/empire_os")
                and predictive_fabric_research_features.get("status") in (
                    "VERIFIED_INTERNAL_CLOUD_RESEARCH_FEATURES",
                    "VERIFIED_UNCHANGED_CLOUD_RESEARCH_FEATURES")):
            try:
                from empire_os.predictive_cloud_temporal_research_pilot import (
                    refresh_research_pilot,
                )
                temporal_research_pilot = refresh_research_pilot(root, now=current)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                temporal_research_pilot = {
                    "status": "TEMPORAL_PUBLISHER_EVIDENCE_HOLD",
                    "error_class": type(exc).__name__,
                    "forecast_predictions_produced": 0,
                    "production_model_training_authorized": False,
                    "tenant_exposure_authorized": False,
                    "execution_authority": "none",
                }
        # Verify the already-frozen November prospective research ranking.
        # Never re-score or replace a frozen cohort in a scheduled cycle.
        prospective_research_freeze = {
            "status": "TEMPORAL_RESEARCH_SOURCE_NOT_VERIFIED_HOLD",
            "research_scored_projects": 0,
            "production_forecasts_produced": 0,
            "model_training_authorized": False,
        }
        # The frozen November cohort remains independently verifiable even
        # when a NEW publisher edition makes the old temporal source held.
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.predictive_cloud_prospective_freeze import (
                    verify_frozen_cohort,
                )
                prospective_research_freeze = verify_frozen_cohort(root)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                prospective_research_freeze = {
                    "status": "PROSPECTIVE_FROZEN_RESEARCH_COHORT_INTEGRITY_HOLD",
                    "error_class": type(exc).__name__,
                    "research_scored_projects": 0,
                    "production_forecasts_produced": 0,
                    "model_training_authorized": False,
                    "tenant_exposure_authorized": False,
                }
        # Read the ORIGINAL seven-day DESNZ source refresh receipt to
        # evaluate only a future verified official Q4 publisher edition.
        # Present-day Q3 data means WAIT with no writes and no forecasts.
        prospective_outcome_evaluation = {
            "status": "FROZEN_NOVEMBER_RESEARCH_COHORT_NOT_VERIFIED_HOLD",
            "evaluation_writes": 0, "production_forecasts_produced": 0,
        }
        if (persist and root == Path("/srv/empire_os")
                and prospective_research_freeze.get("status")
                    == "VERIFIED_IMMUTABLE_PROSPECTIVE_RESEARCH_FREEZE"):
            try:
                from empire_os.predictive_cloud_prospective_outcome_eval import (
                    check_due as check_future_publisher_outcomes,
                )
                prospective_outcome_evaluation = check_future_publisher_outcomes(
                    root, now=current)
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                prospective_outcome_evaluation = {
                    "status": "NEXT_OFFICIAL_PUBLISHER_EVIDENCE_OR_EVALUATION_HOLD",
                    "error_class": type(exc).__name__,
                    "evaluation_writes": 0,
                    "production_forecasts_produced": 0,
                    "customer_delivery_authorized": False,
                }
        scheduled_feed_observation = {"status": "NOT_SYSTEMD_OWNER_INVOCATION", "timer_receipt_written": False}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.data_brokerage_enterprise_feed import record_scheduled_owner_observation
                scheduled_feed_observation = record_scheduled_owner_observation(
                    root, professional_feed, professional_views, now=current,
                    cloud_research=predictive_cloud_research,
                    fabric_research=predictive_fabric_research_features,
                    temporal_research=temporal_research_pilot,
                    frozen_research=prospective_research_freeze,
                    future_outcome=prospective_outcome_evaluation)
            except (OSError, ValueError, TypeError, KeyError):
                scheduled_feed_observation = {
                    "status": "SCHEDULED_OWNER_OBSERVATION_HELD",
                    "timer_receipt_written": False,
                }
        # Original Data Brokerage source miner owns this once-per-day
        # public-data verification even during its 12-hour query cooldown.
        planning = {"status": "NONCANONICAL_OR_READONLY",
                    "network_requests": 0}
        if persist and root == Path("/srv/empire_os"):
            try:
                from empire_os.data_brokerage_uk_planning_daily import run_due as planning_due
                planning = planning_due(now=current)
            except Exception as exc:
                planning = {"status": "DAILY_PLANNING_ORIGINAL_SOURCE_HOLD",
                            "reason_class": type(exc).__name__,
                            "network_requests": 0}
        if persist and not due_source_cycle(root, now=current):
            # Run a rate-limited Texas-only recovery under THIS ORIGINAL
            # source owner's existing lock. It never advances the 12h
            # general mining checkpoint or creates another scheduler.
            texas_retry = {"status": "NONCANONICAL_NO_RETRY", "network_requests": 0}
            if root == Path("/srv/empire_os"):
                try:
                    from empire_os.data_brokerage_texas_retry import (
                        retry_in_original_owner,
                    )
                    texas_retry = retry_in_original_owner(
                        root, now=current, previous=previous,
                        texas_runner=texas_research_runner,
                    )
                except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                    texas_retry = {
                        "status": "TEXAS_RETRY_SOURCE_HOLD",
                        "network_requests": 0,
                        "execution_authority": "none",
                    }
            texas_status = "NOT_YET_OBSERVED"
            if root == Path("/srv/empire_os"):
                try:
                    from empire_os.data_brokerage_texas_agent import load_state
                    texas_latest = load_state(root, now=current)
                    texas_status = (
                        texas_latest["status"] if texas_latest
                        else "NO_CURRENT_VERIFIED_TEXAS_RECEIPT"
                    )
                except (OSError, ValueError, TypeError, KeyError):
                    texas_status = "TEXAS_SOURCE_STATUS_HOLD"
            return {
                "status": "SOURCE_MINING_COOLDOWN_REUSED",
                "texas_original_brokerage_retry": texas_retry,
                "texas_original_brokerage_agent_status": texas_status,
                "latest_cycle": previous.get("observed_at") if previous else None,
                "next_eligible_at": previous.get("next_eligible_at") if previous else None,
                "provider_requests": 0, "government_catalogue_requests": 0,
                "mining_requests": 0,
                "us_construction_official_status": (
                    (previous or {}).get("us_construction_official_research") or {}
                ).get("status", "NOT_YET_OBSERVED"),
                "uk_planning_daily_refresh": planning,
                "scientific_multi_niche_evidence": scientific_evidence,
                "enterprise_professional_data_feed": professional_feed,
                "enterprise_professional_product_views": professional_views,
                "enterprise_private_research_bundles": private_research_bundles,
                "predictive_cloud_brokerage_research_inputs": predictive_cloud_research,
                "predictive_fabric_brokerage_research_features": predictive_fabric_research_features,
                "predictive_cloud_temporal_research_pilot": temporal_research_pilot,
                "predictive_cloud_prospective_research_freeze": prospective_research_freeze,
                "predictive_cloud_future_publisher_outcome_evaluation": prospective_outcome_evaluation,
                "enterprise_professional_systemd_observation": scheduled_feed_observation,
                "execution_authority": "none",
            }
        # Advance existing indexed query rotation once per cycle, rather
        # than returning the same candidates every twelve hours.
        last_index = previous.get("discovery", {}).get("query_index", -1) if previous else -1
        index = (last_index + 1) % len(DISCOVERY_QUERIES)
        kwargs = {"now": current, "query_index": index}
        private_market_candidate: list[dict] = []
        if persist and root == Path("/srv/empire_os"):
            kwargs["construction_product_sink"] = private_market_candidate.append
        if search is not None:
            kwargs["search"] = search
        if fetch is not None:
            kwargs["fetch"] = fetch
        if catalog_fetch is not None:
            kwargs["catalog_fetch"] = catalog_fetch
        if recent_fetch is not None:
            kwargs["recent_fetch"] = recent_fetch
        result = build_brokerage_source_mining(root, **kwargs)
        buyer_role_status = "NOT_CHECKED_NONCANONICAL_OR_READONLY"
        if persist and root == Path("/srv/empire_os"):
            # One bounded first-party role check inside the ORIGINAL source
            # cycle. No new research scheduler, buying or external contact.
            try:
                from empire_os.data_brokerage_live_buyer_fit import (
                    classify_existing_brokerage_buyers,
                    validate_brokerage_first_party_roles,
                    persist_first_party_fit,
                    validate_first_party_fit_summary,
                )
                qualification = classify_existing_brokerage_buyers(root, now=current)
                if (qualification.get("status") == "FIRST_PARTY_COMMERCIAL_PURPOSES_REVIEWED"
                        and validate_brokerage_first_party_roles(qualification)):
                    summary = persist_first_party_fit(root, qualification)
                    if not validate_first_party_fit_summary(summary):
                        raise ValueError("FIRST_PARTY_BUYER_SUMMARY_POLICY_FAILED")
                    result["source_specific_product_intelligence"]["first_party_buyer_fit_summary"] = summary
                    buyer_role_status = summary["status"]
                else:
                    buyer_role_status = "ORIGINAL_FIRST_PARTY_SOURCE_HOLD"
            except (OSError, ValueError, TypeError, TimeoutError):
                buyer_role_status = "ORIGINAL_FIRST_PARTY_SOURCE_HOLD"
        private_market_state = "NO_ACCEPTED_MARKET_PRODUCT_CANDIDATE"
        texas_agent = {
            "status": "NOT_DUE_OR_NONCANONICAL",
            "source_receipts_committed": False,
            "execution_authority": "none",
            "outreach_sent": False,
        }
        if persist:
            persist_source_cycle(root, result)
            if root == Path("/srv/empire_os"):
                # Same existing 12-hour brokerage lock and department heartbeat.
                # No additional schedule, customer rights, or independent owner.
                try:
                    from empire_os.data_brokerage_texas_agent import run_texas_research
                    research = texas_research_runner or run_texas_research
                    texas_agent = research(
                        root, now=current, persist=True,
                        trigger="ORIGINAL_BROKERAGE_CYCLE",
                    )
                except (OSError, ValueError, TypeError, KeyError, TimeoutError, RuntimeError):
                    texas_agent = {
                        "status": "TEXAS_AUTOMATED_SOURCE_QUALITY_HOLD",
                        "source_receipts_committed": False,
                        "execution_authority": "none",
                        "outreach_sent": False,
                    }
            # Commit the evidence-backed market preview within the original
            # twelve-hour source-owner lock, after the canonical mining record.
            if private_market_candidate and root == Path("/srv/empire_os"):
                candidate = private_market_candidate[0]
                source = result.get("us_construction_official_research") or {}
                expected = source.get("source_sha256") or {}
                receipts = candidate.get("source_receipts") or []
                actual = {
                    "census": receipts[0].get("sha256") if len(receipts) == 4 else None,
                    "federal_awards": receipts[-1].get("sha256") if len(receipts) == 4 else None,
                }
                try:
                    if expected != actual or not validate_private_market_product(
                        candidate, now=current,
                    ):
                        raise ValueError("PRIVATE_PRODUCT_SOURCE_DIGEST_MISMATCH")
                    persist_private_market_product(root, candidate, now=current)
                    private_market_state = "PRIVATE_PRODUCT_EVIDENCE_MATERIALIZED"
                except (OSError, ValueError, TypeError, KeyError):
                    private_market_state = "PRIVATE_PRODUCT_COMMIT_HOLD"
        lane = result["product_targeting_sequence"]["active_lane"]
        mining_enabled = lane["country"] == "US" and lane["product"] == "property_development"
        return {
            "status": result["status"],
            "selected_country": lane["country"],
            "selected_sector": lane["sector"],
            "selected_brokerage_product": lane["product"],
            "proposed_customer_output": lane["proposed_output"],
            "next_evidence_step": lane["next_evidence_action"],
            "registered_source_candidates": len(lane["registered_source_candidates"]),
            "worldwide_registered_countries_scored": result["product_targeting_sequence"]["country_count"],
            "country_product_combinations_scored": result["product_targeting_sequence"]["country_product_combinations_evaluated"],
            "original_internal_product_intelligence_count": result["source_specific_product_intelligence"]["original_product_count"],
            "source_product_mining_status": result["source_specific_product_intelligence"]["status"],
            "source_product_contracts": result["source_specific_product_intelligence"].get("existing_product_contracts_used", []),
            "source_specific_market_status": result["source_specific_product_intelligence"].get("source_status", {}),
            "original_agency_report_buyer_fit_status": result["source_specific_product_intelligence"].get("original_agency_report_buyer_fit", {}).get("status", "NOT_CHECKED"),
            "original_agency_paid_buyers_verified": result["source_specific_product_intelligence"].get("original_agency_report_buyer_fit", {}).get("verified_paid_buyers"),
            "original_agency_offer_scope_fit": result["source_specific_product_intelligence"].get("original_agency_report_buyer_fit", {}).get("fit_assessment"),
            "official_public_buyer_requirements_checked": (result["source_specific_product_intelligence"].get("public_research_buyer_needs") or {}).get("official_notices_assessed", 0),
            "official_public_buyer_fit_verified": (result["source_specific_product_intelligence"].get("public_research_buyer_needs") or {}).get("suitable_bid_or_customer_order_verified", False),
            "targeted_indexed_buyer_jobs_reviewed": (result["source_specific_product_intelligence"].get("targeted_agency_publisher_buyer_scope") or {}).get("discovery_items_count", 0),
            "targeted_full_product_buyers_qualified": (result["source_specific_product_intelligence"].get("targeted_agency_publisher_buyer_scope") or {}).get("full_job_contracts_qualified", 0),
            "research_prospects_with_source_evidence": (result["source_specific_product_intelligence"].get("targeted_agency_publisher_buyer_scope") or {}).get("research_prospects_found", 0),
            "first_party_buyer_job_classification": buyer_role_status,
            "first_party_buyer_job_role_counts": (result["source_specific_product_intelligence"].get("first_party_buyer_fit_summary") or {}).get("first_party_role_counts", {}),
            "buyer_sales_are_not_prospects": True,
            "observed_at": result["observed_at"],
            "next_eligible_at": result["next_eligible_at"],
            "official_source_status": result["official_api_mining"]["status"],
            "sample_mined_count": result["official_api_mining"].get("validated_event_dates", 0),
            "recent_issued_sample_status": result["recent_official_permit_mining"]["status"],
            "recent_issued_sample_count": result["recent_official_permit_mining"].get("valid_recent_issue_dates_in_sample"),
            "source_registry_count": result["existing_source_registry_count"],
            "us_construction_official_status": result[
                "us_construction_official_research"
            ]["status"],
            "us_construction_award_sample_count": result[
                "us_construction_official_research"
            ].get("federal_award_records_accepted_in_sample"),
            "us_construction_private_market_product": private_market_state,
            "texas_original_brokerage_research_agent": texas_agent,
            "new_public_source_candidates": result["discovery"]["candidate_count"],
            "new_official_catalogue_candidates": result["official_dataset_discovery"]["candidate_count"],
            "official_catalogue_status": result["official_dataset_discovery"]["status"],
            "canonical_inbox_signals": result["existing_acquisition_mining"]["signal_count"],
            "provider_requests": 1,
            "government_catalogue_requests": int(mining_enabled),
            "mining_requests": 2 if mining_enabled else 0,
            "uk_planning_daily_refresh": planning,
            "scientific_multi_niche_evidence": scientific_evidence,
            "enterprise_professional_data_feed": professional_feed,
            "enterprise_professional_product_views": professional_views,
            "enterprise_private_research_bundles": private_research_bundles,
            "predictive_cloud_brokerage_research_inputs": predictive_cloud_research,
            "predictive_fabric_brokerage_research_features": predictive_fabric_research_features,
            "predictive_cloud_temporal_research_pilot": temporal_research_pilot,
            "predictive_cloud_prospective_research_freeze": prospective_research_freeze,
            "predictive_cloud_future_publisher_outcome_evaluation": prospective_outcome_evaluation,
            "enterprise_professional_systemd_observation": scheduled_feed_observation,
            "qualified_buyers_inferred": False, "outbound_sent": False,
            "rights_or_licences_elevated": False,
            "execution_authority": "none",
        }
    if not persist:
        return _cycle()
    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            return _cycle()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args(argv)
    root = Path("/srv/empire_os")
    report = run_due_brokerage_source_mining(root, persist=not args.read_only)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in {
        "SOURCE_MINING_CYCLE_EXECUTED", "SOURCE_MINING_COOLDOWN_REUSED",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
