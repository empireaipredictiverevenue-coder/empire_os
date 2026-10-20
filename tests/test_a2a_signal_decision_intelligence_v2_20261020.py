"""V2 regression: deterministic research over fixtures, never production buyers."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.a2a_commercial_signal_miner import mine_signals
from empire_os.a2a_data_campaign_experiments import build_data_campaign_experiments
from empire_os.a2a_data_campaign_release_review import assess_campaign_readiness
from empire_os.a2a_nyc_commercial_evidence_gate import inspect_nyc_pilot
from empire_os.a2a_signal_decision_intelligence_v2 import make_decision_intelligence
from empire_os.a2a_opportunity_graph_v2 import make_opportunity_graph
from tests.test_a2a_commercial_signal_miner_20261020 import community, gps
from tests.test_a2a_nyc_commercial_evidence_gate_20261020 import inputs

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


def _catalogue(*, stale: bool = False):
    stamp = NOW - timedelta(days=3) if stale else NOW
    products = [
        {
            "product_id": name,
            "customer_data_export_ready": False,
            "raw_third_party_resale_cleared": False,
            "buyer_verified": False,
            "product_activation_enabled": False,
        }
        for name in ("nyc_permit_project_verification",
                     "founder_original_intelligence_reports")
    ]
    return {
        "schema_version": "empire.data_brokerage.internal_product_catalog.v1",
        "mode": "OBSERVE", "generated_at": stamp.isoformat(),
        "product_publication_authorized": False,
        "third_party_resale_authorized": False, "marketing_outbound_sent": False,
        "products": products,
    }


def _inputs(*, stale: bool = False):
    signals = mine_signals(community=community(), revenue_gps=gps(), now=NOW)
    campaigns = build_data_campaign_experiments(signals)
    nyc = inspect_nyc_pilot(**inputs())
    release = assess_campaign_readiness(campaigns, nyc)
    return signals, release, _catalogue(stale=stale)


def test_first_research_cycle_not_an_automatic_launch():
    current, release, catalogue = _inputs()
    intel = make_decision_intelligence(current, release, catalogue, now=NOW)
    assert intel["research_candidate_count"] == 4
    assert intel["new_candidate_count"] == 4
    assert intel["verified_new_buyers"] == 0
    assert intel["verified_revenue"] == 0
    assert not intel["outbound"] and not intel["publications"]
    assert intel["new_owner_task_proposals"] > 0
    assert intel["source_licence_approved"] is False
    assert all(not x["buyer_identity_verified"] for x in intel["research_priorities"])


def test_repeat_source_suppresses_owner_task_reissues():
    current, release, catalogue = _inputs()
    intel = make_decision_intelligence(
        current, release, catalogue, previous=deepcopy(current), now=NOW,
    )
    assert intel["new_candidate_count"] == 0
    assert intel["unchanged_research_candidate_count"] == 4
    assert intel["new_owner_task_proposals"] == 0
    assert intel["duplicate_owner_task_reissues_suppressed"] == intel["verification_task_count"]
    assert all(x["temporal_status"] == "UNCHANGED_RESEARCH_SIGNAL"
               for x in intel["research_priorities"])


def test_changed_evidence_reopens_only_the_changed_segment():
    current, release, catalogue = _inputs()
    previous = deepcopy(current)
    amended = deepcopy(current)
    amended["prioritized_research_signals"][0]["research_priority_score_not_probability"] += 1
    intel = make_decision_intelligence(amended, release, catalogue,
                                       previous=previous, now=NOW)
    assert intel["changed_or_new_candidate_count"] == 1
    assert intel["new_owner_task_proposals"] >= 2
    assert intel["unchanged_research_candidate_count"] == 3


def test_source_health_downgrades_discussion_priorities():
    current, release, catalogue = _inputs(stale=True)
    intel = make_decision_intelligence(current, release, catalogue, now=NOW)
    assert intel["catalogue_stale"] is True
    assert "linkedin" in intel["source_health"]["community_intent"]["latest_retrieval_degraded"]
    community_rows = [x for x in intel["research_priorities"] if x["source_class"] == "community_intent"]
    assert community_rows
    assert all(x["quality_adjusted_research_triage_not_probability"] <= 30
               for x in community_rows)
    assert all("NO_VERIFIED_GEO_FOR_MICROTARGETING" in x["reason_codes"]
               for x in community_rows)


def test_product_rights_never_inferred_from_catalogue_presence():
    current, release, catalogue = _inputs()
    intel = make_decision_intelligence(current, release, catalogue, now=NOW)
    nyc = next(x for x in intel["research_priorities"] if x["niche"] == "general_contractor")
    assert nyc["product_hypothesis"] == "nyc_permit_project_verification"
    assert nyc["prioritisation_score_not_probability"] == 80
    assert nyc["quality_adjusted_research_triage_not_probability"] <= 55
    assert "PRODUCT_RIGHTS_AND_DELIVERY_NOT_APPROVED" in nyc["reason_codes"]
    assert not nyc["campaign_ready"]


def test_rejected_promotion_of_financial_claim_or_campaign_authority():
    current, release, catalogue = _inputs()
    modified = deepcopy(current)
    modified["prioritized_research_signals"][0]["buyer_budget"] = 100000
    with pytest.raises(ValueError, match="FINANCIAL_CLAIM"):
        make_decision_intelligence(modified, release, catalogue, now=NOW)
    rejected = deepcopy(release)
    rejected["launch_ready_campaign_count"] = 1
    with pytest.raises(ValueError, match="RELEASE_PACKET"):
        make_decision_intelligence(current, rejected, catalogue, now=NOW)


def test_source_revocation_and_forged_outcomes_rejected():
    current, release, catalogue = _inputs()
    bad = deepcopy(catalogue)
    bad["products"][0]["raw_third_party_resale_cleared"] = True
    with pytest.raises(ValueError, match="CATALOGUE_CLAIM"):
        make_decision_intelligence(current, release, bad, now=NOW)
    bad_signals = deepcopy(current)
    bad_signals["verified_buyers_discovered"] = 2
    with pytest.raises(ValueError, match="MINER_REPORT"):
        make_decision_intelligence(bad_signals, release, catalogue, now=NOW)


def test_previous_missing_segment_does_not_mean_market_disappeared():
    current, release, catalogue = _inputs()
    old = deepcopy(current)
    current = deepcopy(current)
    current["prioritized_research_signals"] = current["prioritized_research_signals"][:1]
    intel = make_decision_intelligence(current, release, catalogue, previous=old, now=NOW)
    assert len(intel["previous_candidates_not_in_latest"]) == 3
    assert intel["previous_absence_proves_market_disappeared"] is False


def test_evidence_graph_protects_independence_and_excludes_people():
    current, release, catalogue = _inputs()
    intel = make_decision_intelligence(current, release, catalogue, now=NOW)
    graph = make_opportunity_graph(intel, release)
    assert graph["node_count"] > 4
    assert graph["edge_count"] > 5
    assert graph["source_family_count"] == 2
    assert graph["source_independence"]["source_rows_not_independent_commercial_confirmations"]
    assert graph["personal_identity_nodes"] == 0
    assert graph["buyers_verified_through_graph"] == 0
    assert graph["calibrated_purchase_probability"] is None
    assert graph["automatic_learning_from_unverified_outcomes"] is False


def test_graph_rejects_new_privilege_claims():
    current, release, catalogue = _inputs()
    intel = make_decision_intelligence(current, release, catalogue, now=NOW)
    fake = deepcopy(intel)
    fake["publications"] = True
    with pytest.raises(ValueError, match="DECISION_PACKET"):
        make_opportunity_graph(fake, release)
    fake = deepcopy(release)
    fake["launch_ready_campaign_count"] = 1
    with pytest.raises(ValueError, match="RELEASE_PACKET"):
        make_opportunity_graph(intel, fake)


def test_requires_aware_now_and_monotonic_history():
    current, release, catalogue = _inputs()
    with pytest.raises(ValueError, match="CLOCK"):
        make_decision_intelligence(current, release, catalogue,
                                   now=datetime(2026, 10, 20, 10))
    prev = deepcopy(current)
    prev["generated_at"] = (NOW + timedelta(minutes=2)).isoformat()
    with pytest.raises(ValueError, match="REVERSAL"):
        make_decision_intelligence(current, release, catalogue,
                                   previous=prev, now=NOW + timedelta(minutes=3))
