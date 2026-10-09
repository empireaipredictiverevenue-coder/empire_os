"""Offline commercial learning and authority boundary regressions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from empire_os.adaptive_outreach_optimizer import (
    EXPLORATION_FRACTION, MIN_DELIVERED_PER_ARM, SEGMENT_MIN_DELIVERED,
    _choose_arm, _bucket, build_performance_snapshot, segment_key,
)
from empire_os.conversation_value import build_first_touch_copy, build_followup_copy
from empire_os.conversation_recovery import build_conversation_recovery
from empire_os.outreach_message_optimizer import review_message
from empire_os.outcome_feedback import build_verified_outcome_feedback
from empire_os.reply_classifier import classify_reply_text
from test_cortex_learning_loop import _twin, _verified_outcome

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
PROOF = "your public profile shows 4.8★ across 198 reviews"
TRIGGER = dict(summary="your public update lists a new Wichita location",
               evidence_ref="public:update:1", observed_at=NOW.isoformat(),
               signal_type="commercial_change", confidence=0.9, observed_inferred="observed")
EVIDENCE = dict(business_name="Kihle Roofing", niche="roofing", metro="Wichita",
                specific_proof=PROOF)


def quality(evidence=None, body=None):
    return review_message(subject="one thing on Kihle", body=body or (
        f"Saw {PROOF}. I can send a one-page view for Kihle Roofing with "
        "the public evidence and proposed checks for your team. Want me to send it?"
    ), cta="Want me to send it?", evidence=evidence or EVIDENCE, now=NOW)


def record(label="positive"):
    return dict(delivered=True, classification=label, tenant_id="tenant-A",
                fulfilment_order_id="order-1", metadata={"adaptive_outreach": {
                    "exact_segment": "offer|roofing|owner", "subject_arm": "a", "body_arm": "a"}})


def counts(records):
    return build_performance_snapshot(records, generated_at=NOW.isoformat())["segments"]["__global__"]["body_arms"]["a"]


def verified_feedback():
    twin = _twin()
    twin["tenant_id"] = "tenant-A"
    twin["outcomes"]["history"] = [dict(_verified_outcome(), tenant_id="tenant-A", evidence={})]
    twin["commercial"]["payment_evidence"] = [dict(tenant_id="tenant-A", fulfilment_order_id="order-1",
        transaction_hash="offline-proof", verified_at="2026-09-22T11:00:00Z")]
    twin["commercial"]["fulfilment_orders"] = [dict(id="order-1", tenant_id="tenant-A", delivered_at="2026-09-22T10:00:00Z")]
    twin["revenue_truth"].update(tenant_id="tenant-A", fulfilment_order_id="order-1", actual_revenue=True,
        recognized_revenue_cents=1000, recognized_at="2026-09-22T13:00:00Z",
        evidence_refs=["canonical:commercial_events:revenue-1"])
    return build_verified_outcome_feedback(twin, tenant_id="tenant-A", as_of=NOW)


def test_perfect_structure_is_not_elite_persuasion_or_trigger_evidence():
    result = quality()
    assert result["structural_score"] >= 90
    assert result["commercial_persuasion_score"] <= 74
    assert result["why_now_state"] == "UNKNOWN/MISSING"
    assert result["evidence_backing"] == "PROOF_BACKED"
    assert result["experiment_eligible"] is True
    assert result["dimensions"]["why_now_quality"] == 0
    assert all(value == "UNKNOWN" for value in result["alignment"].values())


def test_fresh_trigger_preserves_provenance_and_improves_timing_quality():
    evidence = dict(EVIDENCE, why_now=TRIGGER)
    result = quality(evidence, f"Saw {TRIGGER['summary']}. " + quality_body())
    assert result["evidence_backing"] == "PROOF_AND_TRIGGER_BACKED"
    assert result["dimensions"]["why_now_quality"] > quality()["dimensions"]["why_now_quality"]
    assert result["why_now"]["confidence"] == 0.9
    assert result["why_now"]["observed_inferred"] == "observed"
    assert result["why_now"]["freshness"]["age_hours"] == 0


def quality_body():
    return f"Saw {PROOF}. I can send the evidence and proposed checks for your team. Want me to send it?"


@pytest.mark.parametrize("change", ["stale", "future", "missing_ref", "missing_date"])
def test_invalid_trigger_fails_closed(change):
    trigger = dict(TRIGGER)
    if change == "stale": trigger["observed_at"] = (NOW - timedelta(days=31)).isoformat()
    if change == "future": trigger["observed_at"] = (NOW + timedelta(hours=1)).isoformat()
    if change == "missing_ref": trigger.pop("evidence_ref")
    if change == "missing_date": trigger.pop("observed_at")
    result = quality(dict(EVIDENCE, why_now=trigger))
    assert result["why_now"] is None
    assert result["evidence_backing"] == "PROOF_BACKED"
    copy = build_first_touch_copy(dict(contact_name="Clay Winter", evidence=dict(EVIDENCE, why_now=trigger)), now=NOW)
    assert TRIGGER["summary"] not in copy.body


def test_alignment_requires_evidence_and_contradiction_blocks_experiments():
    evidence = dict(EVIDENCE, message_alignment={"offer_problem_fit": True})
    assert quality(evidence)["alignment"]["offer_problem_fit"] == "UNKNOWN"
    evidence["message_alignment"] = {"offer_problem_fit": {"supported": True, "evidence_ref": "qualification:1"}}
    assert quality(evidence)["alignment"]["offer_problem_fit"] == "SUPPORTED"
    evidence["message_alignment"]["cta_offer_fit"] = False
    assert quality(evidence)["experiment_eligible"] is False


@pytest.mark.parametrize("urgent", ["act now", "urgent", "you need", "ready to buy", "budget available"])
def test_invented_urgency_or_intent_never_enters_experiments(urgent):
    result = quality(dict(EVIDENCE, why_now=TRIGGER), quality_body() + f" {urgent}")
    assert result["experiment_eligible"] is False
    assert result["commercial_persuasion_score"] == 0


@pytest.mark.parametrize("label", ["question", "objection", "later", "positive"])
def test_engagement_and_positive_intent_are_not_revenue(label):
    row = record(label)
    row.update(recognized_revenue=True, expected_revenue_cents=100000, verified_payment=True)
    result = counts([row])
    assert result["commercial_replies"] == 1
    assert result["positive_replies"] == int(label == "positive")
    assert result["recognized_revenue"] == result["verified_payment"] == 0
    assert result["qualified_conversation"] == 0


def test_unsubscribe_is_still_hard_suppression_and_not_engagement():
    assert classify_reply_text("Interested but unsubscribe me")["classification"] == "unsubscribe"
    result = counts([record("unsubscribe"), record("negative")])
    assert result["unsubscribes"] == result["negative_replies"] == 1
    assert result["commercial_replies"] == 0
    recovery = build_conversation_recovery([dict(id="i1", prospect_id="p1", status="suppressed",
        metadata={"candidate_evidence": EVIDENCE})], {"i1": NOW - timedelta(hours=200)}, {}, now=NOW)
    assert recovery["items"][0]["recovery_reason"] == "suppressed_after_delivery"


def test_revenue_learning_requires_existing_verified_gate_and_order_attribution():
    row = record()
    row["verified_outcome_feedback"] = verified_feedback()
    result = counts([row])
    assert result["recognized_revenue"] == result["verified_payment"] == result["fulfilled"] == 1
    for change in ("wrong_tenant", "wrong_order", "unverified", "forecast", "missing_payment"):
        bad = deepcopy(row)
        if change == "wrong_tenant": bad["tenant_id"] = "tenant-B"
        if change == "wrong_order": bad["fulfilment_order_id"] = "order-other"
        if change == "unverified": bad["verified_outcome_feedback"]["verified_outcome"] = False
        if change == "forecast": bad["verified_outcome_feedback"]["cortex_packet"]["label"]["forecast_derived"] = True
        if change == "missing_payment": bad["verified_outcome_feedback"]["cortex_packet"]["verification"]["payment_verified"] = False
        assert counts([bad])["recognized_revenue"] == 0


def test_sparse_segments_and_sparse_arms_cannot_claim_winners():
    snapshot = build_performance_snapshot([record()] * 7, generated_at=NOW.isoformat())
    assert snapshot["winner_claim_allowed"] is False
    snapshot = {"segments": {"__global__": {"delivered": 16, "body_arms": {
        "a": {"delivered": 8, "commercial_replies": 1},
        "b": {"delivered": 8, "commercial_replies": 2},
        "sparse": {"delivered": 1, "commercial_replies": 100}}}}}
    key = next(str(i) for i in range(1000) if _bucket(f"explore:body_arms:{i}") >= 2000)
    arm, meta = _choose_arm(("a", "b", "sparse"), assignment_key=key, arm_type="body_arms", snapshot=snapshot, exact_segment="sparse-segment")
    assert arm == "b" and meta["segment"] == "__global__"
    explore = next(str(i) for i in range(1000) if _bucket(f"explore:body_arms:{i}") < 2000)
    _, meta = _choose_arm(("a", "b", "sparse"), assignment_key=explore, arm_type="body_arms", snapshot=snapshot, exact_segment="sparse-segment")
    assert meta["exploration"] is True
    assert (MIN_DELIVERED_PER_ARM, SEGMENT_MIN_DELIVERED, EXPLORATION_FRACTION) == (8, 16, 0.20)


def test_learning_dimensions_use_only_supplied_context():
    base = segment_key(offer_key="map", niche="roofing", decision_role="owner")
    assert segment_key(offer_key="map", niche="roofing", decision_role="owner", dimensions={"trigger_class": "hiring"}) == base + "|trigger_class=hiring"


def test_followups_propose_checks_without_fabricating_completed_work_or_proof():
    row = dict(candidate_evidence={k: EVIDENCE[k] for k in ("business_name", "niche", "metro")})
    first = build_followup_copy(row, step=1, now=NOW)
    final = build_followup_copy(row, step=2, now=NOW)
    assert first.specific_proof is first.why_now_summary is None
    assert "I pulled" not in first.body
    assert "propose checking" in first.body
    assert first.body != final.body and "Closing the loop" in final.body
    with pytest.raises(ValueError, match="conversation context missing"):
        build_followup_copy({"candidate_evidence": {}}, step=1, now=NOW)
    recovery = build_conversation_recovery([dict(id="i", prospect_id="p", status="delivered", metadata={})],
        {"i": NOW - timedelta(hours=200)}, {}, now=NOW)
    assert recovery["items"][0]["recovery_reason"] == "missing_canonical_context"


def test_no_score_grants_execution_authority():
    result = quality()
    assert result["send_enabled"] is False and result["execution_authority"] == "none"
    snapshot = build_performance_snapshot([record()] * 100, generated_at=NOW.isoformat())
    assert snapshot["execution_authority"] == "none"
