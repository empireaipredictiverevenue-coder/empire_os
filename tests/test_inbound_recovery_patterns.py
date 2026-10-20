from datetime import datetime, timedelta, timezone

import pytest

from empire_os.inbound_recovery_patterns import PatternPolicy, analyse_inbound_patterns
from empire_os.inbound_revenue_recovery import RecoveryEvent

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def event(i, *, kind="unanswered", day_offset=0, tenant="a",
          synthetic=False, verified=True, event_id=None):
    timestamp = NOW - timedelta(days=day_offset, minutes=i)
    return RecoveryEvent(
        tenant_id=tenant, event_id=event_id or f"{i}-{kind}-{day_offset}",
        call_id=f"call-{i}", occurred_at=timestamp.isoformat(),
        kind=kind, origin="provider", verified=verified, synthetic=synthetic,
    )


def analyse(events, **kwargs):
    return analyse_inbound_patterns(
        events, as_of=NOW,
        policy=PatternPolicy("a", "Europe/London", **kwargs),
    )


def test_insufficient_sample_no_invented_alerts():
    report = analyse([event(0), event(1), event(2)])
    assert report["cohort_sufficient"] is False
    assert report["alerts"] == []
    assert report["revenue_estimated"] is False


def test_verified_recurrent_missed_window_can_trigger_internal_recommendation():
    # Twenty verified local test events, all on same Tuesday morning.
    observed = [event(i, kind="unanswered" if i < 12 else "answered") for i in range(20)]
    report = analyse(observed)
    assert report["cohort_sufficient"] is True
    assert report["sample_size"] == 20
    assert report["missed_calls"] == 12
    assert report["alerts"]
    assert report["alerts"][0]["priority"] == "operator_capacity_review"
    assert report["alerts"][0]["automated_changes"] is False


def test_repeated_provider_event_id_not_double_counted():
    one = event(0)
    report = analyse([one, one, one], minimum_calls=1, minimum_segment_calls=1,
                     minimum_missed_calls=1)
    assert report["sample_size"] == 1
    assert report["missed_calls"] == 1


def test_answered_and_missed_same_call_is_excluded_not_mislabeled():
    report = analyse([event(0), event(0, kind="answered")])
    assert report["sample_size"] == 0
    assert report["ambiguous_dispositions_excluded"] == 1


def test_synthetic_cross_tenant_unverified_and_stale_excluded():
    report = analyse([
        event(0, synthetic=True),
        event(1, tenant="b"),
        event(2, verified=False),
        event(3, day_offset=40),
    ])
    assert report["sample_size"] == 0
    assert report["alerts"] == []


def test_threshold_prevents_overreacting_to_low_volume():
    report = analyse([event(i) for i in range(20)],
                     minimum_segment_calls=25)
    assert report["cohort_sufficient"] is True
    assert report["alerts"] == []


def test_timezone_policy_validated():
    with pytest.raises(ValueError, match="valid_timezone"):
        PatternPolicy("a", "Nowhere/Missing")
    with pytest.raises(ValueError, match="threshold"):
        PatternPolicy("a", "Europe/London", minimum_calls=0)
    with pytest.raises(ValueError, match="timezone_aware"):
        analyse_inbound_patterns(
            [event(1)], as_of=datetime(2026, 10, 20, 12),
            policy=PatternPolicy("a", "Europe/London"),
        )


def test_source_does_not_pretend_to_predict_revenue():
    report = analyse([event(i) for i in range(20)])
    assert report["predictive_causal_claims"] is False
    assert report["customer_contact_authorized"] is False
    for alert in report["alerts"]:
        assert alert["estimated_revenue"] is None
