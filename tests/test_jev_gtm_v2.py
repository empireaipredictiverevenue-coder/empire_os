"""Acceptance tests for JEV GTM V2 evidence and commercial authority."""
from datetime import datetime, timedelta, timezone
import copy

import pytest

from empire_os.jev_gtm_v2 import build_jev_gtm_decision, review_gtm_signals
from empire_os.typed_decision_batch import (
    DecisionBatchRequestV2, DecisionBatchResultV2, DecisionQuestionV2,
)

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


def account(**changes):
    row = {
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "opportunity_key": "op:1",
        "entity_verified": True,
        "tenant_binding_verified": True,
        "business_name": "North Roof",
        "description": "roofing contractor hiring for growth and expansion",
        "target_buyer_pools": ["local_and_smb_buyers"],
        "target_product_codes": ["managed_service"],
        "first_party_people": [{"title": "owner"}],
    }
    row.update(changes)
    return row


def signal(**changes):
    row = {
        "signal_id": "signal:1",
        "signal_type": "hiring",
        "source_id": "jobs:source",
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "truth_class": "OBSERVED",
        "observed_at": NOW.isoformat(),
        "evidence_refs": ["evidence:job:1"],
    }
    row.update(changes)
    return row


def run(**changes):
    params = {
        "account": account(),
        "signals": [signal()],
        "as_of": NOW,
        "outreach": {"suppression_checked": True},
    }
    params.update(changes)
    return build_jev_gtm_decision(**params)


def test_genuine_evidenced_signal_is_review_only():
    result = run()
    assert result["action"] == "OUTREACH_REVIEW"
    assert result["icp"]["score_type"] == "DETERMINISTIC_HEURISTIC_NOT_PROBABILITY"
    assert result["prediction_of_purchase_probability"] is None
    assert result["outbound_approved"] is False
    assert result["contact_permission_granted"] is False
    assert result["execution_authority"] == "none"
    assert result["actual_revenue"] is False


@pytest.mark.parametrize("flag", ["suppressed", "do_not_contact", "opted_out"])
def test_suppression_never_allows_outreach(flag):
    result = run(outreach={"suppression_checked": True, flag: True})
    assert result["action"] == "HOLD"
    assert result["contact_suppressed"] is True


def test_real_unsubscribe_reply_is_hard_stop():
    result = run(reply={
        "source_ref": "email:1",
        "received_at": NOW.isoformat(),
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "thread_linkage_verified": True,
        "body_text": "Please unsubscribe me",
    })
    assert result["action"] == "HOLD"
    assert result["reply"]["classification"] == "unsubscribe"
    assert result["contact_suppressed"] is True


@pytest.mark.parametrize("body,expected", [
    ("Sounds interesting, tell me more", "REPLY_REVIEW"),
    ("Can you send pricing?", "REPLY_REVIEW"),
    ("That's too expensive", "REPLY_REVIEW"),
    ("Try again later", "FOLLOWUP_REVIEW"),
    ("No thanks", "HOLD"),
])
def test_reply_triage_reuses_canonical_classifier(body, expected):
    result = run(reply={
        "source_ref": "email:1",
        "received_at": NOW.isoformat(),
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "thread_linkage_verified": True,
        "body_text": body,
    })
    assert result["action"] == expected


def test_unverified_reply_does_not_make_positive_action():
    result = run(reply={"body_text": "Sounds interesting"})
    assert result["action"] == "EVIDENCE_REVIEW"


def test_no_entity_or_tenant_proof_requires_identity():
    for change in ({"entity_verified": False}, {"tenant_binding_verified": False}):
        assert run(account=account(**change))["action"] == "IDENTITY_REVIEW"


def test_warm_intro_needs_verified_person_and_recent_evidence():
    rel = {
        "verified": True,
        "person_identity_verified": True,
        "evidence_refs": ["meeting:1"],
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "last_interaction_at": (NOW - timedelta(days=20)).isoformat(),
    }
    assert run(relationship=rel)["action"] == "INTRODUCTION_REVIEW"
    rel["person_identity_verified"] = False
    assert run(relationship=rel)["action"] == "OUTREACH_REVIEW"


def test_old_relationship_is_not_warm():
    rel = {
        "verified": True,
        "person_identity_verified": True,
        "evidence_refs": ["meeting:1"],
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "last_interaction_at": (NOW - timedelta(days=500)).isoformat(),
    }
    assert run(relationship=rel)["action"] == "OUTREACH_REVIEW"


def test_stale_signal_is_not_current_buyer_intent():
    old = signal(observed_at=(NOW - timedelta(days=91)).isoformat())
    row = run(signals=[old])
    assert row["action"] == "RESEARCH_REQUIRED"
    assert row["signal_review"]["excluded"][0]["reason"] == "stale_signal"


def test_future_signal_excluded():
    row = run(signals=[signal(observed_at=(NOW + timedelta(days=1)).isoformat())])
    assert row["signal_review"]["excluded"][0]["reason"] == "future_signal"


def test_undocumented_signal_excluded():
    row = run(signals=[signal(evidence_refs=[])])
    assert row["signal_review"]["fresh"] == []
    assert row["action"] == "RESEARCH_REQUIRED"


