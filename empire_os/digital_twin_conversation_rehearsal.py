"""Original Digital Twin Phase 14: two-sided fictional conversation rehearsal.

Deterministic scenario actors, not two autonomous deployed AI agents or a model.
Shares original PRIME objection cues and state transitions. Never fabricates
original owner receipts, real people, sales, revenue, or sending rights. The
simulated buyer's scripted confirmation is NOT evidence of customer success.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from empire_os.rapport_intent_cta import _buyer_text
from empire_os.prime_conversation_objection_shadow import (
    CUES, PRIORITY, NO_CONTACT, REFUSAL, NO_PRICE_OBJECTION,
)
from empire_os.prime_objection_lifecycle_shadow import (
    advance_objection_state, CATEGORIES,
)

SCHEMA = "empire.digital_twin.conversation_rehearsal.v1"
SUMMARY_SCHEMA = "empire.prime.conversation_twin_synthetic_status.v1"
MAX_SCENARIOS = 24
MAX_DIALOGUE_TURNS = 5
REACTIONS = frozenset({
    "CONFIRM_RESOLVED", "STILL_CONCERNED", "REOPEN_AFTER_CONFIRM",
    "SILENCE", "DECLINE", "OPT_OUT",
})
SELLER_SCRIPTS = {
    "PRICE_OR_BUDGET_QUESTION":
        "I can explain the written pricing basis, but I won't quote a fee until the exact scope and approved terms are verified.",
    "TRUST_OR_PROOF_QUESTION":
        "I can provide verifiable evidence and its limitations; I cannot guarantee an outcome.",
    "TIMING_OR_CAPACITY_CONCERN":
        "Understood. I will respect your timing and won't follow up without permission.",
    "DECISION_AUTHORITY_QUESTION":
        "I can provide an accurate written summary for your team's internal review.",
    "SCOPE_OR_FIT_QUESTION":
        "I can outline the exact deliverables, exclusions, and items that still require verification.",
    "INTEGRATION_OR_IMPLEMENTATION_CONCERN":
        "I can outline the onboarding steps and dependencies, clearly marking unverified integrations.",
    "PRIVACY_OR_COMPLIANCE_CONCERN":
        "I can refer you to approved privacy, security, retention and consent terms. I won't guess.",
    "ATTRIBUTION_OR_DELIVERY_CONCERN":
        "I will distinguish technical routing from independently connected calls and paid-delivery evidence.",
}
UNSAFE_CLAIM = re.compile(
    r"\b(?:guaranteed (?:profits?|sales?|results?|conversions?)|"
    r"100\s*% (?:guaranteed|success|conversion)|"
    r"we (?:know|understand) (?:your|their) hidden (?:feelings|thoughts)|"
    r"ignore (?:their|your|the) opt[ -]?out|"
    r"send (?:them|you) messages? (?:anyway|regardless)|"
    r"we (?:already )?(?:made|received) (?:a )?payment)\b", re.I,
)
REACTION_TEXT = {
    "CONFIRM_RESOLVED": "That explanation answers my specific concern. Thank you.",
    "STILL_CONCERNED": "I still have the same concern. The details are not clear.",
    "REOPEN_AFTER_CONFIRM": "Actually, I still need more detail about that concern.",
    "DECLINE": "No thanks. I am not interested.",
    "OPT_OUT": "Please unsubscribe me. Do not contact me again.",
}


@dataclass(frozen=True)
class SyntheticConversationScenario:
    scenario_id: str
    buyer_opening: str
    expected_first_objection_code: str | None
    buyer_reaction: str
    expected_final_state: str
    seller_response_override: str | None = None

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,55}", self.scenario_id):
            raise ValueError("bounded_fictional_scenario_key_required")
        if (type(self.buyer_opening) is not str
            or not 1 <= len(self.buyer_opening) <= 420
            or "@" in self.buyer_opening or "http" in self.buyer_opening.lower()):
            raise ValueError("fictional_bounded_buyer_utterance_required")
        if self.expected_first_objection_code is not None and (
            self.expected_first_objection_code not in CATEGORIES
        ):
            raise ValueError("known_original_objection_code_required")
        if self.buyer_reaction not in REACTIONS:
            raise ValueError("known_synthetic_buyer_reaction_required")
        if self.expected_final_state not in {
            "PERSON_REPORTED_RESOLVED_NOT_PROVIDER_VERIFIED", "REOPENED",
            "ANSWERED_AWAITING_CONFIRMATION", "SIMULATED_DECLINED",
            "SIMULATED_OPTED_OUT", "NO_OBJECTION_OBSERVED",
            "SELLER_RESPONSE_POLICY_HELD",
        }:
            raise ValueError("expected_simulated_terminal_state_required")
        if self.seller_response_override is not None and (
            type(self.seller_response_override) is not str
            or not 1 <= len(self.seller_response_override) <= 500
        ):
            raise ValueError("bounded_synthetic_override_required")


def _first_objection(utterance: str) -> str | None:
    body = _buyer_text(utterance)
    matched = set()
    for code, pattern, _ in CUES:
        if re.search(pattern, body, re.I):
            if code == "PRICE_OR_BUDGET_QUESTION" and NO_PRICE_OBJECTION.search(body):
                continue
            matched.add(code)
    return next((code for code in PRIORITY if code in matched), None)


def _synthetic_dialogue(
    s: SyntheticConversationScenario,
) -> tuple[tuple[dict[str, Any], ...], str | None, str, tuple[str, ...], bool]:
    first = _buyer_text(s.buyer_opening)
    transcript: list[dict[str, Any]] = [{
        "actor": "FICTIONAL_BUYER_TWIN", "text": first,
        "real_person": False, "simulated": True,
    }]
    objection = _first_objection(first)
    states: dict[str, str] = {}
    if NO_CONTACT.search(first) or REFUSAL.search(first):
        status = ("SIMULATED_OPTED_OUT" if NO_CONTACT.search(first)
                  else "SIMULATED_DECLINED")
        return tuple(transcript), objection, status, (), False
    if objection is None:
        return tuple(transcript), objection, "NO_OBJECTION_OBSERVED", (), False
    states = advance_objection_state(
        states, kind="PERSON_STATED_CONCERN", concern=objection,
    )
    reply = s.seller_response_override or SELLER_SCRIPTS[objection]
    # Only exactly vetted scripts are permitted as simulated seller actions.
    if (s.seller_response_override is not None
        or UNSAFE_CLAIM.search(reply) is not None
        or reply != SELLER_SCRIPTS[objection]):
        return tuple(transcript), objection, "SELLER_RESPONSE_POLICY_HELD", (
            "unapproved_or_unsupported_seller_claim_refused",
        ), False
    transcript.append({
        "actor": "FICTIONAL_SELLER_TWIN", "text": reply,
        "real_person": False, "simulated": True,
    })
    states = advance_objection_state(
        states, kind="HUMAN_EXPLANATION_SENT", concern=objection,
    )
    if s.buyer_reaction == "SILENCE":
        return tuple(transcript), objection, states[objection], (), True
    response_text = REACTION_TEXT[s.buyer_reaction]
    if s.buyer_reaction == "REOPEN_AFTER_CONFIRM":
        transcript.append({
            "actor": "FICTIONAL_BUYER_TWIN",
            "text": REACTION_TEXT["CONFIRM_RESOLVED"],
            "real_person": False, "simulated": True,
        })
        states = advance_objection_state(
            states, kind="PERSON_EXPLICITLY_CONFIRMED_RESOLVED", concern=objection,
        )
    transcript.append({
        "actor": "FICTIONAL_BUYER_TWIN", "text": response_text,
        "real_person": False, "simulated": True,
    })
    if s.buyer_reaction == "CONFIRM_RESOLVED":
        states = advance_objection_state(
            states, kind="PERSON_EXPLICITLY_CONFIRMED_RESOLVED", concern=objection,
        )
    elif s.buyer_reaction in ("STILL_CONCERNED", "REOPEN_AFTER_CONFIRM"):
        states = advance_objection_state(
            states, kind="PERSON_STILL_CONCERNED", concern=objection,
        )
    elif s.buyer_reaction in ("DECLINE", "OPT_OUT"):
        status = ("SIMULATED_OPTED_OUT" if s.buyer_reaction == "OPT_OUT"
                  else "SIMULATED_DECLINED")
        return tuple(transcript), objection, status, (), True
    if len(transcript) > MAX_DIALOGUE_TURNS:
        raise ValueError("bounded_synthetic_turn_limit")
    return tuple(transcript), objection, states[objection], (), True


def rehearse_conversation(
    scenario: SyntheticConversationScenario, *, show_dialogue: bool = False,
) -> dict[str, Any]:
    """Execute two fictional, deterministic turns + scripted reaction."""
    if type(scenario) is not SyntheticConversationScenario:
        raise ValueError("original_fictional_conversation_scenario_required")
    scenario.validate()
    if type(show_dialogue) is not bool:
        raise ValueError("synthetic_transcript_view_boolean_required")
    dialogue, detected, actual_state, blockers, seller_acted = _synthetic_dialogue(scenario)
    pass_contract = (
        detected == scenario.expected_first_objection_code
        and actual_state == scenario.expected_final_state
        and (actual_state != "SELLER_RESPONSE_POLICY_HELD" or not seller_acted)
    )
    return {
        "schema_version": SCHEMA,
        "mode": "SIMULATION",
        "scenario_id": scenario.scenario_id,
        "buyer_twin": "FICTIONAL_SCRIPTED_BUYER",
        "seller_twin": "EXISTING_PRIME_OBJECTION_RULE_POLICY",
        "scripted_not_generatively_autonomous": True,
        "scenario_contract_pass": pass_contract,
        "detected_original_objection_code": detected,
        "simulated_final_state": actual_state,
        "simulated_seller_reply_generated": seller_acted,
        "scenario_assertion_blockers": list(blockers),
        "simulated_dialogue": list(dialogue) if show_dialogue else None,
        "simulated_turn_count": len(dialogue),
        "simulation_only": True,
        "actual_revenue": False,
        "real_world_predictive_accuracy": None,
        "real_customer_objection_resolved": None,
        "verified_buyer_conversion_count": None,
        "recognized_revenue_cents": None,
        "model_weight_mutation": False,
        "provider_or_tenant_authenticated": False,
        "real_messages_sent": False,
        "crm_writes": False,
        "empiredb_writes": False,
        "trading_executed": False,
        "execution_authority": "none",
    }


def run_conversation_twin_gauntlet(
    scenarios: Sequence[SyntheticConversationScenario], *, show_dialogue: bool = False,
) -> dict[str, Any]:
    if type(scenarios) not in (list, tuple) or not 1 <= len(scenarios) <= MAX_SCENARIOS:
        raise ValueError("bounded_synthetic_scenario_batch_required")
    seen: set[str] = set()
    reviewed = []
    for scenario in scenarios:
        item = rehearse_conversation(scenario, show_dialogue=show_dialogue)
        if item["scenario_id"] in seen:
            raise ValueError("duplicate_synthetic_scenario_refused")
        seen.add(item["scenario_id"])
        reviewed.append(item)
    passes = sum(1 for item in reviewed if item["scenario_contract_pass"])
    return {
        "schema_version": "empire.digital_twin.conversation_gauntlet.v1",
        "mode": "SIMULATION",
        "scenario_count": len(reviewed),
        "scenario_contract_pass_count": passes,
        "scenario_contract_fail_count": len(reviewed) - passes,
        "all_scenario_contracts_passed": passes == len(reviewed),
        "scenarios": reviewed,
        "synthetic_scenarios_are_not_real_world_validation": True,
        "two_agents_autonomously_generating_replies": False,
        "simulation_only": True,
        "actual_revenue": False,
        "real_world_predictive_accuracy": None,
        "verified_buyer_conversion_count": None,
        "recognized_revenue_cents": None,
        "outbound_sent": False,
        "model_weight_mutation": False,
        "crm_writes": False,
        "empiredb_writes": False,
        "execution_authority": "none",
    }


def founder_conversation_twin_status(review: Mapping[str, Any] | None) -> dict[str, Any]:
    """Strict coarse bridge, no simulated conversational transcript."""
    if review is None:
        return {
            "schema_version": SUMMARY_SCHEMA, "mode": "SIMULATION",
            "status": "NOT_RUN", "scenario_contract_tests_passed": None,
            "real_world_predictive_accuracy": None, "actual_revenue": False,
            "execution_authority": "none",
        }
    if (type(review) is not dict
        or review.get("schema_version") != "empire.digital_twin.conversation_gauntlet.v1"
        or review.get("mode") != "SIMULATION"
        or review.get("simulation_only") is not True
        or review.get("actual_revenue") is not False
        or review.get("real_world_predictive_accuracy") is not None
        or review.get("verified_buyer_conversion_count") is not None
        or review.get("recognized_revenue_cents") is not None
        or review.get("outbound_sent") is not False
        or review.get("model_weight_mutation") is not False
        or review.get("crm_writes") is not False
        or review.get("empiredb_writes") is not False
        or review.get("execution_authority") != "none"
        or review.get("two_agents_autonomously_generating_replies") is not False
        or review.get("synthetic_scenarios_are_not_real_world_validation") is not True):
        raise ValueError("untrusted_conversation_digital_twin_summary_refused")
    tests = review.get("scenario_count")
    passed = review.get("scenario_contract_pass_count")
    failed = review.get("scenario_contract_fail_count")
    if (type(tests) is not int or not 1 <= tests <= MAX_SCENARIOS
        or type(passed) is not int or type(failed) is not int
        or passed < 0 or failed < 0 or passed + failed != tests
        or review.get("all_scenario_contracts_passed") is not (failed == 0)):
        raise ValueError("inconsistent_conversation_twin_scenario_counts")
    scenario_rows = review.get("scenarios")
    if (type(scenario_rows) is not list or len(scenario_rows) != tests
        or any(type(item) is not dict
               or item.get("schema_version") != SCHEMA
               or item.get("mode") != "SIMULATION"
               or item.get("simulation_only") is not True
               or item.get("actual_revenue") is not False
               or item.get("provider_or_tenant_authenticated") is not False
               or item.get("real_messages_sent") is not False
               or item.get("verified_buyer_conversion_count") is not None
               or item.get("recognized_revenue_cents") is not None
               or item.get("execution_authority") != "none"
               or type(item.get("scenario_contract_pass")) is not bool
               for item in scenario_rows)
        or passed != sum(1 for item in scenario_rows if item["scenario_contract_pass"])
        or len({item.get("scenario_id") for item in scenario_rows}) != tests):
        raise ValueError("untrusted_individual_synthetic_scenario_receipts")
    return {
        "schema_version": SUMMARY_SCHEMA,
        "mode": "SIMULATION",
        "status": "SCENARIO_CONTRACTS_PASSED" if failed == 0 else "SCENARIO_CONTRACT_FAILURES",
        "scenario_count": tests,
        "scenario_contract_pass_count": passed,
        "scenario_contract_fail_count": failed,
        "scenario_contract_tests_passed": failed == 0,
        "real_world_predictive_accuracy": None,
        "actual_revenue": False,
        "execution_authority": "none",
    }
