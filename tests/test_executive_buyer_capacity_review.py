"""Commercial buyer capacity never becomes a fake payable publisher contract."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.executive_buyer_capacity_review import review_buyer_capacity
from empire_os.executive_commercial_observer import observe_executive_commercial_roles
from empire_os.executive_founder_status import read_executive_founder_status

NOW = datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)


def snapshot():
    return {
        "schema_version": "empire.buyer_capacity_readiness.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "allocation_executed": False, "allocation_ready": False,
        "payment_action": False, "revenue_recognition": False,
        "observed_at": (NOW - timedelta(minutes=5)).isoformat(),
        "buyers_seen": 1057, "reviewed": 1, "market_defined": 107,
        "positive_capacity_configured": 121,
        "delivery_destination_present": 485,
        "capacity_verified": 0, "terms_verified": 0,
        "delivery_verified": 0, "commercially_activated": 0,
        "fully_activated": 0,
        "buyer_contact": "PRIVATE_SHOULD_NEVER_BE_EMITTED",
    }


def test_real_aggregate_shape_is_observed_but_not_sellable():
    original = snapshot()
    before = json.dumps(original, sort_keys=True)
    r = review_buyer_capacity(original, as_of=NOW)
    assert r["status"] == "NO_VERIFIED_COMMERCIAL_CAPACITY"
    assert r["source_current"] is True
    assert r["counts"]["buyers_seen"] == 1057
    assert r["counts"]["terms_verified"] == 0
    assert r["publisher_payout_can_be_quoted"] is False
    assert r["lead_delivery_authorized"] is False
    assert r["specific_buybox_verified"] is False
    assert r["execution_authority"] == "none"
    assert "PRIVATE_SHOULD_NEVER_BE_EMITTED" not in json.dumps(r)
    assert json.dumps(original, sort_keys=True) == before


def test_all_positive_aggregate_numbers_are_not_specific_installer_buybox():
    x = snapshot()
    for key in ("capacity_verified", "terms_verified", "delivery_verified", "commercially_activated"):
        x[key] = 1
    r = review_buyer_capacity(x, as_of=NOW)
    assert r["status"] == "AGGREGATE_CAPACITY_NOT_SPECIFIC_BUYBOX"
    assert r["solar_installer_postcode_coverage_verified"] is False
    assert r["publisher_payout_can_be_quoted"] is False
    assert r["lead_delivery_authorized"] is False


@pytest.mark.parametrize("field,value", [
    ("mode", "EXECUTE"),
    ("execution_authority", "granted"),
    ("allocation_executed", True),
    ("allocation_ready", True),
    ("payment_action", True),
    ("revenue_recognition", True),
    ("terms_verified", True),
    ("buyers_seen", -1),
    ("buyers_seen", 0),
    ("capacity_verified", 10000001),
    ("observed_at", "2026-10-15T15:55:00"),
    ("observed_at", "2035-01-01T00:00:00Z"),
])
def test_untrusted_or_forged_capacity_evidence_is_held(field, value):
    x = snapshot()
    x[field] = value
    if field == "buyers_seen" and value == 0:
        # Cannot report more category-specific entries than buyers seen.
        pass
    assert review_buyer_capacity(x, as_of=NOW)["status"] == "SOURCE_UNTRUSTED" or (
        field == "observed_at" and value.startswith("2035")
        and review_buyer_capacity(x, as_of=NOW)["status"] == "SOURCE_STALE"
    )


def test_stale_and_missing_sources_never_claim_capacity():
    x = snapshot()
    x["observed_at"] = (NOW - timedelta(hours=5)).isoformat()
    assert review_buyer_capacity(x, as_of=NOW)["status"] == "SOURCE_STALE"
    assert review_buyer_capacity(None, as_of=NOW)["status"] == "SOURCE_MISSING"
    assert review_buyer_capacity([], as_of=NOW)["status"] == "SOURCE_UNTRUSTED"


def test_naive_review_clock_rejected():
    with pytest.raises(ValueError):
        review_buyer_capacity(snapshot(), as_of=datetime(2026, 10, 15))
