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


def test_original_predictive_bridge_accepts_codes_as_research_only():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    tenant = "tenant-prime-partner-test"
    source = [
        e("ROUTE_OR_NUMBER_LIVE_REPORTED", 1),
        e("PUBLISHER_SPONSORED_PLACEMENTS_ONLY_REPORTED", 2),
        e("BUYER_INTERNAL_DECISION_PENDING_REPORTED", 3),
        e("COMPLETE_BUYER_REQUIREMENTS_SENT", 4),
    ]
    review = build_predictive_revenue_brain_review(
        tenant_id=tenant, as_of=NOW, original_partner_signal_codes=source,
    )
    founder = review["prime_buyer_partner_signal_shadow"]
    assert founder["observed_reported_event_count_band"] == "0-4"
    assert founder["category_count_band_when_at_least_five"] == {}
    assert founder["owner_source_live_authenticated"] is False
    assert founder["buyer_enquiries_independently_verified"] is False
    assert founder["revenue_recognized"] is False
    assert founder["negative_and_pending_partner_evidence_preserved"] is True
    assert review["prime_first_buyer_intent_independently_verified"] is False
    assert review["prime_original_single_buyer_enquiry_preflight_status"] == "NOT_CONNECTED"
    assert review["prime_signed_owner_replay_protection_verified"] is False
    assert review["recognized_revenue_cents"] is None
    assert review["astra_dispatch_executed"] is False
    assert review["outbound_sent"] is False
    assert review["database_writes"] is False
    assert tenant not in str(founder)
    assert "message_fingerprint" not in str(founder)


def test_default_original_predictive_bridge_reports_unknown_source_not_zero():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    result = build_predictive_revenue_brain_review(
        tenant_id="tenant-prime-partner-test", as_of=NOW,
    )
    assert result["prime_buyer_partner_signal_shadow"]["observed_reported_event_count_band"] is None
    assert result["prime_buyer_partner_signal_shadow"]["buyer_enquiries_independently_verified"] is False
    assert result["revenue_verified"] is False


def test_bridge_fails_closed_for_untrusted_semantic_code_and_body():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    for injected in (
        e("ROUTE_OR_NUMBER_LIVE_REPORTED", body="PRIVATE PROVIDER TEXT"),
        e("ROUTE_OR_NUMBER_LIVE_REPORTED", direction="outbound"),
        e("ROUTE_OR_NUMBER_LIVE_REPORTED", event_code="PAYMENT_RECEIVED"),
    ):
        with pytest.raises(ValueError):
            build_predictive_revenue_brain_review(
                tenant_id="tenant-prime-partner-test",
                as_of=NOW,
                original_partner_signal_codes=[injected],
            )


def test_source_owner_taxonomy_changes_fail_closed_without_original_review(monkeypatch):
    from empire_os import prime_buyer_partner_signal_shadow as module
    from empire_os.buyer_mail_semantics import EVENT_CODES
    assert frozenset(module.TAXONOMY) == EVENT_CODES
    monkeypatch.setattr(module, "EVENT_CODES", EVENT_CODES | {"NEW_POTENTIAL_BUYER"})
    with pytest.raises(ValueError, match="taxonomy_changed_review_required"):
        review([])
