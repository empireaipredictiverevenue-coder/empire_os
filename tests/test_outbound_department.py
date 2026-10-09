import copy

import pytest

from empire_os.outbound_department import (
    NEXT_ACTIONS,
    derive_relationship_state,
    plan_outbound_account,
    review_outbound_draft,
)


def account(**overrides):
    row = {
        "prospect_id": "p1",
        "review_id": "r1",
        "company_name": "Intercept Roofing & Construction",
        "company_name_verified": True,
        "decision_maker": "Trace Finch",
        "decision_title": "Owner",
        "contact_email": "info@interceptroofing.com",
        "contact_route": "company_routed",
        "person_bound": False,
        "buyer_review_status": "pending",
    }
    row.update(overrides)
    return row


def evidence(ref="e1", summary="Intercept Roofing & Construction publishes a commercial roofing service page."):
    return {
        "evidence_ref": ref,
        "summary": summary,
        "verified": True,
        "fresh": True,
        "account_bound": True,
    }


def sent(n, *, value_count=0):
    rows = []
    for i in range(n):
        rows.append({
            "event_type": "delivered",
            "delivered": True,
            "touch_number": i + 1,
            "touch_purpose": "value" if i >= n - value_count else "rapport",
            "evidence_refs": [f"old-{i+1}"],
        })
    return rows


def base_plan(history=(), ev=None, **kwargs):
    ev = [evidence()] if ev is None else ev
    return plan_outbound_account(account(), history=history, evidence=ev, **kwargs)


def safe_body(company="Intercept Roofing & Construction"):
    return (
        "Hi — this is for Trace Finch.\n\n"
        f"I noticed {company} publishes a dedicated commercial roofing service page. "
        "Thought it was worth flagging."
    )


def test_intercept_first_touch_is_rapport_first():
    plan = base_plan()
    assert plan["relationship_stage"] == "COLD_VERIFIED"
    assert plan["action_type"] == "DRAFT_RAPPORT_TOUCH"
    assert plan["cta_allowed"] is False
    assert plan["price_allowed"] is False
    assert plan["execution_authority"] == "none"
    assert plan["person_bound"] is False
    assert plan["contact_route"] == "company_routed"
    assert plan["company_name"] == "Intercept Roofing & Construction"


def test_no_evidence_researches_instead_of_fabricating():
    plan = base_plan(ev=[])
    assert plan["action_type"] == "RESEARCH"
    assert "fresh_unused_account_evidence" in plan["missing_evidence"]


def test_unverified_evidence_is_not_usable():
    row = evidence()
    row["verified"] = False
    plan = base_plan(ev=[row])
    assert plan["action_type"] == "RESEARCH"


def test_stale_evidence_is_not_usable():
    row = evidence()
    row["fresh"] = False
    plan = base_plan(ev=[row])
    assert plan["action_type"] == "RESEARCH"


def test_unbound_evidence_is_not_usable():
    row = evidence()
    row["account_bound"] = False
    plan = base_plan(ev=[row])
    assert plan["action_type"] == "RESEARCH"


def test_contradicted_evidence_is_not_usable():
    row = evidence()
    row["contradicted"] = True
    plan = base_plan(ev=[row])
    assert plan["action_type"] == "RESEARCH"


def test_company_routed_forces_non_person_bound_output():
    plan = base_plan()
    assert plan["contact_route"] == "company_routed"
    assert plan["person_bound"] is False


def test_company_routed_personhood_conflict_blocks():
    bad = account(person_bound=True)
    plan = plan_outbound_account(bad, evidence=[evidence()])
    assert plan["action_type"] == "BLOCK"
    assert "contact_route_personhood_conflict" in plan["missing_evidence"]


def test_role_inbox_personhood_conflict_blocks_even_if_route_claims_person_bound():
    bad = account(contact_route="person_bound", person_bound=True)
    plan = plan_outbound_account(bad, evidence=[evidence()])
    assert plan["action_type"] == "BLOCK"
    assert "role_inbox_personhood_conflict" in plan["missing_evidence"]


