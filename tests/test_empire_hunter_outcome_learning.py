from empire_os.hunter.models import ContactEvidence, VerificationState
from empire_os.hunter.outcome_learning import (
    calibrate_contact,
    calibrate_pattern_outcomes,
)


def contact():
    return ContactEvidence(
        email="jane.smith@acme.test",
        state=VerificationState.PROBABLE,
        confidence=0.78,
        source="empire_pattern_brain",
        person_name="Jane Smith",
        person_bound=True,
        mx_ok=True,
        syntax_ok=True,
    )


def test_verified_delivery_confirms_contact():
    result = calibrate_contact(
        contact(),
        [{
            "email": "jane.smith@acme.test",
            "event_type": "delivered",
            "verified": True,
            "evidence_ref": "outbound_event:1",
        }],
    )

    assert result.state is VerificationState.CONFIRMED
    assert result.posterior_confidence >= 0.95
    assert result.actual_revenue_observed is False


def test_verified_bounce_rejects_contact():
    result = calibrate_contact(
        contact(),
        [{
            "email": "jane.smith@acme.test",
            "event_type": "bounced",
            "verified": True,
            "evidence_ref": "provider_event:1",
        }],
    )

    assert result.state is VerificationState.REJECTED
    assert result.posterior_confidence <= 0.10


def test_unverified_event_does_not_change_confidence():
    result = calibrate_contact(
        contact(),
        [{
            "email": "jane.smith@acme.test",
            "event_type": "delivered",
            "verified": False,
            "evidence_ref": "model_guess:1",
        }],
    )

    assert result.posterior_confidence == 0.78
    assert result.state is VerificationState.PROBABLE
    assert result.verified_events == ()
    assert result.ignored_events == ("delivered",)


def test_revenue_and_gp_only_count_when_explicitly_observed():
    result = calibrate_contact(
        contact(),
        [{
            "email": "jane.smith@acme.test",
            "event_type": "revenue_recognized",
            "verified": True,
            "evidence_ref": "commercial_event:1",
            "actual_revenue_cents": 150000,
            "gross_profit_cents": 90000,
        }],
    )

    assert result.actual_revenue_cents == 150000
    assert result.gross_profit_cents == 90000
    assert result.actual_revenue_observed is True
    assert result.realized_gp_observed is True


def test_pattern_outcomes_learn_from_verified_events_only():
    result = calibrate_pattern_outcomes(
        [
            {
                "email": "jane.smith@acme.com",
                "person_name": "Jane Smith",
                "domain": "acme.com",
                "event_type": "delivered",
                "verified": True,
                "evidence_ref": "delivery:1",
            },
            {
                "email": "john.doe@acme.com",
                "person_name": "John Doe",
                "domain": "acme.com",
                "event_type": "reply_received",
                "verified": True,
                "evidence_ref": "reply:1",
            },
            {
                "email": "bad.guess@acme.com",
                "person_name": "Bad Guess",
                "domain": "acme.com",
                "event_type": "bounced",
                "verified": False,
                "evidence_ref": "guess:1",
            },
        ],
        domain="https://www.acme.com",
    )

    assert result.pattern == "first.last"
    assert result.verified_attempts == 2
    assert result.positive_events == 2
    assert result.negative_events == 0
    assert result.confidence_delta > 0
