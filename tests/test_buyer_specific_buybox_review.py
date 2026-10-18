"""Buyer-specific proof never becomes a permission to send or allocate."""
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.buyer_specific_buybox_review import (
    review_single_buyer, review_buyer_buybox_candidates,
)
from scripts.review_existing_buyer_buybox_candidates import review_existing_buyers

NOW = datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc)


def buyer(**update):
    record = {
        "id": "buyer-1234",
        "buyer_name": "Genuine Solar Company",
        "niche": "Solar",
        "metro": "Bolton",
        "status": "active",
        "is_active": True,
        "reviewed_at": NOW.isoformat(),
        "daily_cap": 30,
        "calls_today": 0,
        "destination_phone": "recipient-path",
        "webhook_url": "",
        "commercial_activation_state": "discovered",
        "commercial_activated_at": None,
        "commercial_terms_source": None,
        "commercial_terms_reference": None,
        "commercial_terms_verified_at": None,
        "capacity_verified_at": None,
        "delivery_verified_at": None,
    }
    record.update(update)
    return record


def activated(**changes):
    row = buyer(
        commercial_activation_state="activated",
        commercial_activated_at=NOW.isoformat(),
        commercial_terms_source="agreement",
        commercial_terms_reference="reference1",
        commercial_terms_verified_at=NOW.isoformat(),
        capacity_verified_at=NOW.isoformat(),
        delivery_verified_at=NOW.isoformat(),
    )
    row.update(changes)
    return row


def test_first_party_buyer_has_next_steps_no_authority():
    record = review_single_buyer(buyer(), as_of=NOW)
    assert record["evidence_stage_count"] == 5
    assert record["next_action"] == "VERIFY_BUYER_CAPACITY_AGREEMENT"
    assert record["configured_activation_gate_passed"] is False
    assert record["specific_buybox_verified"] is False
    assert record["lead_delivery_authorized"] is False


def test_existing_activation_gate_not_promoted_to_buybox():
    record = review_single_buyer(activated(), as_of=NOW)
    assert record["configured_activation_gate_passed"] is True
    assert record["evidence_stage_count"] == 9
    assert record["next_action"] == "VERIFY_EXACT_BUYBOX_TERMS_AND_RECONTACT"
    assert record["specific_buybox_verified"] is False
    assert record["postcode_and_price_verified"] is False
    assert record["buyer_acceptance_verified"] is False
    assert record["buyer_can_be_quoted"] is False


@pytest.mark.parametrize("change,key", [
    ({"reviewed_at": (NOW + timedelta(minutes=5)).isoformat()}, "buyer_review"),
    ({"reviewed_at": "not-a-time"}, "buyer_review"),
    ({"capacity_verified_at": (NOW + timedelta(days=1)).isoformat()}, "capacity_evidence"),
    ({"daily_cap": True}, "configured_capacity"),
    ({"daily_cap": "30"}, "configured_capacity"),
    ({"metro": ""}, "market"),
])
def test_invalid_or_future_stage_evidence(change, key):
    record = review_single_buyer(buyer(**change), as_of=NOW)
    assert record["recorded_evidence"][key] is False


@pytest.mark.parametrize("change", [
    {"id": "fixture:buyer"},
    {"buyer_name": "Demo Buyer"},
    {"buyer_name": "Test Buyer"},
    {"status": "non_buyer"},
    {"webhook_url": "https://example.com/hook"},
])
def test_nonbuyer_entries_do_not_make_shortlist(change):
    assert review_single_buyer(buyer(**change), as_of=NOW) is None


def test_sorting_dedup_and_source_count():
    rows = [buyer(id="b-a", reviewed_at=None), activated(id="b-b")]
    review = review_buyer_buybox_candidates(rows, as_of=NOW, max_candidates=1)
    assert review["status"] == "CANDIDATE_REVIEW_READY"
    assert review["buyers_observed"] == 2
    assert review["candidate_count"] == 2
    assert review["returned_count"] == 1
    assert review["truncated_count"] == 1
    assert review["candidates"][0]["configured_activation_gate_passed"] is True
    assert review["specific_verified_buybox_count"] is None
    assert review["database_writes"] is False


def test_duplicate_and_bound_refuse_partial_report():
    with pytest.raises(ValueError, match="duplicate"):
        review_buyer_buybox_candidates([buyer(), buyer()], as_of=NOW)
    with pytest.raises(ValueError, match="bounded range"):
        review_buyer_buybox_candidates([buyer()], as_of=NOW, max_candidates=100)
    with pytest.raises(ValueError, match="timezone"):
        review_buyer_buybox_candidates([buyer()], as_of=datetime(2026, 10, 18))


def test_cli_redacts_company_and_can_filter_market():
    rows = [
        buyer(id="solar-1", buyer_name="Private Solar Buyer"),
        buyer(id="roof-1", buyer_name="Private Roofing Buyer", niche="roofing"),
    ]
    out = review_existing_buyers(
        buyer_rows=rows, niche="solar", as_of=NOW, limit=5,
    )
    assert out["candidate_count"] == 1
    assert out["company_names_exposed"] is False
    assert out["candidates"][0]["buyer_name"] is None
    assert "Private Solar Buyer" not in json.dumps(out)
    named = review_existing_buyers(
        buyer_rows=rows, niche="solar", as_of=NOW, include_names=True,
    )
    assert named["candidates"][0]["buyer_name"] == "Private Solar Buyer"
    assert named["outbound_sent"] is False


def test_absent_market_is_not_zero_total_buyers():
    out = review_existing_buyers(
        buyer_rows=[buyer(niche="roofing")], niche="solar", as_of=NOW,
    )
    assert out["status"] == "NO_REAL_BUYER_CANDIDATES"
    assert out["buyers_observed"] == 0
    assert out["filters"]["niche"] == "solar"
    assert out["specific_verified_buybox_count"] is None


def test_private_source_details_do_not_surface_in_result():
    record = activated(
        buyer_name="Real Solar",
        private_field="not-for-report",
        owner_note="confidential",
    )
    out = review_buyer_buybox_candidates([record], as_of=NOW)
    payload = json.dumps(out)
    assert "not-for-report" not in payload
    assert "confidential" not in payload
    assert "reference1" not in payload
    assert "recipient-path" not in payload

def test_same_row_summary_is_validated_without_authority():
    from empire_os.buyer_capacity_readiness import summarize_buyer_capacity
    from empire_os.executive_buyer_capacity_review import review_buyer_capacity
    source = summarize_buyer_capacity([buyer()], observed_at=NOW)
    assert source["same_record_preparation_count"] == 1
    result = review_buyer_capacity(source, as_of=NOW)
    assert result["counts"]["same_record_preparation_count"] == 1
    assert result["specific_buybox_verified"] is False
    source["same_record_preparation_count"] = 2
    assert review_buyer_capacity(source, as_of=NOW)["status"] == "SOURCE_UNTRUSTED"
