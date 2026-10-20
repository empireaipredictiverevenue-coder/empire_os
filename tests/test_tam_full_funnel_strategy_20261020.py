"""TAM-to-customer full-funnel strategy regression without live outreach."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from scripts.review_tam_full_funnel_strategy_20261020 import (
    SOURCES, read_existing_snapshots, review_full_funnel_strategy,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def fixture():
    iso = NOW.isoformat()
    return {
        "tam": {
            "schema_version": SOURCES["tam"][1], "generated_at": iso,
            "observed_unique_entity_count": 8,
            "source_population_complete": False, "tenant_source_scope_verified": False,
            "tam_inferred_from_observed_roster": False,
        },
        "optimizer": {
            "schema_version": SOURCES["optimizer"][1], "generated_at": iso,
            "learning_state": "LEARNING", "outbound_mutation": False,
            "labelled_intent_count": 4, "winner_claim_allowed": False,
        },
        "campaigns": {
            "schema_version": SOURCES["campaigns"][1], "generated_at": iso,
            "campaign_count": 5, "status": "VERIFIED_RUNTIME",
        },
        "outcomes": {
            "schema_version": SOURCES["outcomes"][1], "generated_at": iso,
            "outcome_linkage_proved": False, "exact_outcome_match_count": 0,
        },
        "assets": {
            "schema_version": SOURCES["assets"][1], "deployment_verified": True,
            "campaign_ids": ["campaign_" + str(i) * 24 for i in range(1, 6)],
        },
    }


def test_complete_operating_model_includes_every_video_phase():
    result = review_full_funnel_strategy(fixture(), now=NOW)
    assert result["qualified_market"]["sampled_entities_observed"] == 8
    assert result["qualified_market"]["complete_market_size"] is None
    assert result["campaign_assets"]["deployed_assets_correlated_to_runtime"] == 5
    assert result["verified_commercial_feedback"]["exact_campaign_outcome_matches"] == 0
    assert result["verified_commercial_feedback"]["attributed_recognised_revenue"] is None
    assert result["existing_outreach_learning"]["labelled_intent_examples"] == 4
    assert [x["stage"] for x in result["workflow_handoff"]] == [
        "market", "offer", "creative", "delivery",
        "signals", "response", "retargeting", "revenue",
    ]
    assert result["experiment"]["holdout_fraction"] == 0.1
    assert len(result["experiment"]["variants"]) == 4
    assert len(result["measurement_funnel"]) == 9
    assert result["frequency_policy"]["repeat_wave_window_days"] == [30, 60]
    assert all(stage["verified_value"] is None for stage in result["measurement_funnel"])
    for key in ("external_messages_sent", "database_writes",
                "tracking_or_websites_changed", "production_workflows_activated",
                "paid_media_budget_committed"):
        assert result[key] is False


def test_stale_tam_cannot_be_taken_as_verified_full_market():
    data = fixture()
    data["tam"]["source_population_complete"] = True
    data["tam"]["tenant_source_scope_verified"] = True
    data["tam"]["generated_at"] = (NOW - timedelta(days=10)).isoformat()
    result = review_full_funnel_strategy(data, now=NOW)
    assert result["qualified_market"]["complete_addressable_market_verified"] is False
    assert result["qualified_market"]["complete_market_size"] is None
    assert "COMPLETE_VERIFIED_QUALIFIED_TAM_NOT_AVAILABLE" in result["launch_blockers"]


def test_wrong_schema_cannot_count_as_campaign_proof():
    data = fixture()
    data["campaigns"]["schema_version"] = "wrong"
    result = review_full_funnel_strategy(data, now=NOW)
    assert result["campaign_assets"]["existing_campaigns_runtime_verified"] is None
    assert result["campaign_assets"]["deployed_assets_correlated_to_runtime"] is None


def test_unmatched_or_unverified_assets_not_claimed_deployed():
    data = fixture()
    data["assets"]["campaign_ids"].pop()
    assert review_full_funnel_strategy(data, now=NOW)["campaign_assets"]["deployed_assets_correlated_to_runtime"] is None
    data = fixture()
    data["assets"]["deployment_verified"] = False
    assert review_full_funnel_strategy(data, now=NOW)["campaign_assets"]["deployed_assets_correlated_to_runtime"] is None


def test_outcome_claim_requires_exact_matches_and_resolved_source():
    data = fixture()
    data["outcomes"]["outcome_linkage_proved"] = True
    res = review_full_funnel_strategy(data, now=NOW)
    assert res["verified_commercial_feedback"]["outcome_linkage_verified"] is False
    data["outcomes"]["exact_outcome_match_count"] = 2
    res = review_full_funnel_strategy(data, now=NOW)
    assert res["verified_commercial_feedback"]["outcome_linkage_verified"] is True
    # Even exact matching outcomes does not imply paying customer or real money.
    assert res["verified_commercial_feedback"]["paid_customer_winning_variant"] is None
    assert res["verified_commercial_feedback"]["attributed_recognised_revenue"] is None


def test_unsafe_files_ignored(tmp_path):
    fixture_data = fixture()
    for k, (path, _) in SOURCES.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(fixture_data[k]))
    data = read_existing_snapshots(tmp_path)
    assert len(data) == 5
    assert data["tam"]["observed_unique_entity_count"] == 8
    p = tmp_path / SOURCES["tam"][0]
    p.unlink()
    p.symlink_to(tmp_path / SOURCES["optimizer"][0])
    assert read_existing_snapshots(tmp_path)["tam"] == {}


def test_invalid_timestamps_and_boolean_metrics_do_not_become_counts():
    data = fixture()
    data["campaigns"]["campaign_count"] = True
    data["outcomes"]["exact_outcome_match_count"] = True
    data["tam"]["generated_at"] = "not-a-date"
    out = review_full_funnel_strategy(data, now=NOW)
    assert out["campaign_assets"]["existing_campaigns_runtime_verified"] is None
    assert out["verified_commercial_feedback"]["exact_campaign_outcome_matches"] is None
    assert out["qualified_market"]["observation_fresh"] is False


def test_no_personal_data_can_be_transformed_to_output():
    data = fixture()
    data["tam"]["some_private_email"] = "prospect@example.test"
    data["assets"]["recipient_id"] = "john-doe-secret"
    dumped = json.dumps(review_full_funnel_strategy(data, now=NOW))
    assert "prospect@" not in dumped
    assert "john-doe-secret" not in dumped


from scripts.review_tam_full_funnel_strategy_20261020 import (
    plan_compliant_market_touch, triage_same_day_signal,
    review_paid_customer_winners,
)


def contact(**changes):
    params = {
        "contact_lookup_key": "f" * 32,
        "market_scope_verified": True,
        "lawful_outreach_verified": True,
        "suppressed": False,
        "sending_domain_approved": True,
        "last_touch_verified": True,
        "last_touch_at": None,
        "now": NOW,
    }
    params.update(changes)
    return plan_compliant_market_touch(**params)


def test_real_wave_planner_reuses_existing_experiment_and_does_not_send():
    a = contact()
    b = contact()
    assert a == b
    assert a["status"] == "PLAN_ONLY_FOUNDATION_CHECKS_PASSED"
    assert a["planned_arm"] in {
        "no_marketing_holdout", "buyer_inventory_fit_offer",
        "revenue_leak_signal_offer", "verified_market_opportunity_brief",
    }
    assert a["sent"] is False
    assert a["automatic_activation"] is False
    assert "f" * 32 not in json.dumps(a)


def test_30_day_cooldown_and_cross_campaign_history_enforced():
    assert "MARKET_WAVE_30_DAY_COOLDOWN" in contact(
        last_touch_at=NOW - timedelta(days=29))["blockers"]
    assert contact(last_touch_at=NOW - timedelta(days=30))["status"].startswith("PLAN_ONLY")
    assert "CROSS_CAMPAIGN_CONTACT_HISTORY_UNVERIFIED" in contact(
        last_touch_verified=False)["blockers"]


def test_permission_suppression_sender_and_tam_gate_every_recipient():
    for key, value in (
        ("suppressed", True), ("lawful_outreach_verified", False),
        ("market_scope_verified", False), ("sending_domain_approved", False),
    ):
        result = contact(**{key: value})
        assert result["status"] == "HOLD"
        assert result["planned_arm"] is None
        assert result["sent"] is False


def test_only_opaque_contact_keys_allowed():
    import pytest
    for key in ("person@example.com", "1", "", "0" * 12):
        with pytest.raises(ValueError):
            contact(contact_lookup_key=key)


def test_event_click_cannot_trigger_outreach_or_retargeting():
    for kind in (
        "email_click", "consented_site_visit", "server_accepted_enquiry",
        "booked_meeting", "settled_revenue",
    ):
        result = triage_same_day_signal(
            kind=kind, independent_provenance_verified=True,
            lawful_contact_permission_verified=True, suppression_clear=True,
        )
        assert result["outbound_dispatched"] is False
        assert result["retargeting_authorized"] is False
        if kind == "email_click":
            assert result["action"] == "weak_interest_research_review"
        if kind in ("booked_meeting", "server_accepted_enquiry"):
            assert result["action"] == "same_business_day_sales_review"
    assert triage_same_day_signal(
        kind="server_accepted_enquiry", independent_provenance_verified=True,
        lawful_contact_permission_verified=False, suppression_clear=True,
    )["action"] == "INTERNAL_REVIEW_NO_OUTREACH"


def test_paid_customers_are_primary_and_no_cash_proof_is_fabricated():
    arms = {
        "variant_a": {"eligible_delivered": 100, "paid_customers": 4},
        "variant_b": {"eligible_delivered": 100, "paid_customers": 2},
    }
    not_ready = review_paid_customer_winners(arms, outcome_receipts_verified=False)
    assert not_ready["winner"] is None
    observed = review_paid_customer_winners(arms, outcome_receipts_verified=True)
    assert observed["winner"] == "variant_a"
    assert observed["status"] == "DESCRIPTIVE_WINNER_FOR_HUMAN_REVIEW"
    assert observed["automatic_scaling"] is False
    zero = {k: {"eligible_delivered": 100, "paid_customers": 0} for k in arms}
    assert review_paid_customer_winners(zero, outcome_receipts_verified=True)["winner"] is None


def test_winner_rejects_unsafe_low_sample_or_impossible_claims():
    import pytest
    bad = {
        "variant_a": {"eligible_delivered": 5, "paid_customers": 1},
        "variant_b": {"eligible_delivered": 100, "paid_customers": 99},
    }
    with pytest.raises(ValueError):
        review_paid_customer_winners(bad, outcome_receipts_verified=True)
    bad["variant_a"] = {"eligible_delivered": 100, "paid_customers": 101}
    with pytest.raises(ValueError):
        review_paid_customer_winners(bad, outcome_receipts_verified=True)
