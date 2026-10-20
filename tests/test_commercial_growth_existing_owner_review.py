"""Contract tests: no Buyer Scout or Sales Director work is duplicated."""
from copy import deepcopy

import pytest

from empire_os.commercial_growth_existing_owner_review import (
    review_existing_owner_handoff,
)
from empire_os.video_commercial_growth_framework import (
    build_commercial_growth_review,
)


def commercial(*, stale=True):
    return build_commercial_growth_review(
        observations={"observations": []},
        offer_book={
            "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
            "generated_at": ("2026-09-30T00:00:00Z" if stale else "2026-10-20T07:00:00Z"),
            "targets": [
                {
                    "company": "Example Co",
                    "canonical_prospect_id": None,
                    "state": "PRODUCT_READINESS_REQUIRED",
                    "person_verified": False,
                    "email_verified": False,
                    "demand_state": "UNKNOWN",
                    "buyer_demand_verified": False,
                    "contact_mode": "EXISTING_THREAD_REVIEW",
                    "offer_package_ready": False,
                }
            ],
        },
        funnel={
            "schema_version": "empire.founder_commercial_funnel.v1",
            "generated_at": ("2026-09-22T00:00:00Z" if stale else "2026-10-20T07:00:00Z"),
        },
        now=__import__("datetime").datetime(
            2026, 10, 20, 8, tzinfo=__import__("datetime").timezone.utc
        ),
    )


def bd(activated=0, *, status="BUSINESS_DEVELOPMENT_RESEARCH_TRIAGE_READY"):
    return {
        "schema_version": "empire.bd.conversion_desk_review.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "status": status,
        "outbound_allowed": False,
        "database_writes": False,
        "hold_code": "STALE_SCOUT_SNAPSHOT" if status == "SOURCE_EVIDENCE_HOLD" else None,
        "scout_candidate_count": 6,
        "review_ready_count": 0,
        "fully_activated_buyer_count": activated,
        "buyer_market_match_verified": False,
        "priority_actions": [
            {
                "owner": "buyer_scout",
                "action": "REVIEW_FIRST_PARTY_DIRECT_BUYER_CLAIM_SOURCES",
                "reason": "site_evidence_below_floor",
                "evidence_count": 6,
            }
        ],
    }


def test_separate_cohorts_and_owner_holds():
    report = review_existing_owner_handoff(commercial=commercial(), buyer_development=bd())
    assert report["status"] == "SOURCE_REVIEW_HOLD"
    assert report["historical_offer_book_cohort"]["historical_offer_target_count"] == 1
    assert report["existing_buyer_development_cohort"]["scout_candidate_count"] == 6
    assert report["existing_buyer_development_cohort"]["fully_activated_buyer_count"] == 0
    assert report["cohorts_are_separate_and_not_summable"] is True
    assert report["buyer_identity_join_performed"] is False
    assert report["agent_tasks_created"] is False
    assert report["crm_mutations"] is False
    assert report["outbound_allowed"] is False


def test_workstream_routes_stay_suggestions_not_executed_tasks():
    report = review_existing_owner_handoff(commercial=commercial(), buyer_development=bd())
    suggested = report["existing_owner_review_suggestions"]
    owners = [row["existing_owner_lane"] for row in suggested]
    assert "commercial_source_owners" in owners
    assert "commercial_evidence_verifier" in owners
    assert "decision_maker_resolver" in owners
    assert "commercial_catalog_owner" in owners
    assert "sales_director_operator" in owners
    assert report["existing_bd_owner_priority_actions"][0]["owner_from_existing_bd_desk"] == "buyer_scout"
    assert report["existing_bd_owner_priority_actions"][0]["task_created"] is False


def test_fresh_sources_and_activated_buyer_still_no_execution_authority():
    report = review_existing_owner_handoff(commercial=commercial(stale=False), buyer_development=bd(activated=1))
    assert report["status"] == "OWNER_REVIEW_ONLY"
    assert report["external_actions"] is False
    assert report["database_writes"] is False
    assert report["payment_authorized"] is False


def test_bd_source_hold_refuses_to_treat_old_counts_as_current():
    report = review_existing_owner_handoff(commercial=commercial(stale=False), buyer_development=bd(20, status="SOURCE_EVIDENCE_HOLD"))
    assert report["status"] == "SOURCE_REVIEW_HOLD"
    assert report["existing_buyer_development_cohort"]["fully_activated_buyer_count"] is None
    assert report["existing_buyer_development_cohort"]["review_ready_count"] is None
    assert report["existing_bd_owner_priority_actions"] == []
    assert "buyer_acquisition_team" in [x["existing_owner_lane"] for x in report["existing_owner_review_suggestions"]]


@pytest.mark.parametrize("field,value", [
    ("schema_version", "unknown"),
    ("execution_authority", "write"),
    ("outbound_allowed", True),
    ("database_writes", True),
    ("status", "AUTO_APPROVED"),
])
def test_bd_execution_or_schema_escalation_rejected(field, value):
    packet = bd()
    packet[field] = value
    with pytest.raises(ValueError):
        review_existing_owner_handoff(commercial=commercial(), buyer_development=packet)


def test_growth_schema_execution_escalation_rejected():
    current = commercial()
    current["outbound_authority"] = "automatic"
    with pytest.raises(ValueError):
        review_existing_owner_handoff(commercial=current, buyer_development=bd())


def test_bad_overlap_count_rejected_not_pushed_to_agent():
    current = commercial()
    current["readiness_gap_counts_nonexclusive"]["CANONICAL_ID_MISSING"] = 2
    with pytest.raises(ValueError, match="overlapping gap"):
        review_existing_owner_handoff(commercial=current, buyer_development=bd())


def test_unlisted_bd_owner_is_not_dispatched_or_exported():
    packet = bd()
    packet["priority_actions"][0]["owner"] = "fictional_autonomous_seller"
    report = review_existing_owner_handoff(commercial=commercial(), buyer_development=packet)
    assert report["existing_bd_owner_priority_actions"] == []
    assert report["agent_tasks_created"] is False


def test_commmercial_gap_codes_count_are_nonexclusive_and_no_contact_leak():
    packet = commercial()
    gaps = packet["readiness_gap_counts_nonexclusive"]
    assert gaps["CANONICAL_ID_MISSING"] == 1
    assert gaps["PRODUCT_TERMS_OR_CATALOG_UNREADY"] == 1
    assert gaps["PERSON_CONTACT_EVIDENCE_UNVERIFIED"] == 1
    assert gaps["BUYER_DEMAND_NOT_VERIFIED"] == 1
    assert gaps["EXISTING_CONVERSATION_REQUIRES_LIVE_THREAD_RECHECK"] == 1
    assert packet["readiness_counts_are_overlapping"] is True
