"""Offline PRIME owner-code promotion firewall; no live mailbox or tenant proofs."""
import hashlib
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.prime_buyer_partner_signal_shadow import (
    TAXONOMY, review_partner_signal_codes, founder_partner_signal_status,
)

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def e(code, i=0, **kw):
    v = {
        "event_code": code,
        "direction": TAXONOMY[code][1],
        "observed_at": (NOW - timedelta(hours=2)).isoformat(),
        "message_fingerprint": hashlib.sha256(f"fictional-message-{i}".encode()).hexdigest(),
    }
    v.update(kw)
    return v


def review(values):
    return review_partner_signal_codes(
        source="empire_gmail_api_readonly", observations=values, as_of=NOW,
    )


def test_all_original_codes_mapped_without_buyer_promotion():
    assert len(TAXONOMY) == 11
    items = [e(k, i) for i, k in enumerate(TAXONOMY)]
    out = review(items)
    assert out["source_observation_count"] == 11
    assert out["unique_message_count_not_verified_buyers"] == 11
    assert out["independently_verified_buyer_enquiries"] is None
    assert out["verified_paid_call_count"] is None
    assert out["realized_revenue_cents"] is None
    assert out["source_owner_authentication_verified"] is False
    assert out["execution_authority"] == "none"
    public = founder_partner_signal_status(out)
    assert public["observed_reported_event_count_band"] == "10-14"
    assert public["category_count_band_when_at_least_five"] == {}


def test_negative_and_pending_evidence_never_become_approval():
    x = review([
        e("PUBLISHER_SPONSORED_PLACEMENTS_ONLY_REPORTED", 1),
        e("BUYER_INTERNAL_DECISION_PENDING_REPORTED", 2),
    ])
    assert x["source_category_counts_unverified"] == {
        "INTERNAL_DECISION_PENDING_REPORTED": 1,
        "NEGATIVE_COMMERCIAL_FIT_REPORTED": 1,
    }
    assert x["buyer_activation_authorized"] is False


def test_two_distinct_codes_on_same_original_message_count_one_message():
    x = review([
        e("RECORDING_ENABLED_REPORTED", 1),
        e("ROUTE_OR_NUMBER_LIVE_REPORTED", 1),
    ])
    assert x["unique_message_count_not_verified_buyers"] == 1
    assert x["source_observation_count"] == 2


def test_duplicate_original_code_same_message_is_rejected():
    with pytest.raises(ValueError, match="duplicate_owner"):
        review([
            e("ROUTE_OR_NUMBER_LIVE_REPORTED"),
            e("ROUTE_OR_NUMBER_LIVE_REPORTED"),
        ])


def test_missing_source_is_unknown_not_empty_buyer_funnel():
    x = review_partner_signal_codes(
        source="empire_gmail_api_readonly", observations=None, as_of=NOW,
    )
    assert x["source_observation_count"] is None
    assert x["independently_verified_buyer_enquiries"] is None
    assert founder_partner_signal_status(x)["observed_reported_event_count_band"] is None


@pytest.mark.parametrize("change,reason", [
    ({"direction": "outbound"}, "direction"),
    ({"event_code": "BUYER_PAID_INVOICE"}, "unknown_original"),
    ({"message_fingerprint": "private@example.com"}, "opaque_original"),
    ({"observed_at": "2026-10-24T12:00:00"}, "timezone"),
    ({"observed_at": "2026-10-26T12:00:00Z"}, "future_original"),
    ({"raw_body": "please pay me"}, "privacy_minimal"),
])
def test_tampering_and_private_inputs_fail_closed(change, reason):
    with pytest.raises(ValueError, match=reason):
        review([e("ROUTE_OR_NUMBER_LIVE_REPORTED", **change)])


def test_public_surface_suppresses_rare_category_counts():
    public = founder_partner_signal_status(review([e("ROUTE_OR_NUMBER_LIVE_REPORTED")]))
    assert public["category_count_band_when_at_least_five"] == {}
    assert public["buyer_enquiries_independently_verified"] is False
    assert public["outbound_sent"] is False


def test_caller_cannot_promote_buyers_through_founder_projection():
    x = review([e("ROUTE_OR_NUMBER_LIVE_REPORTED")])
    x["buyer_activation_authorized"] = True
    with pytest.raises(ValueError, match="unpromoted"):
        founder_partner_signal_status(x)


def test_stale_observations_are_historical_not_fresh_signal():
    x = review([
        e("ROUTE_OR_NUMBER_LIVE_REPORTED",
          observed_at=(NOW - timedelta(days=60)).isoformat()),
    ])
    assert x["stale_observation_count"] == 1
    assert x["source_owner_authentication_verified"] is False
