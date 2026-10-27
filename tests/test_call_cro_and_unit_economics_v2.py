"""CRO stage ratios and cash/unit research are independent and proof-gated."""
from datetime import datetime, timezone
from pathlib import Path
import pytest

from empire_os.conversion_intelligence import (
    HOMEOWNER_CALL_STAGES, review_homeowner_call_funnel,
)
from empire_os.call_unit_economics_review import (
    REQUIRED_FIELDS, REQUIRED_RECEIPTS, review_call_unit_economics,
)

STAGES = {
    "landing_sessions": 1000,
    "eligible_zip_interactions": 300,
    "consented_call_choices": 120,
    "provider_connected_calls": 70,
    "buyer_accepted_payable_calls": 50,
    "independently_settled_calls": 40,
}
COSTS = {
    "provider_connected_calls": 70,
    "buyer_accepted_payable_calls": 50,
    "independently_settled_calls": 40,
    "bank_verified_cash_received_cents": 300000,
    "actual_paid_media_cost_cents": 125000,
    "actual_publisher_cost_cents": 12000,
    "actual_processing_cost_cents": 3000,
    "actual_refund_or_chargeback_cost_cents": 2000,
}

def homeowner(**kwargs):
    return review_homeowner_call_funnel(
        source_id="google_search_ads", cohort_ref="SYNTHETIC_TEST_COHORT_ONLY",
        counts=kwargs.get("counts", STAGES),
        evidence_refs=kwargs.get("refs", {
            x: "test:synthetic:" + x for x in HOMEOWNER_CALL_STAGES
        }),
        source_lineage_verified=kwargs.get("verified", True),
        min_sample_size=20,
    )

def unit(**kwargs):
    return review_call_unit_economics(
        source_id="google_search_ads", cohort_ref="SYNTHETIC_TEST_COHORT_ONLY",
        currency="USD",
        values=kwargs.get("values", COSTS),
        receipt_refs=kwargs.get("refs", {
            x: "test:synthetic:" + x for x in REQUIRED_RECEIPTS
        }),
        source_attribution_verified=kwargs.get("attributed", True),
        independent_finance_verified=kwargs.get("finance", True),
        same_cohort_verified=kwargs.get("same_cohort", True),
    )

def test_synthetic_cro_measures_only_documented_same_cohort():
    x = homeowner()
    assert x["measured_stage_count"] == 5
    assert x["first_reviewable_bottleneck"] == "eligible_zip_interactions"
    assert x["bottleneck_rate"] == 0.3
    assert x["stage_reviews"][0]["stage_conversion_rate"] is None
    assert x["stage_reviews"][-1]["stage_conversion_rate"] == 0.8
    assert x["automatic_experiment_rollout"] is False
    assert x["execution_authority"] == "none"

def test_unknown_counts_cro_cannot_infer_dropoff():
    unknowns = {x: None for x in HOMEOWNER_CALL_STAGES}
    x = homeowner(counts=unknowns, refs={x: None for x in HOMEOWNER_CALL_STAGES}, verified=False)
    assert x["measured_stage_count"] == 0
    assert x["first_reviewable_bottleneck"] is None
    assert all(x["stage_conversion_rate"] is None for x in x["stage_reviews"])

def test_absent_source_lineage_hides_rates_even_with_synthetic_counts():
    x = homeowner(verified=False)
    assert x["first_reviewable_bottleneck"] is None
    assert x["measured_stage_count"] == 0
    assert all(x["stage_conversion_rate"] is None for x in x["stage_reviews"])

def test_missing_earlier_step_no_fake_rate_from_disjoint_populations():
    counts = dict(STAGES)
    counts["eligible_zip_interactions"] = None
    x = homeowner(counts=counts)
    assert x["stage_reviews"][2]["stage_conversion_rate"] is None

def test_impossible_conversion_sequence_rejected():
    counts = dict(STAGES)
    counts["buyer_accepted_payable_calls"] = 100
    with pytest.raises(ValueError):
        homeowner(counts=counts)

def test_same_cohort_cash_unit_math_with_synthetic_inputs():
    x = unit()
    assert x["profitability_calibrated"] is True
    assert x["actual_cash_received_cents"] == 300000
    assert x["actual_cost_cents"] == 142000
    assert x["cash_margin_cents"] == 158000
    assert x["cash_margin_per_settled_call_cents"] == 3950
    assert x["cru_acronym_expansion_confirmed"] is False
    assert x["spend_approved"] is False and x["payment_approved"] is False

@pytest.mark.parametrize("override", [
    {"attributed": False}, {"finance": False}, {"same_cohort": False},
    {"values": {x: None for x in REQUIRED_FIELDS}},
    {"refs": {x: None for x in REQUIRED_RECEIPTS}},
])
def test_missing_proof_means_unknown_margin(override):
    x = unit(**override)
    assert x["profitability_calibrated"] is False
    assert x["cash_margin_cents"] is None
    assert x["cash_margin_per_settled_call_cents"] is None
    assert x["actual_cash_received_cents"] is None

def test_financial_boolean_and_negative_cost_rejected():
    values = dict(COSTS)
    values["actual_paid_media_cost_cents"] = -1
    with pytest.raises(ValueError):
        unit(values=values)
    values["actual_paid_media_cost_cents"] = True
    with pytest.raises(ValueError):
        unit(values=values)

def test_accepted_calls_cannot_exceed_connected():
    values = dict(COSTS)
    values["buyer_accepted_payable_calls"] = 100
    with pytest.raises(ValueError):
        unit(values=values)

def test_zero_settled_call_never_claims_margin():
    values = dict(COSTS)
    values["independently_settled_calls"] = 0
    x = unit(values=values)
    assert x["cash_margin_per_settled_call_cents"] is None
    assert x["profitability_calibrated"] is False

def test_existing_owner_handoff_contains_both_scoped_reviews():
    from empire_os.competitor_call_cro_owner_handoff import build_cro_owner_handoff
    r = {
        "schema_version": "empire.competitor_call_conversion_readiness.v1",
        "mode": "OBSERVE", "exact_source_to_settlement_proven": False,
        "acquisition_source_profitability_calibrated": False,
        "ad_spend_authorized": False, "content_publication_authorized": False,
        "external_send_authorized": False, "database_writes": False,
        "execution_authority": "none",
        "measurement_chain_steps": [
            {"stage": str(i), "verified": False, "count": None}
            for i in range(6)
        ],
    }
    x = build_cro_owner_handoff(readiness=r, page_source=None,
                                form_source=None, now=datetime(2026, 10, 27, 13, tzinfo=timezone.utc))
    assert x["homeowner_call_cohort_review"]["measured_stage_count"] == 0
    assert x["provisional_cru_unit_economics"]["cash_margin_cents"] is None
    assert x["cru_meaning_canonical_verified"] is False
