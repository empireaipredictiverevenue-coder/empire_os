"""The Empire AI Meta Market Validation Agent (offline research-only).

A deterministic specialist for Greg Isenberg's niche/city/rules -> verified
list -> owned distribution -> vertical software validation framework.

It does not collect from Meta, run outbound, activate ad spend, modify CRM,
invent buyers, create payable appointments, or self-authorise deployment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.meta_social_opportunity_research import SCHEMA as EVIDENCE_SCHEMA
from empire_os.meta_social_opportunity_research import review_packet

AGENT_SCHEMA = "empire.meta_market_validation_agent.v1"
OWNER = "meta_market_validation_agent"
DEFAULT_LANES = (
    {"id": "us_hvac_phoenix", "niche": "hvac", "city": "Phoenix, AZ", "us_zip": "85001"},
    {"id": "us_roofing_tampa", "niche": "roofing", "city": "Tampa, FL", "us_zip": "33602"},
)
LEVELS = (
    "L1_DISCOVER_PROVENANCE",
    "L2_BUILD_PERMISSIONED_VERIFIED_SUPPLY",
    "L3_TEST_OWNED_OPT_IN_DISTRIBUTION",
    "L4_PROVE_PAID_MATCH_BEFORE_SOFTWARE",
)
# Deliberate minimums for a lean test, NOT results, forecasts or commitments.
TARGETS = {
    "independent_authorised_demand_sources": 2,
    "willing_verified_business_providers": 3,
    "real_opted_in_enquiries": 10,
    "buyer_accepted_appointments": 3,
    "independently_reconciled_paid_transactions": 1,
}
PHASES = (
    "RESEARCH_HOLD",
    "EVIDENCE_REVIEW",
    "SUPPLY_VERIFICATION_REQUIRED",
    "BUYER_TERMS_REQUIRED",
    "READY_FOR_FOUNDER_TEST_APPROVAL",
)


def _task(lane: str, order: int, action: str, acceptance: str,
          gate: str = "internal_research_only") -> dict[str, Any]:
    return {
        "id": f"{lane}:{order:02d}:{action}",
        "owner": OWNER,
        "action": action,
        "acceptance_criteria": acceptance,
        "gate": gate,
        "automated_external_execution": False,
    }


def run_agent(
    *,
    evidence_packet: Mapping[str, Any] | None = None,
    lanes: tuple[dict[str, str], ...] = DEFAULT_LANES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return executable *research tasks* and experiment scorecard, without I/O."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone_aware_now_required")
    if len(lanes) < 1 or len(lanes) > 5:
        raise ValueError("lane_count_out_of_range")
    if evidence_packet is None:
        evidence_packet = {"schema_version": EVIDENCE_SCHEMA, "observations": []}
    if not isinstance(evidence_packet, Mapping):
        raise ValueError("invalid_evidence_packet")

    # Fixtures must never be mistaken for production source evidence.
    synthetic = evidence_packet.get("synthetic") is True
    if synthetic:
        vetted = {"schema_version": EVIDENCE_SCHEMA, "observations": []}
    else:
        vetted = evidence_packet
    review = review_packet(vetted, now=now)
    matches = {(p["niche"], p["us_zip"]): p for p in review["market_hypotheses"]}
    evidence = review["evidence"]
    lane_ids: set[str] = set()
    lane_reports = []
    tasks = []
    for lane in lanes:
        if not isinstance(lane, Mapping):
            raise ValueError("lane_not_structured")
        lane_id = lane.get("id")
        niche = lane.get("niche")
        us_zip = lane.get("us_zip")
        city = lane.get("city")
        if not all(isinstance(value, str) and value.strip() for value in
                   (lane_id, niche, us_zip, city)):
            raise ValueError("invalid_lane")
        if lane_id in lane_ids or not lane_id.replace("_", "").isalnum():
            raise ValueError("duplicate_or_invalid_lane_id")
        if len(us_zip) != 5 or not us_zip.isdecimal():
            raise ValueError("invalid_lane_zip")
        lane_ids.add(lane_id)
        matching = [x for x in evidence if x["niche"] == niche and x["us_zip"] == us_zip]
        demand = [x for x in matching if x["kind"] == "aggregate_demand"]
        supply = [x for x in matching if x["kind"] == "business_supply"]
        independent_sources = len({x["source_url"] for x in demand})
        hypothesis = matches.get((niche, us_zip))
        # Marketplace IG listings and profiles are NOT provider willingness.
        verified_willing_providers = 0
        independently_reconciled_purchases = 0
        state = "EVIDENCE_REVIEW" if hypothesis else "RESEARCH_HOLD"
        lane_tasks = [
            _task(lane_id, 1, "VERIFY_MARKET_AND_PAYER_COVERAGE",
                  "Obtain authoritative buyer ZIP coverage, eligibility and target use case; do not imply coverage today."),
            _task(lane_id, 2, "OBTAIN_AUTHORISED_DEMAND_SIGNAL_SOURCES",
                  "Review permission and provenance for >=2 independent aggregate signals; exclude private posts and personal information."),
            _task(lane_id, 3, "VERIFY_PROVIDER_SUPPLY_AND_CONSENT",
                  "Independently verify >=3 providers' eligibility, capacity and willingness to participate; profiles alone do not count."),
            _task(lane_id, 4, "DOCUMENT_BUYER_PAYABLE_TERMS",
                  "Verify buying entity, appointment definition, cancellation/rejection rules, signed rates and payout evidence."),
            _task(lane_id, 5, "DRAFT_OWNED_LANDING_AND_ORGANIC_CONTENT_TEST",
                  "Prepare opt-in value proposition, transparent disclosure and measurement plan; no publishing without founder approval.",
                  "founder_approval_before_publication"),
            _task(lane_id, 6, "RUN_MINIMUM_VIABLE_MATCH_TEST",
                  "After explicit approval, measure genuine sessions, consented enquiries, verified appointments and reconciled payment.",
                  "founder_approval_before_live_test"),
        ]
        tasks.extend(lane_tasks)
        lane_reports.append({
            "lane_id": lane_id, "niche": niche, "city": city, "us_zip": us_zip,
            "city_and_zip_are_provisional_not_confirmed_buying_coverage": True,
            "phase": state, "hypothesis_present": hypothesis is not None,
            "independent_demand_sources_observed": independent_sources,
            "business_supply_evidence_observed": len(supply),
            "verified_willing_providers": verified_willing_providers,
            "verified_payers": 0,
            "verified_appointments": 0,
            "independently_reconciled_purchases": independently_reconciled_purchases,
            "commercial_experiment_authorized": False,
            "traffic_activation_authorized": False,
            "next_step": ("REQUEST_SOURCE_RIGHTS_AND_INDEPENDENT_EVIDENCE" if
                          independent_sources < TARGETS["independent_authorised_demand_sources"]
                          else "VERIFY_PROVIDER_WILLINGNESS_AND_PAYER_TERMS"),
            "evidence_ids": sorted(x["evidence_id"] for x in matching),
            "experiment_targets_not_results": dict(TARGETS),
            "agent_tasks": lane_tasks,
        })
    return {
        "schema_version": AGENT_SCHEMA, "agent": OWNER, "generated_at": now.isoformat(),
        "status": "SYNTHETIC_TEST_ONLY" if synthetic else (
            "EVIDENCE_CANDIDATES_FOUND" if review["market_hypotheses"]
            else "PENDING_REAL_AUTHORISED_EVIDENCE"),
        "mode": "OBSERVE", "implementation_stage": "isolated_research_candidate",
        "level_framework": list(LEVELS),
        "lanes": lane_reports, "research_task_count": len(tasks),
        "source_review": {
            "received": 0 if synthetic else review["observations_received"],
            "accepted": review["accepted_observations"],
            "held": review["held_counts"],
            "market_hypothesis_count": len(review["market_hypotheses"]),
        },
        "provenance": {
            "source": "pre_reviewed_offline_structured_packet",
            "third_party_content_collected": False,
            "current_source_rights_independently_audited": False,
        },
        "authority": {
            "meta_data_collection": False, "meta_scraping": False,
            "read_private_groups": False, "publish_or_send": False,
            "external_calls": False, "send_dm": False, "ad_spend": False,
            "database_writes": False, "crm_writes": False,
            "production_timers_started": False, "consumer_activation": False,
        },
        "next_action": "COMPLETE_PERMISSION_AND_BUYER_CAPACITY_GATES_BEFORE_REAL_PILOT",
    }
