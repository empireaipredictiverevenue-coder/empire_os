"""Laya integration tests use synthetic evidence packet fixtures only."""
from copy import deepcopy
import pytest

from empire_os.data_exchange_laya_shadow import (
    evaluate_laya_shadow, SCHEMA, TASK, THRESHOLD,
)
from empire_os.typed_decision_provider import TypedDecisionResult
from test_data_exchange_agi_bridge import review as agi_review, procurement


def packet():
    return agi_review(changed=True, proc=procurement())


class FakeProvider:
    def __init__(self, *, label=None, confidence=0.92, provider_key="laya_http",
                 shadow_only=True, execution_authority="none", fail=None):
        self.calls = []
        self.label = label
        self.confidence = confidence
        self.provider_key = provider_key
        self.shadow_only = shadow_only
        self.execution_authority = execution_authority
        self.fail = fail

    def evaluate(self, request):
        self.calls.append(request)
        if self.fail:
            raise self.fail
        return TypedDecisionResult(
            provider_key=self.provider_key,
            model_key="laya:onnx", task_key=request.task_key,
            decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref,
            label=self.label or request.allowed_labels[0],
            confidence=self.confidence, latency_ms=21.0,
            source_ref="laya:http:shadow:" + request.state_ref,
            shadow_only=self.shadow_only,
            execution_authority=self.execution_authority,
        )


def test_disabled_default_no_model_call():
    p = FakeProvider(fail=AssertionError("must not call"))
    v = evaluate_laya_shadow(packet(), provider=p)
    assert p.calls == []
    assert v["decision_status"] == "NOT_RUN"
    assert v["model_inference_performed"] is False
    assert v["execution_authority"] == "NONE"


def test_accepted_laya_action_remains_nonexecuting_advisory():
    p = FakeProvider(label="review_dataset_rights")
    v = evaluate_laya_shadow(packet(), provider=p, allow_inference=True)
    assert v["decision_status"] == "ADVISORY_LABEL_SCHEMA_VERIFIED"
    assert v["candidate_action"] == "review_dataset_rights"
    assert v["candidate_agrees_with_base_priority"] is True
    assert v["confidence"] == 0.92
    assert v["latency_ms"] == 21.0
    assert v["model_does_not_override_base_plan"] is True
    assert v["buyer_intent_verified"] is False
    assert v["customer_delivery_enabled"] is False
    assert v["outbound_enabled"] is False
    assert v["payment_execution"] is False
    assert v["production_writes"] is False
    assert v["execution_authority"] == "NONE"
    r = p.calls[0]
    assert r.risk_class == "low"
    assert r.task_key == TASK
    assert r.decision_schema_ref == SCHEMA
    assert r.state_ref.startswith("empire:data_exchange:shadow:")
    assert len(r.allowed_labels) == 5
    assert all("private@example" not in str(r.state) for _ in range(1))
    assert "PRIVATE-TENDER-DESCRIPTION" not in str(r.state)


def test_disagreement_cannot_override_canonical_plan():
    p = FakeProvider(label="research_first_paid_buyer")
    v = evaluate_laya_shadow(packet(), provider=p, allow_inference=True)
    assert v["candidate_action"] == "research_first_paid_buyer"
    assert v["deterministic_priority"] == "review_dataset_rights"
    assert v["candidate_agrees_with_base_priority"] is False
    assert v["execution_authority"] == "NONE"


@pytest.mark.parametrize("confidence", [0.0, 0.4, 0.79])
def test_low_confidence_is_not_accepted(confidence):
    v = evaluate_laya_shadow(
        packet(), provider=FakeProvider(confidence=confidence),
        allow_inference=True,
    )
    assert v["decision_status"] == "HOLD_LOW_CONFIDENCE"
    assert v["candidate_action"] is None
    assert v["confidence"] == confidence


@pytest.mark.parametrize("options", [
    {"label": "outreach.send"},
    {"label": "pay_and_bill"},
    {"execution_authority": "EXECUTE"},
    {"shadow_only": False},
    {"provider_key": "gemini"},
    {"confidence": 2.0},
    {"confidence": -0.1},
    {"fail": TimeoutError("sidecar busy")},
])
def test_invalid_or_untrusted_provider_never_gains_authority(options):
    p = FakeProvider(**options)
    v = evaluate_laya_shadow(packet(), provider=p, allow_inference=True)
    assert v["candidate_action"] is None
    assert v["decision_status"] in {
        "HOLD_PROVIDER_OR_VALIDATION_FAILURE", "REJECTED_AUTHORITY_OR_PROVIDER",
    }
    assert v["execution_authority"] == "NONE"


@pytest.mark.parametrize("change", [
    lambda x: x.update({"execution_authority": "EXECUTE"}),
    lambda x: x.update({"customer_delivery_enabled": True}),
    lambda x: x["research_workstreams"][0].update({"workstream": "outreach.send"}),
    lambda x: x["unresolved_evidence"].append("private@example.org"),
    lambda x: x["evidence_refs"].append("bad:source"),
])
def test_tampered_context_never_reaches_laya(change):
    p = deepcopy(packet())
    change(p)
    client = FakeProvider()
    with pytest.raises(ValueError):
        evaluate_laya_shadow(p, provider=client, allow_inference=True)
    assert client.calls == []


def test_local_state_contains_only_codes_counts_and_base_priority():
    provider = FakeProvider()
    evaluate_laya_shadow(packet(), provider=provider, allow_inference=True)
    state = provider.calls[0].state
    assert set(state) == {
        "source_change_count", "procurement_context_count",
        "evidence_gap_codes", "baseline_priority",
    }
    assert state["source_change_count"] == 1
    assert state["procurement_context_count"] == 1
    assert "private" not in str(state).lower()
    assert THRESHOLD == 0.8


def test_cli_laya_opt_in_and_default_do_not_change_rights_priority(
    tmp_path, capsys, monkeypatch,
):
    import json
    from test_data_exchange_agi_bridge import source
    import scripts.review_data_exchange_agi as operator

    before, after = source(changed=True)
    a, b = tmp_path / "before.json", tmp_path / "after.json"
    a.write_text(json.dumps(before), encoding="utf-8")
    b.write_text(json.dumps(after), encoding="utf-8")
    args = ["--snapshots", str(a), str(b), "--tenant-id", "internal"]

    assert operator.main(args) == 0
    disabled = json.loads(capsys.readouterr().out)
    assert disabled["laya_shadow_review"]["decision_status"] == "NOT_RUN"
    assert disabled["laya_shadow_review"]["model_inference_performed"] is False
    assert disabled["recommended_workstream"] == "review_dataset_rights"

    calls = []
    def stub_laya(packet, *, allow_inference):
        calls.append(allow_inference)
        return {"decision_status": "HOLD_LOW_CONFIDENCE",
                "execution_authority": "NONE", "candidate_action": None}

    monkeypatch.setattr(operator, "evaluate_laya_shadow", stub_laya)
    assert operator.main([*args, "--laya-shadow"]) == 0
    enabled = json.loads(capsys.readouterr().out)
    assert calls == [True]
    assert enabled["laya_shadow_review"]["execution_authority"] == "NONE"
    assert enabled["recommended_workstream"] == "review_dataset_rights"
    assert enabled["local_reasoning_review"]["model_inference_performed"] is False


def test_sidecar_exception_not_reported_as_success():
    v = evaluate_laya_shadow(
        packet(), provider=FakeProvider(fail=RuntimeError("busy")),
        allow_inference=True,
    )
    assert v["decision_status"] == "HOLD_PROVIDER_OR_VALIDATION_FAILURE"
    assert v["model_inference_performed"] is False
