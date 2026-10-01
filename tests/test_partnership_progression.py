import pytest

from empire_os.partnership_progression import (
    POSITIVE_STATES,
    derive_partnership_progression,
)


@pytest.mark.parametrize("state", POSITIVE_STATES)
def test_each_positive_state_requires_explicit_evidence(state):
    result = derive_partnership_progression({
        state.lower(): True,
        "evidence_refs": [f"evidence:{state.lower()}"],
    })

    assert result.state == state
    assert result.state_class == "positive"
    assert result.observed_positive_states == (state,)
    assert result.execution_authority == "none"
    assert result.outreach_authorized is False


def test_highest_explicit_positive_state_is_current_without_inference():
    result = derive_partnership_progression({
        "person_bound": True,
        "needs_discovered": True,
        "evidence_refs": ["contact:1", "reply:1"],
    })

    assert result.state == "NEEDS_DISCOVERED"
    assert result.observed_positive_states == (
        "PERSON_BOUND",
        "NEEDS_DISCOVERED",
    )
    assert "ENGAGED" not in result.observed_positive_states


def test_stop_has_highest_precedence():
    result = derive_partnership_progression({
        "engaged": True,
        "capacity_hold": True,
        "opt_out": True,
        "evidence_refs": ["reply:opt-out"],
    })

    assert result.state == "STOP"
    assert result.state_class == "negative"
    assert result.outreach_authorized is False


def test_no_fit_precedes_hold_and_positive():
    result = derive_partnership_progression({
        "commercial_partner": True,
        "capacity_hold": True,
        "negative_economics": True,
        "evidence_refs": ["economics:42"],
    })

    assert result.state == "NO_FIT"


def test_hold_requires_explicit_constraint():
    result = derive_partnership_progression({
        "engaged": True,
        "capacity_hold": True,
        "evidence_refs": ["reply:capacity-full"],
    })

    assert result.state == "HOLD"


def test_stalled_is_not_inferred_from_silence():
    result = derive_partnership_progression({
        "person_bound": True,
        "no_reply": True,
        "evidence_refs": ["contact:sent"],
    })

    assert result.state == "PERSON_BOUND"
    assert result.state != "STALLED"


def test_explicit_stalled_is_supported():
    result = derive_partnership_progression({
        "explicit_stalled": True,
        "evidence_refs": ["conversation:stalled"],
    })

    assert result.state == "STALLED"


def test_missing_evidence_reference_fails_closed_to_unknown():
    result = derive_partnership_progression({
        "engaged": True,
    })

    assert result.state == "UNKNOWN"
    assert result.blockers == ("evidence_refs_missing",)


def test_generic_score_does_not_create_partnership_state():
    result = derive_partnership_progression({
        "qualification_score": 99,
        "evidence_refs": ["qualification:99"],
    })

    assert result.state == "UNKNOWN"
    assert result.buyer_intent_inferred is False
    assert result.commercial_intent_inferred is False


def test_empty_input_is_unknown():
    result = derive_partnership_progression(None)

    assert result.state == "UNKNOWN"
    assert result.state_class == "unknown"
    assert result.execution_authority == "none"
