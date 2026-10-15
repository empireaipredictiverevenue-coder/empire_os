"""Local-model shadow safety tests, using the existing AGI test fixtures."""
from copy import deepcopy
import json

import pytest
from empire_os.data_exchange_local_reasoning import (
    review_local_reasoning, validated_context,
)

from test_data_exchange_agi_bridge import review as agi_review, procurement


def packet():
    return agi_review(changed=True, proc=procurement())


class FakeLocalModel:
    def __init__(self, raw=None, *, error=None):
        self.calls = []
        self.raw = raw
        self.error = error

    def chat(self, messages, system=None, temperature=0.2, max_tokens=2048):
        self.calls.append((messages, system, temperature, max_tokens))
        if self.error:
            raise self.error
        return self.raw


def candidate(p=None, **changes):
    context = validated_context(p or packet())
    raw = {
        "hypothesis_key": "stage_change_precedes_opportunity",
        "research_action": "review_dataset_rights",
        "evidence_ref": context.evidence[0],
        "counterargument": "The site may never proceed",
        "falsification_test": "Timestamped independent outcomes and a no-change baseline",
    }
    raw.update(changes)
    return json.dumps(raw)


def test_default_no_inference_no_client_invocation():
    stub = FakeLocalModel(error=AssertionError("no model call"))
    result = review_local_reasoning(packet(), client=stub)
    assert stub.calls == []
    assert result["model_output_review_status"] == "NOT_RUN"
    assert result["model_inference_performed"] is False
    assert result["customer_delivery_enabled"] is False
    assert result["execution_authority"] == "NONE"


def test_local_model_choice_is_advisory_not_evidence_or_execution():
    p = packet()
    stub = FakeLocalModel(candidate(p))
    result = review_local_reasoning(p, client=stub, allow_inference=True)
    assert result["model_output_review_status"] == "ADVISORY_CANDIDATE_SCHEMA_VERIFIED"
    assert result["model_inference_performed"] is True
    assert result["candidate_agrees_with_base_priority"] is True
    assert result["independent_model_critic_completed"] is False
    assert result["hypotheses_remain_untested"] is True
    assert result["predictive_claim_ready"] is False
    assert result["production_writes"] is False
    assert result["execution_authority"] == "NONE"
    assert len(stub.calls) == 1
    msgs, system, temperature, tokens = stub.calls[0]
    assert temperature == 0.0 and tokens == 110
    assert "not an executor" in system
    prompt = msgs[0]["content"]
    assert "private@example.org" not in prompt
    assert "PRIVATE-TENDER-DESCRIPTION" not in prompt
    assert "personal" not in prompt.lower()
    assert "evidence" in prompt


def test_model_alternative_advisory_does_not_overwrite_rights_priority():
    p = packet()
    action = "independently_verify_source_transitions"
    stub = FakeLocalModel(candidate(p, research_action=action))
    result = review_local_reasoning(p, client=stub, allow_inference=True)
    assert result["model_candidate"]["research_action"] == action
    assert result["deterministic_recommendation"] == "review_dataset_rights"
    assert result["candidate_agrees_with_base_priority"] is False
    assert result["does_not_override_base_plan"] is True


@pytest.mark.parametrize("changes", [
    {"hypothesis_key": "verified_funding_event"},
    {"research_action": "payment.move"},
    {"research_action": "outreach.send"},
    {"evidence_ref": "https://attacker.test/false-proof"},
    {"counterargument": "Buyers are definitely ready to pay"},
    {"falsification_test": "Skip evidence checks"},
    {"model_override": True},
])
def test_model_hallucination_or_permission_escalation_rejected(changes):
    p = packet()
    stub = FakeLocalModel(candidate(p, **changes))
    outcome = review_local_reasoning(p, client=stub, allow_inference=True)
    assert outcome["model_output_review_status"] == "REJECTED_UNTRUSTED_OUTPUT"
    assert outcome["model_candidate"] is None
    assert outcome["execution_authority"] == "NONE"


def test_malformed_model_output_fails_closed_without_echo():
    for raw in (
        "not json",
        '{"error":"provider not available"}',
        json.dumps({"evil": "override"}), "private-content" * 500,
    ):
        response = review_local_reasoning(
            packet(), client=FakeLocalModel(raw), allow_inference=True,
        )
        assert response["model_output_review_status"] in {
            "REJECTED_UNTRUSTED_OUTPUT", "HOLD_PROVIDER_FAILURE"
        }
        assert response["model_candidate"] is None
        assert "private-content" not in str(response)
        assert "provider not available" not in str(response)


def test_local_provider_failure_is_hold_not_pretend_success():
    model = FakeLocalModel(error=TimeoutError("local port slow"))
    result = review_local_reasoning(packet(), client=model, allow_inference=True)
    assert result["model_output_review_status"] == "HOLD_PROVIDER_FAILURE"
    assert result["model_inference_performed"] is False


@pytest.mark.parametrize("mutate", [
    lambda x: x.update({"customer_delivery_enabled": True}),
    lambda x: x.update({"execution_authority": "EXECUTE"}),
    lambda x: x.update({"predictive_marketing_claim_ready": True}),
    lambda x: x.update({"procurement_context_count": 2}),
    lambda x: x["evidence_refs"].append("evil:fake-source"),
    lambda x: x["unresolved_evidence"].append("private@example.org"),
    lambda x: x["hypotheses"][0].update({"state": "VERIFIED"}),
    lambda x: x["hypotheses"][0].update({"alternatives": ["conclusively true"]}),
    lambda x: x["research_workstreams"][0].update({"workstream": "outreach.send"}),
    lambda x: x.update({"recommended_workstream": "research_first_paid_buyer"}),
])
def test_untrusted_packet_never_sent_to_model(mutate):
    p = deepcopy(packet())
    mutate(p)
    stub = FakeLocalModel(candidate())
    with pytest.raises(ValueError):
        review_local_reasoning(p, client=stub, allow_inference=True)
    assert stub.calls == []


