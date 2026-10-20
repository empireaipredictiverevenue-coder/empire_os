"""Existing self-serve membership is NOT an activated paid or delivery contract."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.exchange_self_serve_fulfilment_review_v1 import (
    build_exchange_self_serve_fulfilment_review,
)
from tests.exchange_snapshot_fixture_20261020 import fixture, NOW


def buyer_interest():
    return {
        "decision": "interest_recorded",
        "tier_code": "exchange_seat_growth",
        "delivery_preference": "webhook",
        "pricing_binding": False,
        "seat_activated": False,
        "commercial_terms_verified": False,
        "capacity_verified": False,
        "actual_revenue": False,
        "email": "personal-secret@example.com",
        "buyer_name": "Private Buyer Name",
    }


def test_four_memberships_are_interest_only_without_proven_mrr():
    result = build_exchange_self_serve_fulfilment_review(fixture(), now=NOW)
    assert result["state"] == "OPERATOR_REVIEW_ONLY"
    assert [p["monthly_membership_price_cents"] for p in result["plan_catalog"]] == [
        9900, 24900, 49900, 99900,
    ]
    assert result["subscription_activation_authorized"] is False
    assert result["lead_delivery_authorized"] is False
    assert result["recognized_mrr_cents"] == 0
    assert result["canonical_inventory"]["delivery_ready_now"] == 0
    assert result["canonical_inventory"]["allocation_candidate_records"] == 1
    assert result["canonical_inventory"]["verified_active_capacity_seat_records"] == 1
    assert result["subscription_and_usage_billing_must_be_separate"]
    assert result["legacy_sqlite_billing_not_accepted"]


def test_buyer_interest_receipt_never_proves_entitlement_or_exposes_person():
    r = build_exchange_self_serve_fulfilment_review(
        fixture(), now=NOW, interest_receipt=buyer_interest(),
    )
    assert r["buyer_interest_state"] == "BUYER_STATED_NON_BINDING_INTEREST"
    assert r["requested_product_monthly_price_cents"] == 24900
    assert r["requested_delivery_mode_supported"] is True
    assert "payment" in " ".join(r["subscription_gate_proofs_not_provided"])
    assert r["actual_contract_subscriptions_verified"] == 0
    assert r["lead_delivery_authorized"] is False
    assert "personal-secret" not in json.dumps(r)
    assert "Private Buyer Name" not in json.dumps(r)


def test_unsupported_delivery_mode_adds_gate():
    interest = buyer_interest()
    interest["tier_code"] = "exchange_seat_starter"
    interest["delivery_preference"] = "api"
    r = build_exchange_self_serve_fulfilment_review(
        fixture(), now=NOW, interest_receipt=interest,
    )
    assert r["requested_delivery_mode_supported"] is False
    assert "requested_delivery_mode_outside_selected_tier" in r["blockers"]


@pytest.mark.parametrize("tamper", [
    lambda x: x.update({"decision": "subscription_paid"}),
    lambda x: x.update({"seat_activated": True}),
    lambda x: x.update({"actual_revenue": True}),
    lambda x: x.update({"pricing_binding": True}),
    lambda x: x.update({"commercial_terms_verified": True}),
    lambda x: x.update({"capacity_verified": True}),
    lambda x: x.update({"tier_code": "fake_paid_plan"}),
])
def test_forged_paid_interest_fail_closed(tamper):
    value = buyer_interest()
    tamper(value)
    r = build_exchange_self_serve_fulfilment_review(
        fixture(), interest_receipt=value, now=NOW,
    )
    assert r["state"] == "HOLD"
    assert r["subscription_activation_authorized"] is False
    assert r["recognized_mrr_cents"] == 0


def test_invalid_snapshot_and_stale_receipt_held():
    snap = fixture()
    snap["canonical_backend"] = "supabase"
    r = build_exchange_self_serve_fulfilment_review(snap, now=NOW)
    assert r["state"] == "HOLD"
    assert r["lead_delivery_authorized"] is False

    snap = fixture()
    snap["observed_at"] = (NOW - timedelta(days=1)).isoformat()
    r = build_exchange_self_serve_fulfilment_review(snap, now=NOW)
    assert r["state"] == "OPERATOR_REVIEW_ONLY"
    assert r["canonical_inventory"]["fresh"] is False
    assert "fresh_canonical_empiredb_market_snapshot" in r["blockers"]


def test_qualified_buyer_is_not_payment_or_legal_source_rights():
    r = build_exchange_self_serve_fulfilment_review(fixture(), now=NOW)
    assert r["buyer_qualified_discount_may_reduce_commercial_review_not_privacy_or_source_rights"]
    assert "person_specific_notice_consent_and_transfer_rights_where_applicable" in r["per_lead_gate_proofs_not_provided"]
    assert "recorded_delivery_acknowledgement_and_rejection_window" in r["per_lead_gate_proofs_not_provided"]
