from empire_os.mrr_product_recovery import (
    mrr_recovery_catalog,
    mrr_recovery_summary,
)


def test_mrr_recovery_restores_old_product_families_without_legacy_authority():
    rows = {row["key"]: row for row in mrr_recovery_catalog()}

    for key in (
        "platform_saas_tiers",
        "lane_seat_subscription_tiers",
        "empire_leads_engine",
        "hermes_framework",
        "opencut_studio",
        "empire_templates",
        "marketingskills",
        "satellite_idle_watch",
        "skillspector_audit",
        "synthetic_agent",
        "aeo_monitor",
        "agent_copilot",
        "white_label_platform",
        "affiliate_partner_program",
        "omega_evaluation_mrr",
        "intelligence_retainer",
    ):
        assert key in rows

    assert rows["synthetic_agent"]["disposition"] == "RETIRE"
    assert rows["aeo_monitor"]["disposition"] == "MERGE"
    assert rows["lane_seat_subscription_tiers"]["target_phase"] == "4"


def test_historical_prices_are_not_current_commercial_truth():
    rows = mrr_recovery_catalog()

    assert any(row["legacy_pricing_present"] for row in rows)
    assert all(
        row["legacy_pricing_approved_current"] is False
        for row in rows
    )


def test_mrr_recovery_uses_current_settlement_and_no_execution_authority():
    summary = mrr_recovery_summary()

    assert summary["product_count"] >= 15
    assert summary["canonical_settlement_rail"] == "USDT_BSC"
    assert summary["legacy_settlement_allowed"] is False
    assert summary["legacy_pricing_approved_current_count"] == 0
    assert summary["actual_revenue"] is False
    assert summary["execution_authority"] == "none"