def test_safely_selects_second_hypothesis_with_approved_disconfirmation():
    p = packet()
    result = review_local_reasoning(p, client=FakeLocalModel(candidate(
        p,
        hypothesis_key="procurement_corroborates_project",
        counterargument="Both events may be unrelated despite shared geography",
        falsification_test="Official common project identifier or direct document citation",
    )), allow_inference=True)
    assert result["model_output_review_status"] == "ADVISORY_CANDIDATE_SCHEMA_VERIFIED"
    assert result["model_candidate"]["hypothesis_key"] == "procurement_corroborates_project"


def test_compact_indexed_qwen_result_maps_only_to_approved_catalogue():
    p = packet()
    result = review_local_reasoning(
        p, client=FakeLocalModel('{"h":1,"a":2,"e":1,"c":0}'),
        allow_inference=True,
    )
    assert result["model_output_review_status"] == "ADVISORY_CANDIDATE_SCHEMA_VERIFIED"
    assert result["model_candidate"] == {
        "hypothesis_key": "procurement_corroborates_project",
        "research_action": "verify_cross_source_project_identity",
        "evidence_ref": "find-a-tender:notice:096757-2026",
        "counterargument": "Both events may be unrelated despite shared geography",
        "falsification_test": "Official common project identifier or direct document citation",
    }
    assert result["candidate_agrees_with_base_priority"] is False
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize("output", [
    '{"h":true,"a":0,"e":0,"c":0}',
    '{"h":5,"a":0,"e":0,"c":0}',
    '{"h":0,"a":10000,"e":0,"c":0}',
    '{"h":0,"a":0,"e":2,"c":0}',
    '{"h":1,"a":0,"e":0,"c":4}',
    '{"h":0,"a":0,"e":0,"c":-1}',
    '{"h":0,"a":0,"e":0,"c":0,"tool":"outreach.send"}',
])
def test_compact_model_hallucinations_fail_closed(output):
    result = review_local_reasoning(
        packet(), client=FakeLocalModel(output), allow_inference=True
    )
    assert result["model_output_review_status"] == "REJECTED_UNTRUSTED_OUTPUT"
    assert result["execution_authority"] == "NONE"


def test_operator_cli_default_and_opt_in_path_are_explicit(tmp_path, capsys, monkeypatch):
    import json
    import scripts.review_data_exchange_agi as operator
    from test_data_exchange_agi_bridge import source

    a, b = source(changed=False)
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(a), encoding="utf-8")
    after.write_text(json.dumps(b), encoding="utf-8")
    argv = [
        "--snapshots", str(before), str(after), "--tenant-id", "tenant-internal",
    ]
    assert operator.main(argv) == 0
    disabled = json.loads(capsys.readouterr().out)
    assert disabled["local_reasoning_review"]["model_inference_performed"] is False
    assert disabled["local_reasoning_review"]["model_output_review_status"] == "NOT_RUN"

    invoked = []
    def stub_model(packet, *, allow_inference):
        invoked.append(allow_inference)
        return {"model_output_review_status": "HOLD_PROVIDER_FAILURE",
                "execution_authority": "NONE"}
    monkeypatch.setattr(operator, "review_local_reasoning", stub_model)
    assert operator.main([*argv, "--local-model"]) == 0
    enabled = json.loads(capsys.readouterr().out)
    assert invoked == [True]
    assert enabled["local_reasoning_review"]["execution_authority"] == "NONE"
    assert enabled["recommended_workstream"] == "review_dataset_rights"


def test_provider_json_error_is_reported_as_unavailable_not_hallucinated():
    model = FakeLocalModel('{"error":"llama_cpp_request_failed:TimeoutError"}')
    review = review_local_reasoning(packet(), client=model, allow_inference=True)
    assert review["model_output_review_status"] == "HOLD_PROVIDER_FAILURE"
    assert review["model_inference_performed"] is False
    assert review["model_candidate"] is None


def test_exact_markdown_fenced_model_json_can_be_verified_without_lowering_gates():
    ticks = chr(96) * 3
    raw = ticks + 'json\n{\n  "h": 0,\n  "a": 0,\n  "e": 0,\n  "c": 0\n}\n' + ticks
    result = review_local_reasoning(packet(), client=FakeLocalModel(raw),
                                    allow_inference=True)
    assert result["model_output_review_status"] == "ADVISORY_CANDIDATE_SCHEMA_VERIFIED"
    assert result["model_candidate"]["research_action"] == "review_dataset_rights"
    assert result["execution_authority"] == "NONE"


def test_fenced_json_with_extra_commands_is_rejected():
    ticks = chr(96) * 3
    body = '{"h":0,"a":0,"e":0,"c":0}'
    bad_outputs = [
        ticks + "json\n" + body + "\n" + ticks + "\nexecute outreach.send",
        "Some advice\n" + ticks + "json\n" + body + "\n" + ticks,
        ticks + "json\n" + body[:-1] + ',"send":true}' + "\n" + ticks,
    ]
    for bad in bad_outputs:
        result = review_local_reasoning(packet(), client=FakeLocalModel(bad),
                                        allow_inference=True)
        assert result["model_output_review_status"] == "REJECTED_UNTRUSTED_OUTPUT"
        assert result["model_candidate"] is None
        assert result["outbound_enabled"] is False