def test_duplicates_are_rejected():
    row = run(signals=[signal(), signal()])
    assert len(row["signal_review"]["fresh"]) == 1
    assert row["signal_review"]["excluded"][0]["reason"] == "duplicate_signal"


def test_contradicted_evidence_stops_promotion():
    row = run(signals=[signal(contradicted=True)])
    assert row["action"] == "EVIDENCE_REVIEW"
    assert "contradictory_signal_requires_review" in row["blockers"]


def test_missing_suppression_readback_never_approves_contact():
    row = run(outreach={})
    assert row["suppression_checked"] is False
    assert "suppression_readback_missing" in row["blockers"]
    assert row["outbound_approved"] is False


def test_quant_scope_mismatch_is_hold():
    row = run(quant_packet={
        "tenant_id": "tenant:other", "opportunity_key": "op:1",
        "actual_revenue": False, "execution_authority": "none",
        "value_available": True, "expected_gross_profit_cents": 10000,
    })
    assert row["action"] == "HOLD"
    assert row["economics"]["status"] == "BLOCKED"


def test_modelled_economics_is_not_recognised_revenue():
    row = run(quant_packet={
        "tenant_id": "tenant:1", "opportunity_key": "op:1",
        "actual_revenue": False, "execution_authority": "none",
        "value_available": True, "expected_gross_profit_cents": 10000,
    })
    assert row["economics"]["status"] == "MODELED"
    assert row["actual_revenue"] is False


def test_negative_verified_economics_holds():
    row = run(quant_packet={
        "tenant_id": "tenant:1", "opportunity_key": "op:1",
        "actual_revenue": False, "execution_authority": "none",
        "value_available": True, "expected_gross_profit_cents": -1200,
    })
    assert row["action"] == "HOLD"


def test_fingerprint_is_stable_for_same_evidence_and_changes_with_signal():
    original = run()
    assert original["decision_fingerprint"] == run()["decision_fingerprint"]
    assert original["decision_fingerprint"] != run(signals=[signal(signal_id="signal:changed")])["decision_fingerprint"]


def test_shadow_batch_does_not_override_suppression():
    q = DecisionQuestionV2(
        "buyer", "choice", "Classify", {"interested": "wants offer", "no": "declines"},
    )
    request = DecisionBatchRequestV2("schema:gtm:2", "state:1", {"ref": "1"}, (q,))
    result = DecisionBatchResultV2(
        "schema:gtm:2", "state:1", "laya", "local",
        {"buyer": {"choice": "interested", "confidence": .99}}, 12, "laya:1",
    )
    reviewed = run(outreach={"suppression_checked": True, "suppressed": True}, shadow_batch=(request, result))
    assert reviewed["action"] == "HOLD"
    assert reviewed["shadow_decision"]["changes_route"] is False


def test_shadow_authority_attack_fails():
    q = DecisionQuestionV2("buyer", "choice", "Classify", {"yes": "yes", "no": "no"})
    request = DecisionBatchRequestV2("schema:gtm:2", "state:1", {}, (q,))
    result = DecisionBatchResultV2(
        "schema:gtm:2", "state:1", "laya", "local",
        {"buyer": {"choice": "yes", "confidence": .99}}, 10, "laya:1",
        execution_authority="send",
    )
    with pytest.raises(ValueError, match="cannot grant"):
        run(shadow_batch=(request, result))


def test_never_guess_value_of_information_or_probability():
    row = run()
    assert row["value_of_information"]["status"] == "UNAVAILABLE"
    assert row["prediction_of_purchase_probability"] is None


def test_no_mutation_side_effects_or_external_dependencies():
    row = run()
    assert row["database_write"] is False
    assert row["payment_action"] is False
    assert row["fulfilment_action"] is False
    assert row["mode"] == "OBSERVE"


@pytest.mark.parametrize("kind,criteria", [
    ("choice", {"yes": "Yes", "no": "No"}),
    ("score", {}),
    ("noul", {"true": "True", "false": "False"}),
])
def test_typed_batch_validates_three_primitives(kind, criteria):
    q = DecisionQuestionV2("q", kind, "Classify", criteria)
    request = DecisionBatchRequestV2("schema:1", "state:1", {}, (q,))
    request.validate()
    value = (
        {"choice": "yes", "confidence": .7} if kind == "choice"
        else {"score": 55} if kind == "score"
        else {"probability_true": .45}
    )
    result = DecisionBatchResultV2("schema:1", "state:1", "local", "v1", {"q": value}, 1, "ref:1")
    result.validate(request)


def test_rejects_invalid_probability_distribution():
    q = DecisionQuestionV2("q", "choice", "Classify", {"yes": "Yes", "no": "No"})
    req = DecisionBatchRequestV2("s", "r", {}, (q,))
    res = DecisionBatchResultV2("s", "r", "local", "v1", {
        "q": {"choice": "yes", "confidence": .9, "probabilities": {"yes": .9, "no": .9}}
    }, 1, "ref:1")
    with pytest.raises(ValueError, match="not normalized"):
        res.validate(req)


