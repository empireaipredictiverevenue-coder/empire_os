"""Real observer reconciliation tests: synthetic fixtures remain offline."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os

import pytest

from scripts.review_tam_full_funnel_strategy_20261020 import (
    REAL_OBSERVER_SOURCES, read_real_commercial_observers,
    review_real_commercial_observers,
)

NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
STAMP = NOW.isoformat()


def sources():
    common = {"mode": "OBSERVE", "generated_at": STAMP}
    return {
        "next_best": {
            **common,
            "schema_version": "empire.next_best_action_snapshot.v1",
            "execution_authority": "none", "outreach_authorized": False,
            "payment_authorized": False, "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "action_count": 2, "actions": [
                {
                    "company_name": "PRIVATE_COMPANY_SHOULD_NOT_LEAK",
                    "entity_id": "secret_buyer",
                    "recommended_action": "verify_decision_maker",
                    "recommendation_only": True,
                    "execution_authority": "none",
                    "mutation_authorized": False,
                    "external_execution_authorized": False,
                    "outreach_authorized": False,
                    "payment_authorized": False,
                    "buyer_intent_inferred": False,
                    "commercial_intent_inferred": False,
                },
                {
                    "recommended_action": "research_more",
                    "recommendation_only": True,
                    "execution_authority": "none",
                    "mutation_authorized": False,
                    "external_execution_authorized": False,
                    "outreach_authorized": False,
                    "payment_authorized": False,
                    "buyer_intent_inferred": False,
                    "commercial_intent_inferred": False,
                },
            ],
        },
        "account_twin": {
            **common,
            "schema_version": "empire.account_buyer_digital_twin_snapshot.v1",
            "execution_authority": "none", "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_authorized": False, "payment_authorized": False,
            "twin_count": 1,
            "twins": [{
                "entity_id": "secret_buyer",
                "identity": {"company_name": "PRIVATE_ACCOUNT"},
                "revenue_truth": {"recognized_revenue_cents": 99999999},
            }],
        },
        "consent_outcome": {
            **common,
            "schema_version": "empire-consent-outcome-linkage-v1",
            "governance": {"db_write": False, "outbound": False, "funds": False},
            "linked_outcome_count": 2,
            "linked_outcomes": [
                {"source_table": "public.outbound_intents",
                 "outcome_id": "secret_internal_link_a"},
                {"source_table": "public.outbound_intents",
                 "outcome_id": "secret_internal_link_b"},
            ],
        },
        "campaign_output": {
            **common,
            "schema_version": "empire-campaign-output-outcome-v1",
            "db_write": False, "outbound": False,
            "campaign_state_mutated": False,
            "action_authority_granted": False,
            "output_quality_campaign_count": 5,
            "outcome_linkage_campaign_count": 0,
            "outcome_linkage_proved": False,
        },
        "campaign_measured": {
            **common,
            "schema_version": "empire-campaign-measured-outcome-v1",
            "governance": {"db_write": False, "outbound": False},
            "exact_outcome_match_count": 0, "outcome_linkage_proved": False,
        },
        "order_payment": {
            **common,
            "schema_version": "empire-orders-payments-revenue-runtime-control-v1",
            "governance": {"db_write": False, "funds_movement": False,
                           "payment_write": False},
            "semantic_truth": {"real_payment_observed": False},
            "current_transaction_row_count": 0,
        },
    }


def review(value=None):
    return review_real_commercial_observers(
        sources() if value is None else value, now=NOW,
    )


def test_six_authentic_sources_integrated_without_false_payment_or_buyer():
    result = review()
    assert result["integrated_current_observer_sources"] == 6
    assert result["total_observer_sources"] == 6
    assert result["existing_next_best_actions_reviewed"] == 2
    assert result["next_best_internal_play_counts"] == {
        "research_more": 1, "verify_decision_maker": 1,
    }
    assert result["fresh_account_twin_count"] == 1
    assert result["global_linked_event_records_not_sales"] == 2
    assert result["verified_campaign_output_quality_count"] == 5
    assert result["exact_campaign_outcome_linkage_count"] == 0
    assert result["payment_observed_within_checked_population"] is False
    assert result["campaign_verified_paying_customers"] is None
    assert result["recognized_campaign_revenue_cents"] is None
    assert result["margin_realized_cents"] is None
    assert result["production_actions_executed"] is False
    exported = json.dumps(result)
    for forbidden in (
        "PRIVATE_COMPANY_SHOULD_NOT_LEAK", "PRIVATE_ACCOUNT",
        "secret_internal_link", "secret_buyer", "99999999",
    ):
        assert forbidden not in exported


def test_stale_twin_is_not_joined_as_customer_or_fresh_identity():
    data = sources()
    data["account_twin"]["generated_at"] = (NOW-timedelta(days=19)).isoformat()
    result = review(data)
    assert result["integrated_current_observer_sources"] == 5
    assert result["fresh_account_twin_count"] is None
    assert result["source_health"]["account_twin"].startswith("HOLD_")
    assert "SOURCE_NOT_READY:account_twin" in result["source_holds"]
    assert result["campaign_verified_paying_customers"] is None


def test_global_outbound_intent_links_are_never_called_real_campaign_customers():
    data = sources()
    data["consent_outcome"]["linked_outcome_count"] = 8
    data["consent_outcome"]["linked_outcomes"] = [
        {"source_table": "public.outbound_intents", "outcome_id": f"opaque_{i}"}
        for i in range(8)
    ]
    result = review(data)
    assert result["global_linked_event_records_not_sales"] == 8
    assert result["exact_campaign_outcome_linkage_count"] == 0
    assert result["campaign_verified_paying_customers"] is None


def test_forged_new_contact_authority_or_newly_paid_event_is_rejected():
    data = sources()
    data["next_best"]["actions"][0]["mutation_authorized"] = True
    result = review(data)
    assert result["next_best_internal_play_counts"] is None
    assert "NEXT_BEST_PROVENANCE_INVALID" in result["source_holds"]
    assert result["source_health"]["next_best"] == "HOLD_RECOMMENDATION_SOURCE_GOVERNANCE"


def test_source_denominator_mismatch_holds_global_outcome_evidence():
    data = sources()
    data["consent_outcome"]["linked_outcome_count"] = 20
    result = review(data)
    assert result["global_linked_event_records_not_sales"] is None
    assert "GLOBAL_OUTCOME_LINKAGE_UNVERIFIED" in result["source_holds"]


def test_conflicting_campaign_outcome_observers_hold_exact_match_count():
    data = sources()
    data["campaign_output"]["outcome_linkage_campaign_count"] = 1
    data["campaign_output"]["outcome_linkage_proved"] = True
    result = review(data)
    assert result["exact_campaign_outcome_linkage_count"] is None
    assert "INDEPENDENT_CAMPAIGN_OUTCOME_COUNTERS_DISAGREE" in result["source_holds"]


def test_measured_outcome_proof_flag_cannot_contradict_match_count():
    data = sources()
    data["campaign_measured"]["outcome_linkage_proved"] = True
    result = review(data)
    assert result["exact_campaign_outcome_linkage_count"] is None
    assert "INDEPENDENT_CAMPAIGN_LINKAGE_PROOF_MISMATCH" in result["source_holds"]


def test_payment_population_must_not_imply_all_of_empire_has_no_revenue():
    data = sources()
    data["order_payment"]["current_transaction_row_count"] = 2
    data["order_payment"]["semantic_truth"]["real_payment_observed"] = True
    result = review(data)
    assert result["controlled_payment_source_row_count"] == 2
    assert result["payment_observed_within_checked_population"] is True
    # Observed payment is NOT evidence of recognized or realized campaign GP.
    assert result["recognized_campaign_revenue_cents"] is None
    assert result["margin_realized_cents"] is None
    assert result["campaign_verified_paying_customers"] is None


def test_incompatible_schema_stale_clock_and_non_observer_mode_fail_closed():
    for name in REAL_OBSERVER_SOURCES:
        for k, v in (
            ("schema_version", "wrong"),
            ("generated_at", (NOW-timedelta(days=3)).isoformat()),
            ("mode", "EXECUTE"),
        ):
            data = sources()
            data[name][k] = v
            result = review(data)
            assert result["source_health"][name] == "HOLD_STALE_MISSING_OR_INCOMPATIBLE_SOURCE"
            assert f"SOURCE_NOT_READY:{name}" in result["source_holds"]


def test_missing_snapshot_is_not_a_zero_count():
    value = sources()
    value.pop("next_best")
    result = review(value)
    assert result["existing_next_best_actions_reviewed"] is None
    assert result["next_best_internal_play_counts"] is None
    assert result["campaign_verified_paying_customers"] is None


def test_allowlisted_reader_rejects_symlink_and_world_writable_snapshot(tmp_path):
    for name, (relative, _) in REAL_OBSERVER_SOURCES.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sources()[name]))
        path.chmod(0o600)
    # End-to-end read from truly scoped test filesystem, no production writes.
    actual = read_real_commercial_observers(tmp_path)
    assert review(actual)["integrated_current_observer_sources"] == 6
    source_path = tmp_path / REAL_OBSERVER_SOURCES["account_twin"][0]
    source_path.unlink()
    (tmp_path / "private_target").write_text(json.dumps(sources()["account_twin"]))
    source_path.symlink_to(tmp_path / "private_target")
    assert read_real_commercial_observers(tmp_path)["account_twin"] == {}
    source_path.unlink()
    source_path.write_text(json.dumps(sources()["account_twin"]))
    source_path.chmod(0o666)
    assert read_real_commercial_observers(tmp_path)["account_twin"] == {}


def test_unsupported_next_best_action_label_not_exported(tmp_path):
    data = sources()
    data["next_best"]["actions"][0]["recommended_action"] = "private_payload@domain.test"
    result = review(data)
    assert result["next_best_internal_play_counts"]["other_existing_action"] == 1
    assert "private_payload" not in json.dumps(result)


def test_all_source_read_results_do_not_permit_external_execution():
    result = review()
    assert result["outbound_execution_eligible_from_observers"] is False
    assert result["canonical_crm_contact_join_established"] is False
    assert result["execution_authority"] == "NONE"
    assert result["database_writes"] is False

def test_full_funnel_owner_interface_receives_current_observers_without_fake_journeys():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    result = review_authenticated_campaign_intelligence(
        now=NOW, observer_snapshots=sources(),
    )
    connections = result["real_existing_source_connections"]
    assert connections["integrated_current_observer_sources"] == 6
    assert connections["existing_next_best_actions_reviewed"] == 2
    assert result["adaptive_buyer_journeys"] is None
    assert result["multiwave_campaign_learning"] is None
    assert result["live_recipient_contact_or_messages"] is False
    assert result["execution_authority"] == "NONE"


def test_owner_interface_without_observer_reader_reports_unknown():
    from scripts.review_tam_full_funnel_strategy_20261020 import (
        review_authenticated_campaign_intelligence,
    )
    result = review_authenticated_campaign_intelligence(now=NOW)
    assert result["real_existing_source_connections"] is None
    assert result["account_intelligence"] is None
    assert result["adaptive_buyer_journeys"] is None
