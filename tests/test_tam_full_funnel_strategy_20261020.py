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
    assert "MARKET_WIDE_COVERAGE_UNVERIFIED_SCOPED_PILOT_ONLY" in result["launch_blockers"]


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

from dataclasses import replace
from scripts.review_tam_full_funnel_strategy_20261020 import (
    RecipientWaveEvidence, assemble_verified_cohort_wave,
    read_existing_buyer_sources, review_current_buyer_contactability,
    BUYER_SOURCE_PATHS,
)


def _canonical_recipient(**changes):
    record = RecipientWaveEvidence(
        contact_lookup_key="a" * 32, company_lookup_key="b" * 32,
        tenant_ref="tenant_empireai", market_scope="GB:solar:buyers",
        last_verified_at=NOW, last_marketing_touch_at=None,
        source_authority_verified=True,
        channel_lawfulness_verified=True, suppression_clear=True,
        contact_history_verified=True,
        sending_domain_approved=True, offer_evidence_verified=True,
    )
    return replace(record, **changes)


def _cohort(keys=None, resolver=None, **kw):
    value = _canonical_recipient()
    return assemble_verified_cohort_wave(
        ["a" * 32] if keys is None else keys,
        trusted_resolver=(lambda _: value) if resolver is None else resolver,
        tenant_ref=kw.get("tenant_ref", "tenant_empireai"),
        market_scope=kw.get("market_scope", "GB:solar:buyers"),
        now=NOW,
    )


def test_one_valid_segment_can_be_planned_without_claiming_tam_complete():
    report = _cohort()
    assert report["status"] == "OFFLINE_SEGMENTED_WAVE_PLAN_NOT_SENT"
    assert report["counts"]["eligible_for_review"] == 1
    assert report["counts"]["held_for_review"] == 0
    assert report["verified_entire_tam"] is False
    assert sum(report["counts"][name] for name in (
        "no_marketing_holdout", "buyer_inventory_fit_offer",
        "revenue_leak_signal_offer", "verified_market_opportunity_brief")) == 1
    for key in ("recipient_list_exported", "auto_email_sending_enabled",
                "retargeting_audience_exported", "source_owner_execution_approval_granted"):
        assert report[key] is False
    dumped = json.dumps(report)
    for secret in ("a" * 32, "b" * 32, "tenant_empireai", "person@example.com"):
        assert secret not in dumped


def test_duplicate_contact_is_idempotently_discarded_before_assignment():
    report = _cohort(keys=["a" * 32] * 3)
    assert report["counts"]["source_contacts_checked"] == 1
    assert report["counts"]["duplicate_lookup_keys_skipped"] == 2
    assert report["counts"]["eligible_for_review"] == 1


def test_two_contacts_same_company_get_identical_offer_arm():
    one = _canonical_recipient()
    two = replace(one, contact_lookup_key="c" * 32)
    report = _cohort(keys=[one.contact_lookup_key, two.contact_lookup_key],
                     resolver=lambda key: {one.contact_lookup_key: one,
                                           two.contact_lookup_key: two}[key])
    arms = {k: v for k, v in report["counts"].items() if k in {
        "no_marketing_holdout", "buyer_inventory_fit_offer",
        "revenue_leak_signal_offer", "verified_market_opportunity_brief",
    }}
    assert sorted(arms.values()) == [0, 0, 0, 1]
    assert report["counts"]["eligible_for_review"] == 1
    assert report["hold_reasons"]["SECOND_CONTACT_SAME_COMPANY_WAVE"] == 1


def test_unknown_permissions_and_suppression_always_hold():
    for prop, val in (
        ("channel_lawfulness_verified", False),
        ("suppression_clear", False),
        ("contact_history_verified", False),
        ("sending_domain_approved", False),
        ("offer_evidence_verified", False),
        ("source_authority_verified", False),
    ):
        row = _canonical_recipient(**{prop: val})
        result = _cohort(resolver=lambda _: row)
        assert result["counts"]["eligible_for_review"] == 0, prop
        assert result["counts"]["held_for_review"] == 1, prop


def test_tenant_market_and_lookup_mismatch_hold():
    for change in (
        {"tenant_ref": "tenant_otherx"},
        {"market_scope": "US:roofing:buyers"},
        {"contact_lookup_key": "f" * 32},
        {"company_lookup_key": "zero"},
    ):
        row = _canonical_recipient(**change)
        report = _cohort(resolver=lambda _: row)
        assert report["counts"]["held_for_review"] == 1
        assert "TENANT_MARKET_OR_IDENTITY_MISMATCH" in report["hold_reasons"]


def test_stale_future_dates_and_30_day_cooldown_rejected():
    for updates in (
        {"last_verified_at": NOW - timedelta(days=4)},
        {"last_verified_at": NOW + timedelta(hours=1)},
        {"last_marketing_touch_at": NOW - timedelta(days=12)},
    ):
        report = _cohort(resolver=lambda _: _canonical_recipient(**updates))
        assert report["counts"]["held_for_review"] == 1
        assert report["counts"]["eligible_for_review"] == 0


def test_unreadable_resolver_errors_never_leak_crm_secret():
    def resolver(_):
        raise ValueError("secret person@example.com")
    report = _cohort(resolver=resolver)
    assert report["hold_reasons"] == {"CANONICAL_CRM_RECORD_UNAVAILABLE": 1}
    assert "person@example.com" not in json.dumps(report)


def test_unsafe_contact_lookup_and_empty_cohort_rejected():
    import pytest
    for keys in (["person@example.com"], [], ["0" * 32], ["A" * 32],
                 ["a" * 32] * 501):
        with pytest.raises(ValueError):
            _cohort(keys=keys)


