from empire_os.commercial_marketing_registry import (
    MARKETING_PLANS,
    VALID_STATES,
    marketing_plan_catalog,
    marketing_summary,
)


def test_marketing_registry_is_read_only_and_governed():
    assert all(plan.state in VALID_STATES for plan in MARKETING_PLANS)
    assert all(plan.execution_authority == "none" for plan in MARKETING_PLANS)
    assert all(plan.outbound_authority is False for plan in MARKETING_PLANS)
    assert all(plan.publishing_authority is False for plan in MARKETING_PLANS)
    assert all(plan.paid_spend_authority is False for plan in MARKETING_PLANS)

    summary = marketing_summary()
    assert summary["execution_authority"] == "none"
    assert summary["actual_revenue"] is False


def test_core_marketing_plans_are_preserved():
    rows = {row["key"]: row for row in marketing_plan_catalog()}
    assert rows["permit_opportunity_gtm"]["state"] == "ACTIVE_BUILD"
    assert rows["property_portfolio_gtm"]["state"] == "ACTIVE_BUILD"
    assert rows["private_capital_abm"]["state"] == "ACTIVE_BUILD"
    assert rows["storm_home_services_gtm"]["state"] == "ACTIVE_BUILD"
    assert rows["roofing_founding_partner_salvage"]["state"] == "SALVAGE_CANDIDATE"
    assert rows["oil_gas_research_gtm"]["state"] == "INCUBATE"
    assert rows["oil_gas_research_gtm"]["channels"] == ("research_only",)
