import pytest

from empire_os.demand_genesis import DemandPlan


def test_demand_plan_is_planning_only():
    plan = DemandPlan(
        plan_id="plan-1",
        channel="aeo",
        objective="Increase qualified discovery for roofing buyers.",
        audience="UK roofing contractors",
        evidence_refs=("search-gap:roofing-london",),
        success_metric="qualified_inbound_conversations",
    )
    payload = plan.as_dict()
    assert payload["execution_authority"] == "none"
    assert payload["approval_required"] is True


def test_demand_plan_requires_evidence():
    plan = DemandPlan(
        plan_id="plan-1",
        channel="content",
        objective="Create demand",
        audience="buyers",
        evidence_refs=(),
        success_metric="qualified_inbound_conversations",
    )
    with pytest.raises(ValueError, match="requires evidence"):
        plan.validate()


def test_unknown_channel_is_rejected():
    plan = DemandPlan(
        plan_id="plan-1",
        channel="carrier_pigeon",
        objective="Create demand",
        audience="buyers",
        evidence_refs=("evidence-1",),
        success_metric="qualified_inbound_conversations",
    )
    with pytest.raises(ValueError, match="unsupported demand channel"):
        plan.validate()


def test_execution_authority_cannot_be_enabled():
    plan = DemandPlan(
        plan_id="plan-1",
        channel="partnership",
        objective="Partner distribution",
        audience="agencies",
        evidence_refs=("partner-gap-1",),
        success_metric="qualified_partner_referrals",
        execution_authority="publish",
    )
    with pytest.raises(ValueError, match="cannot grant execution authority"):
        plan.validate()