def test_suppression_outranks_nurture():
    plan = base_plan(
        history=sent(2),
        suppressions=[{"status": "suppressed"}],
    )
    assert plan["relationship_stage"] == "SUPPRESSED"
    assert plan["action_type"] == "SUPPRESS"


@pytest.mark.parametrize("classification", ["unsubscribe", "opt_out", "do_not_contact"])
def test_unsubscribe_variants_suppress(classification):
    plan = base_plan(replies=[{"reply_id": "x", "classification": classification}])
    assert plan["action_type"] == "SUPPRESS"


@pytest.mark.parametrize("classification", ["ooo", "out_of_office", "auto_reply"])
def test_ooo_variants_wait(classification):
    plan = base_plan(replies=[{"reply_id": "x", "classification": classification}])
    assert plan["action_type"] == "WAIT"


@pytest.mark.parametrize("classification", ["wrong_person", "referral", "not_the_right_person"])
def test_wrong_person_variants_research(classification):
    plan = base_plan(replies=[{"reply_id": "x", "classification": classification}])
    assert plan["action_type"] == "RESEARCH"


@pytest.mark.parametrize("classification", ["interest", "question", "objection", "pricing_question"])
def test_real_reply_stops_nurture_and_hands_to_closer(classification):
    plan = base_plan(replies=[{"reply_id": "x", "classification": classification}])
    assert plan["relationship_stage"] == "CONVERSATION"
    assert plan["action_type"] == "HANDOFF_TO_CLOSER"


def test_unknown_real_reply_stops_nurture_and_waits_for_classification():
    plan = base_plan(replies=[{"reply_id": "x", "classification": "other"}])
    assert plan["relationship_stage"] == "ENGAGED"
    assert plan["action_type"] == "WAIT"
    assert "reply_classification_review" in plan["missing_evidence"]


def test_bounce_does_not_fake_engagement():
    plan = base_plan(replies=[{"reply_id": "x", "classification": "bounce"}])
    assert plan["action_type"] == "DRAFT_RAPPORT_TOUCH"


def test_touch_two_requires_new_value():
    history = sent(1)
    plan = base_plan(history=history, ev=[evidence("e2", "Intercept Roofing & Construction added a project gallery.")])
    assert plan["relationship_stage"] == "RAPPORT_STARTED"
    assert plan["action_type"] == "DRAFT_VALUE_TOUCH"
    assert plan["evidence_refs"] == ["e2"]


def test_touch_three_is_nurture_not_hard_cta():
    history = sent(2, value_count=1)
    plan = base_plan(history=history, ev=[evidence("e3", "Intercept Roofing & Construction highlights commercial maintenance.")])
    assert plan["relationship_stage"] == "RAPPORT_BUILDING"
    assert plan["action_type"] == "DRAFT_NURTURE_TOUCH"
    assert plan["cta_allowed"] is False


def test_touch_four_can_be_soft_conversation_opener_after_verified_value_sequence():
    history = sent(3, value_count=2)
    plan = base_plan(history=history, ev=[evidence("e4", "Intercept Roofing & Construction publishes a Nashville service area.")])
    assert plan["relationship_stage"] == "VALUE_ESTABLISHED"
    assert plan["action_type"] == "DRAFT_SOFT_CONVERSATION_OPENER"
    assert plan["cta_allowed"] is True
    assert plan["execution_authority"] == "none"


def test_no_new_evidence_prevents_followup():
    history = sent(1)
    plan = base_plan(history=history, ev=[evidence("old-1")])
    assert plan["action_type"] == "RESEARCH"


@pytest.mark.parametrize(
    "body, blocker",
    [
        ("I hope this email finds you well. Intercept Roofing & Construction publishes a commercial roofing service page.", "GENERIC_OPENER"),
        ("Just reaching out because Intercept Roofing & Construction publishes a commercial roofing service page.", "GENERIC_OPENER"),
        ("Intercept Roofing & Construction can unlock growth with AI.", "AI_SLOP_PHRASE"),
        ("Intercept Roofing & Construction can leverage AI for game-changing results.", "AI_SLOP_PHRASE"),
        ("Intercept Roofing & Construction can 10x revenue.", "UNSUPPORTED_CLAIM"),
        ("As we discussed, Intercept Roofing & Construction publishes a commercial roofing service page.", "FAKE_FAMILIARITY"),
    ],
)
def test_hard_copy_blockers(body, blocker):
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=body, used_evidence_refs=["e1"],
    )
    assert blocker in review["blockers"]
    assert review["eligible"] is False


