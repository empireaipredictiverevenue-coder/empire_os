"""Tests for targeting and A2A handoff, no calls or side effects."""
from copy import deepcopy

import pytest

from empire_os.a2a_data_campaign_experiments import build_data_campaign_experiments
from empire_os.a2a_data_opportunity_workflow import plan_handoffs
from tests.test_a2a_commercial_signal_miner_20261020 import review


def test_campaigns_laser_target_industries_not_personal_profiles():
    campaigns = build_data_campaign_experiments(review())
    assert campaigns["campaign_count"] == 2
    nyc = campaigns["campaigns"][0]
    assert nyc["segment"]["metro"] == "nyc"
    assert "preconstruction director" in nyc["segment"]["role_titles_not_personal_identities"]
    assert nyc["product_proposal"]["product_id"] == "nyc_permit_project_verification"
    assert "request" in nyc["creative_a_draft"]["cta"].lower()
    assert not nyc["product_proposal"]["data_licence_and_resale_cleared"]
    assert all(not c["publishing_authorised"] for c in campaigns["campaigns"])
    assert all(c["experiment_plan"]["observed_results"] is None for c in campaigns["campaigns"])


def test_graph_contains_8_gated_steps_not_8_executed_tasks():
    campaigns = build_data_campaign_experiments(review())
    handoff = plan_handoffs(campaigns)
    assert handoff["handoff_plan_count"] == campaigns["campaign_count"]
    assert handoff["handoff_step_count"] == 8 * campaigns["campaign_count"]
    assert handoff["plans"][0]["handoffs"][0]["capability"] == "rights_review"
    assert handoff["plans"][0]["handoffs"][-1]["capability"] == "reconciliation"
    assert all(not step["dispatch_authorised"]
               for p in handoff["plans"] for step in p["handoffs"])
    assert handoff["payment_links_issued"] == 0
    assert handoff["payments_executed"] == 0


def test_rejects_privilege_escalation_and_spoofed_campaign_packet():
    result = build_data_campaign_experiments(review())
    result["campaigns"][0]["publishing_authorised"] = True
    with pytest.raises(ValueError, match="exceeds"):
        plan_handoffs(result)
    result["campaigns"][0]["publishing_authorised"] = False
    result["agent_id"] = "other.agent"
    with pytest.raises(ValueError, match="untrusted"):
        plan_handoffs(result)


def test_input_immutability_and_bounded_campaign_count():
    report = review()
    original = deepcopy(report)
    campaigns = build_data_campaign_experiments(report, max_campaigns=1)
    assert report == original
    assert campaigns["campaign_count"] == 1
    with pytest.raises(ValueError):
        build_data_campaign_experiments(report, max_campaigns=0)


def test_forged_finance_execution_is_rejected():
    campaigns = build_data_campaign_experiments(review())
    campaigns["campaigns"][0]["payment_created"] = True
    with pytest.raises(ValueError):
        plan_handoffs(campaigns)
