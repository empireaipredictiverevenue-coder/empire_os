"""First-payer source-to-Quant preflight tests. Synthetic fixtures only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.flagship_first_payer_quant_preflight import (
    review_first_payer_quant_preflight,
)
from empire_os.quant_brain import _DECISION_PACKET_REQUIRED

NOW = datetime(2026, 10, 19, 18, tzinfo=timezone.utc)
ECONOMICS = {
    "probability_success": .55,
    "conditional_revenue_cents": 150_000,
    "fixed_cost_cents": 5_000,
    "success_cost_cents": 20_000,
    "revenue_low_cents": 120_000,
    "revenue_high_cents": 180_000,
    "success_cost_low_cents": 15_000,
    "success_cost_high_cents": 25_000,
    "uncertainty": .30,
    "time_to_revenue_days": 12,
    "confidence": .70,
}
_MODEL = {"probability_success", "uncertainty", "confidence"}


def receipts():
    return {
        key: {
            "source_ref": "canonical:fixture:" + key,
            "tenant_id": "fixture-tenant",
            "opportunity_key": "fixture-opportunity",
            "observed_at": (NOW - timedelta(minutes=3)).isoformat(),
            "value": val,
            "source_class": (
                "ORIGINAL_MODEL_OUTPUT" if key in _MODEL
                else "FIRST_PARTY_COMMERCIAL"
            ),
        }
        for key, val in ECONOMICS.items()
    }


def run(**changes):
    args = dict(
        tenant_id="fixture-tenant",
        opportunity_key="fixture-opportunity",
        model_name="existing_quant",
        model_version="v1",
        quant_inputs=deepcopy(ECONOMICS),
        source_receipts=receipts(),
        assessed_at=NOW,
        horizon_days=30,
    )
    args.update(changes)
    return review_first_payer_quant_preflight(**args)


def test_absent_economics_preserves_exact_eleven_field_hold():
    result = run(quant_inputs={}, source_receipts={})
    assert result["status"] == "QUANT_EVIDENCE_INCOMPLETE"
    assert result["missing_quant_fields"] == list(_DECISION_PACKET_REQUIRED)
    assert result["prospective_registry_preflight"] is None
    assert result["buyer_identity_and_terms_authenticated"] is False


def test_missing_original_price_receipt_does_not_guess_or_promote():
    sources = receipts()
    sources.pop("conditional_revenue_cents")
    result = run(source_receipts=sources)
    assert result["quant_status"] == "UNAVAILABLE"
    assert result["unsupported_original_source_fields"] == [
        "conditional_revenue_cents"
    ]
    assert result["prospective_registry_preflight"] is None


def test_full_synthetic_values_are_only_registry_preflight_preview():
    report = run()
    assert report["status"] == "QUANT_PREVIEW_UNAUTHENTICATED_ORIGINAL_EVIDENCE"
    assert report["quant_status"] == "AVAILABLE"
    original = report["prospective_registry_preflight"]
    assert original["status"] == "REGISTRY_PROOF_REQUIRED"
    assert original["original_prediction_registered"] is False
    assert original["canonical_registry_readback_verified"] is False
    assert original["may_use_in_verified_calibration"] is False
    assert original["proposed_prediction"]["predicted_probability"] == .55
    assert original["proposed_prediction"]["tenant_id"] == "fixture-tenant"
    assert original["proposed_prediction"]["model_version"] == "v1"
    assert len(original["proposed_prediction"]["evidence_refs"]) == 11
    assert report["buyer_identity_and_terms_authenticated"] is False
    assert report["buyer_market_capacity_authenticated"] is False
    assert report["model_probability_prospectively_attested"] is False
    assert report["forecast_durably_registered"] is False
    assert report["customer_accuracy_claim_authorized"] is False
    assert report["original_revenue_verified"] is False
    assert report["database_writes"] is False
    assert report["funds_moved"] is False
    assert report["model_weights_changed"] is False


def test_repeatable_preview_identity_and_no_source_body():
    first = run()
    assert first == run()
    assert "phone" not in repr(first).lower()
    assert "buyer@email" not in repr(first)


@pytest.mark.parametrize("kind", [
    "untrusted_origin", "future", "wrong_value", "missing_field",
    "unsafe_ref", "naive_source", "fake_authenticated",
])
def test_bad_original_receipt_is_not_promoted(kind):
    data = receipts()
    row = data["probability_success"]
    if kind == "untrusted_origin":
        row["source_class"] = "PUBLIC_FORUM"
    elif kind == "future":
        row["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif kind == "wrong_value":
        row["value"] = .95
    elif kind == "missing_field":
        row.pop("source_ref")
    elif kind == "unsafe_ref":
        row["source_ref"] = "https://bad.example?token=secret"
    elif kind == "naive_source":
        row["observed_at"] = "2026-10-19T18:00:00"
    elif kind == "fake_authenticated":
        row["authenticated"] = True
    with pytest.raises(ValueError):
        run(source_receipts=data)


@pytest.mark.parametrize("change", [
    {"revenue_low_cents": 160_000},
    {"revenue_high_cents": 130_000},
    {"success_cost_low_cents": 25_001},
    {"success_cost_high_cents": 10_000},
    {"time_to_revenue_days": 31},
    {"probability_success": 1.2},
    {"confidence": float("nan")},
    {"uncertainty": True},
    {"fixed_cost_cents": -1},
])
def test_unsupported_quant_economics_are_held(change):
    data = deepcopy(ECONOMICS)
    data.update(change)
    src = receipts()
    for key, value in change.items():
        src[key]["value"] = value
    with pytest.raises(ValueError):
        run(quant_inputs=data, source_receipts=src)


def test_partial_inputs_do_not_emit_fake_probability():
    data = {"probability_success": .55}
    src = {"probability_success": receipts()["probability_success"]}
    result = run(quant_inputs=data, source_receipts=src)
    assert result["quant_candidate_preview"] is None
    assert result["prospective_registry_preflight"] is None
    assert "conditional_revenue_cents" in result["missing_quant_fields"]


@pytest.mark.parametrize("horizon", [0, 91, "30", True, -1])
def test_horizon_is_bounded(horizon):
    with pytest.raises(ValueError):
        run(horizon_days=horizon)


def test_no_extra_quant_fields_or_assumed_verified_sources():
    with pytest.raises(ValueError):
        run(quant_inputs=dict(ECONOMICS, verified_outcomes=[1, 0]))
    with pytest.raises(ValueError):
        run(source_receipts=dict(receipts(), unrelated_contact="text"))


@pytest.mark.parametrize("field, value", [
    ("tenant_id", "another-tenant"),
    ("opportunity_key", "other-opportunity"),
    ("tenant_id", ""),
    ("opportunity_key", ""),
])
def test_original_quant_sources_cannot_cross_buyer_or_tenant_boundaries(field, value):
    sources = receipts()
    sources["conditional_revenue_cents"][field] = value
    with pytest.raises(ValueError, match="another opportunity or tenant"):
        run(source_receipts=sources)


def test_original_model_probability_cannot_be_borrowed_from_another_opportunity():
    sources = receipts()
    sources["probability_success"]["opportunity_key"] = "unrelated-buyer"
    with pytest.raises(ValueError, match="another opportunity or tenant"):
        run(source_receipts=sources)