@pytest.mark.parametrize(
    "body",
    [
        safe_body() + "\n\nWant me to send it?",
        safe_body() + "\n\nCan I send the details?",
        safe_body() + "\n\nBook a meeting here.",
        safe_body() + "\n\nHere's my calendar.",
        safe_body() + "\n\nWorth a quick call?",
    ],
)
def test_first_touch_blocks_cta_meeting_calendar_and_call(body):
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=body, used_evidence_refs=["e1"],
    )
    assert "PREMATURE_CTA" in review["blockers"]


@pytest.mark.parametrize(
    "body",
    [
        safe_body() + "\n\nPricing starts at £499 per month.",
        safe_body() + "\n\nThe price is $1500.",
        safe_body() + "\n\nOur monthly fee is 999.",
    ],
)
def test_first_touch_blocks_pricing(body):
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=body, used_evidence_refs=["e1"],
    )
    assert "PREMATURE_PRICE" in review["blockers"]


def test_early_touch_requires_full_verified_company_name():
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="roofing",
        body="Hi — this is for Trace Finch.\n\nI noticed Intercept publishes a dedicated commercial roofing service page. Thought it was worth flagging.",
        used_evidence_refs=["e1"],
    )
    assert "UNVERIFIED_COMPANY_SHORTENING" in review["blockers"]


def test_company_routed_route_cannot_pretend_info_mailbox_is_trace():
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body="Hi Trace,\n\nIntercept Roofing & Construction publishes a dedicated commercial roofing service page. Thought it was worth flagging.",
        used_evidence_refs=["e1"],
    )
    assert "ROLE_INBOX_PERSONHOOD_CLAIM" in review["blockers"]


def test_company_routed_safe_routing_phrase_passes_personhood_gate():
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=safe_body(), used_evidence_refs=["e1"],
    )
    assert "ROLE_INBOX_PERSONHOOD_CLAIM" not in review["blockers"]


def test_missing_evidence_ref_blocks_personalization():
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=safe_body(), used_evidence_refs=[],
    )
    assert "EMPTY_PERSONALIZATION" in review["blockers"]


def test_unselected_evidence_ref_is_unsupported():
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=safe_body(), used_evidence_refs=["not-selected"],
    )
    assert "UNSUPPORTED_CLAIM" in review["blockers"]


def test_repeated_insight_is_blocked():
    history = [{"event_type": "delivered", "delivered": True, "evidence_refs": ["e1"]}]
    plan = base_plan(history=history, ev=[evidence("e2", "Intercept Roofing & Construction added a project gallery.")])
    mutated = dict(plan)
    mutated["evidence_refs"] = ["e1"]
    review = review_outbound_draft(
        account=account(), plan=mutated, subject="Intercept Roofing & Construction",
        body=safe_body(), used_evidence_refs=["e1"],
    )
    assert "REPEATED_INSIGHT" in review["blockers"]


def test_safe_first_touch_passes_copy_gate():
    plan = base_plan()
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=safe_body(), used_evidence_refs=["e1"],
    )
    assert review["eligible"] is True
    assert review["blockers"] == []
    assert review["execution_authority"] == "none"
    assert review["send_enabled"] is False


def test_soft_conversation_opener_allowed_only_after_value_established():
    history = sent(3, value_count=2)
    plan = base_plan(history=history, ev=[evidence("e4", "Intercept Roofing & Construction publishes a Nashville service area.")])
    body = (
        "Intercept Roofing & Construction also publishes a Nashville service area. "
        "If useful, happy to show you what we're seeing."
    )
    review = review_outbound_draft(
        account=account(), plan=plan, subject="Intercept Roofing & Construction",
        body=body, used_evidence_refs=["e4"],
    )
    assert plan["cta_allowed"] is True
    assert "PREMATURE_CTA" not in review["blockers"]


