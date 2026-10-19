"""First-payer cross-owner gap review. No private CRM or DB operations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.flagship_first_payer_owner_handoff import (
    review_current_first_payer_owner_handoff,
    summarize_first_payer_owner_handoff,
)
from empire_os.revenue_buyer_evidence_handoff import (
    review_one_commercial_evidence_request,
    EVIDENCE_CUSTODY,
)
from empire_os.predictive_formula_evidence_review import review_formula_evidence
from empire_os.flagship_buyer_market_projection import (
    review_authorized_market_coverage_snapshot,
)
from test_revenue_buyer_evidence_handoff import fixture

def inputs(tmp_path):
    now = fixture(tmp_path)
    buyer = review_one_commercial_evidence_request(tmp_path, as_of=now)
    formula = review_formula_evidence(tmp_path, as_of=now)
    coverage = review_authorized_market_coverage_snapshot(tmp_path, as_of=now)
    return now, buyer, formula, coverage


def review(now, buyer, formula, coverage):
    return summarize_first_payer_owner_handoff(
        buyer=buyer, formula=formula, coverage=coverage, as_of=now,
    )


def test_existing_owner_workflow_selected_without_duplicate_tasks(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    assert buyer["status"] == "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
    result = review(now, buyer, formula, coverage)
    assert result["status"] == "FIRST_PAYER_BUYER_EVIDENCE_BLOCKED"
    assert result["opaque_opportunity_ref"] == buyer["request"]["opportunity_ref"]
    assert result["market_vertical"] == buyer["request"]["niche"]
    assert result["first_priority_owner"] == "business_development"
    assert result["second_priority_owner"] == "scientific_quant"
    assert len(result["same_opportunity_quant_input_gaps"]) == 11
    assert set(r["field"] for r in result["same_opportunity_quant_input_gaps"]) == set(EVIDENCE_CUSTODY) - set(("buyer_intent_normalized_score_required", "demand_normalized_score_required", "distribution_path_required", "offer_key_required"))
    assert result["source_request_not_equivalent_to_buyer_acceptance"] is True
    assert result["global_quant_counts_not_same_opportunity_counts"] is True
    assert result["forecast_issued"] is False
    assert result["existing_work_item_created"] is False
    assert result["crm_accessed"] is False
    assert result["canonical_record_writes"] is False
    assert result["outbound_sent"] is False
    assert result["funds_moved"] is False
    assert not (tmp_path/"runtime/departments/work").exists()


def test_public_owner_handoff_cannot_leak_source_private_fields(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    buyer["private_customer_email"] = "private@example.com"
    formula["private_secret"] = "never-export-this"
    result = review(now, buyer, formula, coverage)
    serialized = json.dumps(result)
    assert "private@example.com" not in serialized
    assert "never-export-this" not in serialized


def test_missing_original_buyer_request_stays_unknown(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    buyer = dict(buyer, status="HELD_NO_CURRENT_FIRST_PARTY_GAP", request=None)
    result = review(now, buyer, formula, coverage)
    assert result["status"] == "CURRENT_OPPORTUNITY_NOT_ESTABLISHED"
    assert result["opaque_opportunity_ref"] is None
    assert result["same_opportunity_quant_input_gaps"] == []
    assert result["first_priority_owner"] == "existing_evidence_pathways_owner"
    assert result["first_priority_action"] == "RESTORE_CURRENT_FIRST_PARTY_OPPORTUNITY_EVIDENCE"


def test_global_quant_counts_are_explicitly_not_per_opportunity(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    formula["quant_original_prediction_readiness"] = {
        "candidate_count": 11,
        "available_quant_decision_count": 0,
        "source_rows_are_original_conversion_predictions": False,
        "immutable_prediction_receipt_verified": False,
    }
    result = review(now, buyer, formula, coverage)
    assert result["global_quant_candidates_observed"] == 11
    assert result["global_quant_complete_count"] == 0
    assert result["same_buyer_verified_terms"] is False
    assert result["global_quant_counts_not_same_opportunity_counts"] is True


@pytest.mark.parametrize("alter", [
    lambda b,f,c: b.update(buyer_contacted=True),
    lambda b,f,c: b.update(forecast_created=True),
    lambda b,f,c: b.update(actual_revenue_verified=True),
    lambda b,f,c: b.update(execution_authority="send"),
    lambda b,f,c: b["request"].update(opportunity_ref="unsafe-ref"),
    lambda b,f,c: b["request"].update(quant_gaps=[]),
    lambda b,f,c: b["request"]["quant_gaps"][0].update(required_source="PUBLIC_FORUM"),
    lambda b,f,c: b["request"]["quant_gaps"].append(deepcopy(b["request"]["quant_gaps"][0])),
    lambda b,f,c: b["request"].update(automatic_email_or_offer_authorized=True),
    lambda b,f,c: f.update(forecast_generated_by_this_review=True),
    lambda b,f,c: f.update(commercial_execution_authorized=True),
    lambda b,f,c: c.update(written_terms_or_allocation_verified=True),
    lambda b,f,c: c.update(first_party_buyer_request_verified=True),
    lambda b,f,c: c.update(buyer_or_revenue_verified=True),
])
def test_mutated_owner_reports_never_promote_or_dispatch(tmp_path, alter):
    now, buyer, formula, coverage = inputs(tmp_path)
    alter(buyer, formula, coverage)
    with pytest.raises(ValueError):
        review(now, buyer, formula, coverage)
    assert not (tmp_path/"runtime/departments/work").exists()


def test_cross_owner_review_uses_only_existing_observers(tmp_path):
    now, _, _, _ = inputs(tmp_path)
    result = review_current_first_payer_owner_handoff(tmp_path, as_of=now)
    assert result["status"] == "FIRST_PAYER_BUYER_EVIDENCE_BLOCKED"
    assert result["registry_activated"] is False
    assert not (tmp_path/"runtime/departments/work").exists()


def test_stale_authoritative_pathway_has_safe_existing_owner_recovery(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    buyer = dict(buyer, status="HELD_NO_CURRENT_FIRST_PARTY_GAP",
                 reason_code="authoritative_current_pathways_not_ready", request=None)
    result = review(now, buyer, formula, coverage)
    assert result["buyer_source_hold_reason"] == "authoritative_current_pathways_not_ready"
    assert result["first_priority_owner"] == "existing_evidence_pathways_owner"
    assert result["opaque_opportunity_ref"] is None
    assert result["existing_work_item_created"] is False
    assert result["forecast_issued"] is False


def test_untrusted_formula_status_cannot_inject_contacts_to_founder_response(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    formula["source_status"]["opportunity_quant"] = "private@example.com"
    with pytest.raises(ValueError, match="source inventory"):
        review(now, buyer, formula, coverage)


def test_live_sourced_opportunity_with_unknown_market_stays_held(tmp_path):
    now, buyer, formula, coverage = inputs(tmp_path)
    buyer['request']['niche'] = None
    result = review(now, buyer, formula, coverage)
    assert result['status'] == 'FIRST_PAYER_MARKET_IDENTITY_HELD'
    assert result['market_vertical'] is None
    assert result['first_priority_owner'] == 'market_intelligence'
    assert result['first_priority_action'] == 'VERIFY_SOURCE_MARKET_NICHE_BEFORE_BUYER_MATCH'
    assert result['second_priority_owner'] is None
    assert result['second_priority_action'] is None
    assert result['same_buyer_verified_terms'] is False
    assert result['forecast_issued'] is False
