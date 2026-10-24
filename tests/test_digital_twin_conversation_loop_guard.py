"""Original Digital Twin deterministic anti-loop / progress contract."""
from __future__ import annotations

import pytest

from empire_os.digital_twin_conversation_rehearsal import (
    review_synthetic_conversation_loop,
    rehearse_conversation,
)
from scripts.rehearse_prime_conversation_digital_twin_20261024 import default_scenarios


def turn(actor: str, text: str) -> dict:
    return {
        "actor": "FICTIONAL_" + actor + "_TWIN",
        "text": text,
        "real_person": False,
        "simulated": True,
    }


def buyer(text: str) -> dict:
    return turn("BUYER", text)


def seller(text: str) -> dict:
    return turn("SELLER", text)


def test_no_loop_observed_does_not_claim_validated_customer():
    packet = review_synthetic_conversation_loop([
        buyer("How much does it cost?"),
        seller("I can explain the approved price basis."),
        buyer("Thank you for explaining."),
    ])
    assert packet["status"] == "NO_LOOP_OBSERVED_IN_BOUNDED_PREFIX"
    assert packet["stalled_needs_review"] is False
    assert packet["max_synthetic_turns"] == 5
    assert packet["no_autonomous_continuation_authorized"] is True
    assert packet["real_world_predictive_accuracy"] is None
    assert packet["real_messages_sent"] is False
    assert packet["execution_authority"] == "none"


def test_exact_repeated_buyer_turn_stalls_before_inference_can_continue():
    packet = review_synthetic_conversation_loop([
        buyer("What is the price?"),
        seller("Please review the verified pricing basis."),
        buyer("What is the price?"),
    ])
    assert packet["status"] == "REPEATED_TURN_STALLED_NEEDS_REVIEW"
    assert packet["stalled_needs_review"] is True


def test_punctuation_case_changes_do_not_evade_loop_guard():
    packet = review_synthetic_conversation_loop([
        buyer("WHAT is the PRICE?!"),
        seller("We can discuss approved terms."),
        buyer("What is the price."),
    ])
    assert packet["status"] == "REPEATED_TURN_STALLED_NEEDS_REVIEW"


def test_repeating_the_same_seller_pitch_is_a_stall():
    packet = review_synthetic_conversation_loop([
        buyer("Could you show proof?"),
        seller("Here are the verified limitations."),
        buyer("Can you clarify the references?"),
        seller("Here are the verified limitations."),
    ])
    assert packet["status"] == "REPEATED_TURN_STALLED_NEEDS_REVIEW"


def test_simulated_optout_prevents_any_subsequent_seller_message():
    packet = review_synthetic_conversation_loop([
        buyer("Please unsubscribe me."),
        seller("But our offer is important."),
    ])
    assert packet["status"] == "POST_STOP_MESSAGE_HOLD"
    assert packet["stalled_needs_review"] is True
    assert packet["real_messages_sent"] is False


def test_immediate_optout_is_terminal_not_a_repeated_reply_request():
    packet = review_synthetic_conversation_loop([buyer("Do not contact me again.")])
    assert packet["status"] == "SIMULATED_STOP_NO_FOLLOWUP"
    assert packet["stalled_needs_review"] is False
    assert packet["no_autonomous_continuation_authorized"] is True


def test_refusal_after_answer_blocks_followup():
    packet = review_synthetic_conversation_loop([
        buyer("How much is it?"),
        seller("I can send verified pricing terms."),
        buyer("No thanks. Not interested."),
        seller("We will try again anyway."),
    ])
    assert packet["status"] == "POST_STOP_MESSAGE_HOLD"


def test_turn_budget_is_strict_and_not_silent_rollover():
    texts = [
        buyer("What is included?"),
        seller("First, these are the defined deliverables."),
        buyer("How do I obtain them?"),
        seller("By following the documented process."),
        buyer("Are refunds available?"),
        seller("Another marketing followup."),
    ]
    packet = review_synthetic_conversation_loop(texts)
    assert packet["status"] == "TURN_BUDGET_EXCEEDED_HOLD"
    assert packet["inspected_synthetic_turn_count"] == 6
    assert packet["stalled_needs_review"] is True


def test_quoted_history_unsubscribe_does_not_invent_current_optout():
    quoted = (
        "How much is the service?\n"
        "On Wed, 14 Oct 2026, Fictional Sender wrote:\n"
        "Please unsubscribe me."
    )
    packet = review_synthetic_conversation_loop([
        buyer(quoted),
        seller("Only verified scope and pricing, not invented promises."),
    ])
    assert packet["status"] == "NO_LOOP_OBSERVED_IN_BOUNDED_PREFIX"


def test_current_optout_cannot_be_dismissed_by_quoted_sales_question():
    quoted = (
        "Stop contacting me.\n"
        "On Wed, 14 Oct 2026, Fictional Sender wrote:\n"
        "What is your price?"
    )
    packet = review_synthetic_conversation_loop([buyer(quoted), seller("New offer")])
    assert packet["status"] == "POST_STOP_MESSAGE_HOLD"


@pytest.mark.parametrize("turn_change", [
    {"real_person": True},
    {"actor": "LIVE_CLIENT"},
    {"simulated": False},
    {"private_email": "private@example.test"},
    {"text": ""},
])
def test_invalid_or_private_turn_contract_causes_hold(turn_change):
    first = buyer("What are the pricing terms?")
    first.update(turn_change)
    packet = review_synthetic_conversation_loop([first])
    assert packet["status"] == "UNTRUSTED_SYNTHETIC_TURN_HOLD"
    assert packet["stalled_needs_review"] is True
    assert "private@example.test" not in str(packet)


def test_source_can_be_unknown_without_ever_running_a_model():
    packet = review_synthetic_conversation_loop([])
    assert packet["status"] == "NO_SYNTHETIC_TURNS"
    assert packet["inspected_synthetic_turn_count"] == 0
    assert packet["real_world_predictive_accuracy"] is None


@pytest.mark.parametrize("max_turns", [0, 6, -1, True, "five"])
def test_unbounded_turn_config_rejected(max_turns):
    with pytest.raises(ValueError, match="bounded_original_synthetic_watchdog"):
        review_synthetic_conversation_loop([buyer("How much?")], max_turns=max_turns)


def test_watchdog_is_in_actual_original_rehearsal_output():
    for scenario in default_scenarios():
        output = rehearse_conversation(scenario, show_dialogue=True)
        guard = output["synthetic_loop_guard"]
        assert guard["stalled_needs_review"] is False
        assert guard["real_messages_sent"] is False
        assert output["scenario_contract_pass"] is True
        if scenario.scenario_id == "explicit_optout":
            assert guard["status"] == "SIMULATED_STOP_NO_FOLLOWUP"


def test_loop_guard_does_not_grant_sending_or_training_even_for_positive_dialogue():
    output = rehearse_conversation(default_scenarios()[0])
    assert output["synthetic_loop_guard"]["execution_authority"] == "none"
    assert output["real_customer_objection_resolved"] is None
    assert output["model_weight_mutation"] is False
    assert output["real_messages_sent"] is False