def test_astra_cannot_override_deterministic_gate():
    plan = base_plan(astra_recommendation="HANDOFF_TO_CLOSER")
    assert plan["action_type"] == "DRAFT_RAPPORT_TOUCH"
    assert plan["astra_director"]["recommendation_accepted"] is False
    assert plan["astra_director"]["can_grant_send_authority"] is False
    assert plan["execution_authority"] == "none"


def test_matching_astra_recommendation_is_advisory_only():
    plan = base_plan(astra_recommendation="DRAFT_RAPPORT_TOUCH")
    assert plan["astra_director"]["recommendation_accepted"] is True
    assert plan["execution_authority"] == "none"


def test_output_is_deterministic():
    a = base_plan()
    b = base_plan()
    assert a == b


def test_actions_are_bounded():
    assert set(NEXT_ACTIONS) == {
        "RESEARCH", "WAIT", "DRAFT_RAPPORT_TOUCH", "DRAFT_VALUE_TOUCH",
        "DRAFT_NURTURE_TOUCH", "DRAFT_SOFT_CONVERSATION_OPENER",
        "HANDOFF_TO_CLOSER", "SUPPRESS", "BLOCK",
    }


def test_planner_never_grants_terms_payment_or_revenue_authority():
    plan = base_plan()
    assert plan["commercial_terms_authority"] == "none"
    assert plan["payment_authority"] == "none"
    assert plan["revenue_recognition_authority"] == "none"
    assert plan["automated_nurture_allowed"] is False


def test_commercial_ready_never_becomes_a_sender():
    a = account(commercial_ready=True)
    plan = plan_outbound_account(a, evidence=[evidence()])
    assert plan["relationship_stage"] == "COMMERCIAL_READY"
    assert plan["action_type"] == "HANDOFF_TO_CLOSER"
    assert plan["execution_authority"] == "none"


def test_rejected_review_blocks():
    a = account(buyer_review_status="rejected")
    plan = plan_outbound_account(a, evidence=[evidence()])
    assert plan["action_type"] == "BLOCK"


def test_missing_verified_company_name_researches():
    a = account(company_name_verified=False)
    plan = plan_outbound_account(a, evidence=[evidence()])
    assert plan["action_type"] == "RESEARCH"
    assert "verified_company_name" in plan["missing_evidence"]


def test_relationship_state_is_process_evidence_not_open_tracking():
    assert derive_relationship_state(account(), history=sent(1)) == "RAPPORT_STARTED"
    assert derive_relationship_state(account(), history=sent(2, value_count=1)) == "RAPPORT_BUILDING"
    assert derive_relationship_state(account(), history=sent(3, value_count=2)) == "VALUE_ESTABLISHED"


def test_source_has_no_network_db_or_sender_dependencies():
    import inspect
    import empire_os.outbound_department as module

    source = inspect.getsource(module)
    for forbidden in ("requests.", "psycopg", "subprocess.", "smtplib", "socket.", "send_message("):
        assert forbidden not in source


def test_astra_wrapper_is_advisory_and_uses_outbound_gate():
    from empire_os.astra import decide_outbound_account

    plan = decide_outbound_account(
        account(),
        evidence=[evidence()],
        recommendation="HANDOFF_TO_CLOSER",
    )
    assert plan["action_type"] == "DRAFT_RAPPORT_TOUCH"
    assert plan["astra_director"]["recommendation_accepted"] is False
    assert plan["execution_authority"] == "none"

def test_canonical_positive_reply_hands_to_closer():
    plan = base_plan(replies=[{"reply_id": "x", "classification": "positive"}])
    assert plan["relationship_stage"] == "CONVERSATION"
    assert plan["action_type"] == "HANDOFF_TO_CLOSER"


def test_canonical_later_reply_stops_nurture_without_closer_handoff():
    plan = base_plan(replies=[{"reply_id": "x", "classification": "later"}])
    assert plan["relationship_stage"] == "ENGAGED"
    assert plan["action_type"] == "WAIT"
    assert plan["execution_authority"] == "none"