@pytest.mark.parametrize("probability", [float("nan"), float("inf"), -0.1, 1.1, "0.9", True])
def test_rejects_invalid_noul(probability):
    q = DecisionQuestionV2("q", "noul", "Classify", {"true": "yes", "false": "no"})
    req = DecisionBatchRequestV2("s", "r", {}, (q,))
    res = DecisionBatchResultV2("s", "r", "local", "v1", {
        "q": {"probability_true": probability}
    }, 1, "ref:1")
    with pytest.raises(ValueError):
        res.validate(req)


def test_request_rejects_duplicate_questions():
    q = DecisionQuestionV2("q", "choice", "Classify", {"yes": "Yes", "no": "No"})
    with pytest.raises(ValueError, match="duplicate"):
        DecisionBatchRequestV2("s", "r", {}, (q, q)).validate()


def test_cross_tenant_signal_is_not_used():
    row = run(signals=[signal(tenant_id="tenant:other")])
    assert row["signal_review"]["excluded"][0]["reason"] == "signal_scope_mismatch"
    assert row["action"] == "RESEARCH_REQUIRED"


def test_cross_company_signal_is_not_used():
    row = run(signals=[signal(entity_id="entity:other")])
    assert row["signal_review"]["excluded"][0]["reason"] == "signal_scope_mismatch"


def test_inferred_signal_does_not_become_observed():
    row = run(signals=[signal(truth_class="INFERRED")])
    assert row["signal_review"]["fresh"] == []
    assert row["action"] == "RESEARCH_REQUIRED"


def test_cross_tenant_reply_is_not_a_real_conversation():
    row = run(reply={
        "source_ref": "email:1",
        "received_at": NOW.isoformat(),
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:wrong",
        "thread_linkage_verified": True,
        "body_text": "Sounds interesting",
    })
    assert row["action"] == "EVIDENCE_REVIEW"
    assert row["reply"]["classification"] == "unverified"


def test_unlinked_reply_cannot_assert_buying_intent():
    row = run(reply={
        "source_ref": "email:1",
        "received_at": NOW.isoformat(),
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "thread_linkage_verified": False,
        "body_text": "Send pricing",
    })
    assert row["reply"]["classification"] == "unverified"
    assert row["action"] == "EVIDENCE_REVIEW"


def test_warm_relationship_wrong_entity_does_not_count():
    row = run(relationship={
        "verified": True,
        "person_identity_verified": True,
        "entity_id": "entity:wrong",
        "tenant_id": "tenant:1",
        "evidence_refs": ["meeting:1"],
        "last_interaction_at": NOW.isoformat(),
    })
    assert row["relationship"]["warm_verified"] is False


def test_decision_fingerprint_changes_when_reply_text_changes():
    common = {
        "source_ref": "email:1",
        "received_at": NOW.isoformat(),
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "thread_linkage_verified": True,
    }
    a = run(reply={**common, "body_text": "Sounds interesting"})
    b = run(reply={**common, "body_text": "Very interesting"})
    assert a["decision_fingerprint"] != b["decision_fingerprint"]


def test_decision_fingerprint_changes_on_suppression_readback():
    a = run(outreach={"suppression_checked": True, "suppression_readback_ref": "a"})
    b = run(outreach={"suppression_checked": True, "suppression_readback_ref": "b"})
    assert a["decision_fingerprint"] != b["decision_fingerprint"]


def test_stale_reply_not_treated_as_current_sales_opportunity():
    row = run(reply={
        "source_ref": "email:archived",
        "received_at": (NOW - timedelta(days=181)).isoformat(),
        "entity_id": "entity:roof-1",
        "tenant_id": "tenant:1",
        "thread_linkage_verified": True,
        "body_text": "Send pricing",
    })
    assert row["reply"]["classification"] == "stale"
    assert row["action"] == "EVIDENCE_REVIEW"


def test_content_revision_changes_fingerprint():
    row1 = run(account=account(description="roofing contractor hiring for growth"))
    row2 = run(account=account(description="roofing contractor hiring for expansion"))
    assert row1["decision_fingerprint"] != row2["decision_fingerprint"]


def test_source_revision_changes_fingerprint():
    row1 = run(signals=[signal(source_revision="v1")])
    row2 = run(signals=[signal(source_revision="v2")])
    assert row1["decision_fingerprint"] != row2["decision_fingerprint"]


def test_shadow_result_change_invalidates_fingerprint():
    q = DecisionQuestionV2("buyer", "choice", "Classify", {"yes": "Yes", "no": "No"})
    req = DecisionBatchRequestV2("schema:gtm:2", "state:1", {}, (q,))
    def result(value):
        return DecisionBatchResultV2(
            "schema:gtm:2", "state:1", "laya", "local",
            {"buyer": {"choice": value, "confidence": .75}},
            1, "laya:1"
        )
    a = run(shadow_batch=(req, result("yes")))
    b = run(shadow_batch=(req, result("no")))
    assert a["decision_fingerprint"] != b["decision_fingerprint"]
    assert a["action"] == b["action"]
