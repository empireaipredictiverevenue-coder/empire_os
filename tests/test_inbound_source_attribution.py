"""Source attribution must be first-party evidenced, never guessed."""
from datetime import datetime, timedelta, timezone
import pytest

from empire_os.inbound_source_attribution import SourceTouch, attribute_recovered_sources
from empire_os.inbound_revenue_recovery import RecoveryEvent

NOW = datetime(2026, 10, 20, 13, tzinfo=timezone.utc)


def event(kind, minute, *, call="call-a", tenant="customer-one",
          paid=None, currency="", receipt=None, synthetic=False):
    origins = {
        "unanswered": "provider", "callback_connected": "provider",
        "booking_confirmed": "calendar", "booking_cancelled": "calendar", "invoice_paid": "payments",
    }
    return RecoveryEvent(
        tenant_id=tenant, call_id=call,
        event_id=f"{call}-{kind}-{minute}",
        kind=kind, origin=origins[kind],
        occurred_at=(NOW + timedelta(minutes=minute)).isoformat(),
        evidence_ref=receipt or f"{call}-{kind}-receipt",
        verified=True, synthetic=synthetic, amount_minor=paid, currency=currency,
    )


def touch(channel, minute=-10, *, call="call-a", tenant="customer-one",
          attested_by="first_party_call_tracking", verified=True,
          synthetic=False, source_ref="call-track-provider-id", touch_id=None):
    return SourceTouch(
        tenant_id=tenant, call_id=call, touch_id=touch_id or f"{call}-{channel}-{minute}",
        occurred_at=(NOW + timedelta(minutes=minute)).isoformat(),
        channel=channel, source_ref=source_ref,
        attested_by=attested_by, verified=verified, synthetic=synthetic,
    )


def report(events, touches=(), *, minute=60):
    return attribute_recovered_sources(
        events, touches, tenant_id="customer-one",
        as_of=NOW + timedelta(minutes=minute),
    )


def test_verified_first_and_last_touch_with_paid_receipt():
    data = [
        event("unanswered", 0),
        event("callback_connected", 15),
        event("invoice_paid", 20, paid=12000, currency="GBP"),
    ]
    result = report(data, [
        touch("organic_search", -30),
        touch("paid_search", -10),
    ])
    assert result["recovered_calls"] == 1
    assert result["recovered_calls_with_verified_source"] == 1
    assert result["last_touch_channels"]["paid_search"]["recovered_calls"] == 1
    assert result["last_touch_channels"]["paid_search"]["verified_paid_minor_by_currency"] == {"GBP": 12000}
    assert result["first_touch_recovered_call_counts"] == {"organic_search": 1}
    assert not result["profit_or_roi_inferred"]


def test_unlinked_or_unverified_channel_is_unattributed():
    recovery = [event("unanswered", 0), event("booking_confirmed", 10)]
    result = report(recovery, [
        touch("paid_social", -10, verified=False, attested_by="unverified"),
    ])
    assert result["recovered_calls_without_verified_source"] == 1
    assert result["last_touch_channels"]["unattributed"]["recovered_calls"] == 1
    assert result["ignored_unverified_source_touches"] == 1


def test_touch_after_call_cannot_rewrite_acquisition_source():
    data = [event("unanswered", 0), event("callback_connected", 10)]
    result = report(data, [touch("paid_search", minute=1)])
    assert result["recovered_calls_with_verified_source"] == 0


def test_click_from_different_business_or_call_is_ignored():
    data = [event("unanswered", 0), event("booking_confirmed", 10)]
    result = report(data, [
        touch("paid_social", tenant="customer-two"),
        touch("organic_search", call="another-call"),
    ])
    assert result["last_touch_channels"]["unattributed"]["recovered_calls"] == 1


def test_out_of_window_touch_does_not_qualify():
    data = [event("unanswered", 0), event("booking_confirmed", 10)]
    result = report(data, [touch("referral", -31 * 24 * 60)])
    assert result["recovered_calls_without_verified_source"] == 1


def test_synthetic_or_cross_tenant_receipts_never_create_paid_recovery():
    data = [
        event("unanswered", 0), event("callback_connected", 10),
        event("invoice_paid", 20, paid=10000, currency="GBP", synthetic=True),
        event("invoice_paid", 25, paid=90000, currency="GBP", tenant="customer-two"),
    ]
    result = report(data, [touch("organic_search")])
    assert result["last_touch_channels"]["organic_search"]["verified_paid_minor_by_currency"] == {}


def test_payment_before_recovered_contact_not_attributed():
    data = [
        event("unanswered", 0),
        event("invoice_paid", 2, paid=1000, currency="GBP"),
        event("callback_connected", 10),
    ]
    result = report(data)
    assert result["last_touch_channels"]["unattributed"]["verified_paid_minor_by_currency"] == {}


def test_same_receipt_across_calls_does_not_inflate_paid_sum():
    data = [
        event("unanswered", 0, call="a"),
        event("callback_connected", 5, call="a"),
        event("invoice_paid", 15, call="a", paid=21000, currency="GBP", receipt="one-receipt"),
        event("unanswered", 0, call="b"),
        event("callback_connected", 5, call="b"),
        event("invoice_paid", 15, call="b", paid=21000, currency="GBP", receipt="one-receipt"),
    ]
    result = report(data, [touch("referral", call="a"), touch("referral", call="b")])
    assert result["recovered_calls"] == 2
    assert result["last_touch_channels"]["referral"]["verified_paid_minor_by_currency"] == {"GBP": 21000}


def test_optout_blocks_source_recovery_claim():
    data = [event("unanswered", 0), event("callback_connected", 10)]
    data.append(RecoveryEvent(
        tenant_id="customer-one", call_id="call-a", event_id="optout",
        occurred_at=(NOW + timedelta(minutes=1)).isoformat(),
        kind="followup_opt_out", origin="operator",
        synthetic=False,
    ))
    assert report(data, [touch("organic_search")])["recovered_calls"] == 0


def test_duplicate_touch_replay_idempotent_and_conflict_fails():
    data = [event("unanswered", 0), event("callback_connected", 10)]
    t = touch("referral")
    report1 = report(data, [t, t])
    assert report1["recovered_calls_with_verified_source"] == 1
    with pytest.raises(ValueError, match="conflicting_duplicate"):
        report(data, [t, SourceTouch(
            tenant_id=t.tenant_id, call_id=t.call_id,
            touch_id=t.touch_id, occurred_at=t.occurred_at,
            channel="direct", source_ref=t.source_ref,
            verified=True, attested_by=t.attested_by, synthetic=False,
        )])


def test_verified_source_requires_attested_primary_reference():
    with pytest.raises(ValueError, match="verified_touch_requires"):
        touch("paid_search", source_ref="", verified=True)
    with pytest.raises(ValueError, match="verified_touch_requires"):
        touch("paid_search", verified=True, attested_by="unverified")


def test_no_touch_cannot_claim_roi_or_spend():
    result = report([event("unanswered", 0)])
    assert result["recovered_calls"] == 0
    assert not result["ad_spend_inferred"]
    assert not result["source_inference_permitted"]


def test_cancelled_booking_not_claimed_as_source_recovered_or_paid():
    data = [
        event("unanswered", 0),
        event("booking_confirmed", 10, receipt="calendar-event-01"),
        event("booking_cancelled", 15, receipt="calendar-event-01"),
        event("invoice_paid", 20, paid=29000, currency="GBP", receipt="payment-01"),
    ]
    result = report(data, [touch("paid_search")])
    assert result["recovered_calls"] == 0
    assert result["last_touch_channels"] == {}
    assert not result["profit_or_roi_inferred"]