def test_canonical_negative_reply_stops_nurture_without_closer_handoff():
    plan = base_plan(replies=[{"reply_id": "x", "classification": "negative"}])
    assert plan["relationship_stage"] == "ENGAGED"
    assert plan["action_type"] == "WAIT"
    assert plan["execution_authority"] == "none"


def test_late_natural_reference_does_not_require_repeating_full_company_name():
    history = sent(3, value_count=2)
    plan = base_plan(
        history=history,
        ev=[evidence(
            "e4",
            "Intercept Roofing & Construction publishes a Nashville service area.",
        )],
    )
    review = review_outbound_draft(
        account=account(),
        plan=plan,
        subject="Nashville",
        body=(
            "I noticed your team also publishes a Nashville service area. "
            "Thought that was useful context."
        ),
        used_evidence_refs=["e4"],
    )
    assert "UNVERIFIED_COMPANY_SHORTENING" not in review["blockers"]
    assert "EMPTY_PERSONALIZATION" not in review["blockers"]


def test_late_unverified_short_company_name_is_still_blocked():
    history = sent(3, value_count=2)
    plan = base_plan(
        history=history,
        ev=[evidence(
            "e4",
            "Intercept Roofing & Construction publishes a Nashville service area.",
        )],
    )
    review = review_outbound_draft(
        account=account(),
        plan=plan,
        subject="Nashville",
        body=(
            "Intercept also publishes a Nashville service area. "
            "Thought that was useful context."
        ),
        used_evidence_refs=["e4"],
    )
    assert "UNVERIFIED_COMPANY_SHORTENING" in review["blockers"]


def test_late_verified_short_company_name_can_be_mirrored():
    history = sent(3, value_count=2)
    a = account(verified_company_short_names=["Intercept"])
    plan = plan_outbound_account(
        a,
        history=history,
        evidence=[evidence(
            "e4",
            "Intercept Roofing & Construction publishes a Nashville service area.",
        )],
    )
    review = review_outbound_draft(
        account=a,
        plan=plan,
        subject="Nashville",
        body=(
            "Intercept also publishes a Nashville service area. "
            "Thought that was useful context."
        ),
        used_evidence_refs=["e4"],
    )
    assert "UNVERIFIED_COMPANY_SHORTENING" not in review["blockers"]


@pytest.mark.parametrize(
    "cta",
    [
        "Book a meeting here.",
        "Schedule a demo.",
        "Here's my calendar.",
        "Would you be open to a quick call?",
        "Pick a time that works.",
        "I can do 30 minutes tomorrow.",
    ],
)
def test_value_established_still_blocks_hard_cta(cta):
    history = sent(3, value_count=2)
    plan = base_plan(
        history=history,
        ev=[evidence(
            "e4",
            "Intercept Roofing & Construction publishes a Nashville service area.",
        )],
    )
    body = (
        "Intercept Roofing & Construction also publishes a Nashville service area. "
        + cta
    )
    review = review_outbound_draft(
        account=account(),
        plan=plan,
        subject="Nashville",
        body=body,
        used_evidence_refs=["e4"],
    )
    assert plan["action_type"] == "DRAFT_SOFT_CONVERSATION_OPENER"
    assert plan["cta_allowed"] is True
    assert "PREMATURE_CTA" in review["blockers"]


@pytest.mark.parametrize(
    "cta",
    [
        "If useful, I can show you what we're seeing.",
        "Happy to show you what we're seeing if useful.",
        "If this is something you're actively looking at, I can show you what we're seeing.",
    ],
)
def test_value_established_allows_soft_conversation_openers(cta):
    history = sent(3, value_count=2)
    plan = base_plan(
        history=history,
        ev=[evidence(
            "e4",
            "Intercept Roofing & Construction publishes a Nashville service area.",
        )],
    )
    body = (
        "Intercept Roofing & Construction also publishes a Nashville service area. "
        + cta
    )
    review = review_outbound_draft(
        account=account(),
        plan=plan,
        subject="Nashville",
        body=body,
        used_evidence_refs=["e4"],
    )
    assert plan["action_type"] == "DRAFT_SOFT_CONVERSATION_OPENER"
    assert "PREMATURE_CTA" not in review["blockers"]
