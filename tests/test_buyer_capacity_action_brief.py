"""Commercial capacity action flow is evidence-only and never an outbound grant."""
import json
from copy import deepcopy

import pytest

from empire_os.buyer_capacity_action_brief import build_buyer_capacity_action_brief
from empire_os.predictive_decision_control import build_predictive_decision_control
from test_predictive_decision_control import _build, _executive


def _executive_capacity(status="NO_VERIFIED_COMMERCIAL_CAPACITY", **changes):
    cap = {
        "status": status,
        "buyers_seen": 1057,
        "reviewed": 1,
        "market_defined": 107,
        "positive_capacity_configured": 121,
        "delivery_destination_present": 485,
        "capacity_verified": 0,
        "terms_verified": 0,
        "delivery_verified": 0,
        "commercially_activated": 0,
        "specific_buybox_verified": False,
        "publisher_payout_can_be_quoted": False,
        "lead_delivery_authorized": False,
    }
    cap.update(changes)
    return _executive(business_development={"downstream_buyer_capacity": cap})


def test_missing_authority_and_missing_source_holds():
    for data in (None, {}, _executive(available=False),
                 _executive(business_development={})):
        out = build_buyer_capacity_action_brief(data)
        assert out["status"] == "SOURCE_HOLD"
        assert out["work_dispatched"] is False
        assert out["lead_delivery_authorized"] is False
        assert out["verified_specific_buybox_count"] is None


def test_realistic_aggregate_returns_usable_buyer_capacity_checklist():
    out = build_buyer_capacity_action_brief(_executive_capacity())
    assert out["status"] == "BUYER_BUYBOX_EVIDENCE_REQUIRED"
    assert out["buyers_seen"] == 1057
    assert out["first_missing_evidence"] == "VERIFY_CURRENT_BUYER_CAPACITY_EVIDENCE"
    assert len(out["evidence_checklist"]) == 8
    assert out["evidence_checklist"][0]["aggregate_observed_count"] == 1
    assert out["evidence_checklist"][0]["status"] == "AGGREGATE_EXISTS_NOT_SAME_BUYER_PROOF"
    assert out["evidence_checklist"][3]["status"] == "NO_AGGREGATE_PROOF"
    assert out["same_buyer_cross_stage_binding_proven"] is False
    assert out["publisher_payout_can_be_quoted"] is False
    assert out["execution_authority"] == "none"
    assert "@" not in json.dumps(out)


def test_nonzero_aggregates_are_not_same_buyer_proof():
    out = build_buyer_capacity_action_brief(_executive_capacity(
        status="AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX",
        capacity_verified=5, terms_verified=3, delivery_verified=4,
        commercially_activated=2,
    ))
    assert out["status"] == "BUYER_BUYBOX_EVIDENCE_REQUIRED"
    assert out["first_missing_evidence"] == "BIND_ALL_EVIDENCE_TO_ONE_BUYER_BUYBOX"
    assert out["verified_specific_buybox_count"] == 0
    assert out["lead_delivery_authorized"] is False


@pytest.mark.parametrize("change", [
    {"capacity_verified": -1},
    {"terms_verified": True},
    {"buyers_seen": 2},
    {"reviewed": None},
    {"terms_verified": 10_000_001},
    {"specific_buybox_verified": True},
    {"publisher_payout_can_be_quoted": True},
    {"lead_delivery_authorized": True},
])
def test_invalid_or_spoofed_capacity_is_held(change):
    out = build_buyer_capacity_action_brief(_executive_capacity(**change))
    assert out["status"] == "SOURCE_HOLD"
    assert out["verified_specific_buybox_count"] is None
    assert out["work_dispatched"] is False


@pytest.mark.parametrize("status", ["SOURCE_MISSING", "SOURCE_UNTRUSTED", "SOURCE_STALE"])
def test_source_unavailable_cannot_be_turned_into_zero(status):
    out = build_buyer_capacity_action_brief(_executive_capacity(status=status))
    assert out["status"] == "SOURCE_HOLD"
    assert out["buyers_seen"] is None
    assert out["evidence_checklist"] == []


def test_zero_inventory_is_distinct_from_missing_source():
    out = build_buyer_capacity_action_brief(_executive_capacity(
        buyers_seen=0, reviewed=0, market_defined=0,
        positive_capacity_configured=0, delivery_destination_present=0,
    ))
    assert out["buyers_seen"] == 0
    assert out["evidence_checklist"][0]["status"] == "NO_AGGREGATE_PROOF"


def test_decision_control_includes_validated_action_brief():
    data = _build(executive=_executive_capacity())
    brief = data["buyer_capacity_action_brief"]
    assert data["top_three"][0]["recommended_action"] == brief["next_action"]
    assert brief["owner"] == "business_development"
    assert brief["first_missing_evidence"] == "VERIFY_CURRENT_BUYER_CAPACITY_EVIDENCE"
    assert data["outbound_authorized"] is False


@pytest.mark.parametrize("status,adjustment", [
    ("AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX", {}),
    ("NO_VERIFIED_COMMERCIAL_CAPACITY", {
        "capacity_verified": 2, "terms_verified": 2,
        "delivery_verified": 2, "commercially_activated": 2,
    }),
])
def test_inconsistent_evidence_status_is_held(status, adjustment):
    out = build_buyer_capacity_action_brief(
        _executive_capacity(status=status, **adjustment)
    )
    assert out["status"] == "SOURCE_HOLD"
    assert out["reason"] == "buyer_capacity_status_and_aggregate_counts_disagree"
    assert out["work_dispatched"] is False