def _buyer_sources():
    return {
        "buyer_qualification": {
            "schema_version": BUYER_SOURCE_PATHS["buyer_qualification"][1],
            "generated_at": NOW.isoformat(), "mode": "OBSERVE",
            "execution_authority": "none", "outbound_enabled": False,
            "outbound_sent": False, "contact_verified_for_outbound_count": 0,
            "targets": [{"outbound_authorized": False} for _ in range(23)],
        },
        "relationships": {
            "schema_version": BUYER_SOURCE_PATHS["relationships"][1],
            "generated_at": NOW.isoformat(), "mode": "OBSERVE",
            "execution_authority": "NONE", "outbound_authorized": False,
            "outbound_sent": False,
            "relationships": [{"auto_send_authorized": False} for _ in range(261)],
        },
    }


def test_buyer_evidence_maps_real_qualified_targets_not_send_list():
    result = review_current_buyer_contactability(_buyer_sources(), now=NOW)
    assert result["source_status"] == "VERIFIED_READONLY_BUYER_SNAPSHOTS"
    assert result["shortlisted_buyer_targets"] == 23
    assert result["research_target_sectors"] == {"roofing": 0, "solar": 0, "hvac": 0}
    assert result["research_geography_and_live_buying_role_verified"] is False
    assert result["reviewed_relationships"] == 261
    assert result["buyer_contact_verified_count"] == 0
    assert result["permitted_email_recipients"] is None
    assert result["qualifying_contacts_for_wave"] is None
    assert result["existing_auto_send_authority"] is False
    assert "person@example.com" not in json.dumps(result)


def test_missing_stale_or_untrusted_buyer_source_denied():
    for mutated in (
        lambda d: d["relationships"].__setitem__("generated_at", "2020-01-01T00:00:00Z"),
        lambda d: d["relationships"].__setitem__("outbound_authorized", True),
        lambda d: d["buyer_qualification"].__setitem__("mode", "LIVE"),
    ):
        data = _buyer_sources()
        mutated(data)
        assert review_current_buyer_contactability(data, now=NOW)["shortlisted_buyer_targets"] is None


def test_owner_private_file_reader_rejects_symlinks_and_nonprivate_files(tmp_path):
    data = _buyer_sources()
    for key, (path, _) in BUYER_SOURCE_PATHS.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data[key]))
        file.chmod(0o600)
    assert set(read_existing_buyer_sources(tmp_path)) == set(BUYER_SOURCE_PATHS)
    assert review_current_buyer_contactability(
        read_existing_buyer_sources(tmp_path), now=NOW,
    )["buyer_contact_verified_count"] == 0
    qualification_path = tmp_path / BUYER_SOURCE_PATHS["buyer_qualification"][0]
    qualification_path.chmod(0o644)
    assert read_existing_buyer_sources(tmp_path)["buyer_qualification"] == {}
    qualification_path.unlink()
    qualification_path.symlink_to(tmp_path / BUYER_SOURCE_PATHS["relationships"][0])
    assert read_existing_buyer_sources(tmp_path)["buyer_qualification"] == {}

from scripts.review_tam_full_funnel_strategy_20261020 import review_three_offer_creatives


def test_actual_three_offer_copy_uses_existing_quality_gate_and_is_not_sent():
    result = review_three_offer_creatives(market_scope="GB:solar:buyers")
    assert len(result["drafts"]) == 3
    assert {draft["arm"] for draft in result["drafts"]} == {
        "buyer_inventory_fit_offer", "revenue_leak_signal_offer",
        "verified_market_opportunity_brief",
    }
    assert result["copy_sent"] is False
    assert result["offer_truth_independently_verified"] is False
    assert all(d["existing_copy_hard_gate_passed"] is True for d in result["drafts"])
    assert all(d["send_authorized"] is False and d["experiment_eligible"] is False
               for d in result["drafts"])
    assert all(d["existing_copy_quality_score"] >= 70 for d in result["drafts"])


def test_offer_reference_and_market_scope_validation_cannot_bypass_send_authority():
    import pytest
    with pytest.raises(ValueError):
        review_three_offer_creatives(market_scope="random")
    with pytest.raises(ValueError):
        review_three_offer_creatives(market_scope="GB:solar:buyers",
                                     verified_offer_evidence_refs=("person@example.com",))
    result = review_three_offer_creatives(
        market_scope="US:roofing:buyers",
        verified_offer_evidence_refs=("canonical:offers:evidence_001",),
        live_offer_and_landing_verified=True,
    )
    assert result["offer_evidence_references_supplied"] == 1
    assert result["offer_truth_independently_verified"] is False
    assert result["copy_sent"] is False
    assert all(x["send_authorized"] is False for x in result["drafts"])

def test_buyer_sector_research_counts_do_not_misstate_research_as_tam_or_sendability():
    sample = _buyer_sources()
    sample["buyer_qualification"]["targets"] = [
        {"verticals": ["roofing", "solar"], "outbound_authorized": False},
        {"verticals": ["solar"], "outbound_authorized": False},
        {"verticals": ["roofing", "roofing"], "outbound_authorized": False},
    ]
    report = review_current_buyer_contactability(sample, now=NOW)
    assert report["shortlisted_buyer_targets"] == 3
    assert report["research_target_sectors"] == {
        "roofing": 2, "solar": 2, "hvac": 0
    }
    assert report["buyer_contact_verified_count"] == 0
    assert report["permitted_email_recipients"] is None
    assert report["research_geography_and_live_buying_role_verified"] is False
