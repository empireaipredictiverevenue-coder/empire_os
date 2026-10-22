"""Thirty real first-party cases: AI findings only, never publishing authority."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.ai_first_receipt import read_ai_first_summary
from empire_os.search_intelligence.jev_case_receipts import (
    JevCaseReceiptHeld, reviewed_case_summary,
)
from empire_os.search_intelligence.jev_page_case_review import (
    JevPageBatchHeld, batch_plan, run_batch,
)
from empire_os.search_intelligence.service import build_search_intelligence_service


def test_real_local_receipt_reports_failures_not_30_successes():
    packet=read_ai_first_summary()
    assert packet["observed_cases_reviewed"]==30
    assert packet["model_candidates_returned"]==2
    assert packet["deep_ai_research_queue_count"]==30
    assert packet["new_inference_requests_during_status"]==0 if (
        "new_inference_requests_during_status" in packet) else True
    assert packet["human_labels_created"]==0
    assert "/aeo/" not in str(packet)


def test_all_six_real_jev_batches_cover_exact_30_without_paths():
    result=reviewed_case_summary()
    assert result["verified_provider_batches"]==6
    assert result["original_page_cases_assessed"]==30
    assert result["validated_model_responses"]==30
    assert result["model_choice_counts"]=={"SOURCE_AUDIT":30}
    assert result["model_confidence_at_least_0_80"]==4
    assert result["model_confidence_below_0_80"]==26
    assert 0 < result["reported_cost_usd"] < 0.001
    assert result["new_inference_requests_during_status"]==0
    assert result["model_prediction_accuracy_verified"] is False
    assert result["model_outputs_are_human_labels"] is False
    assert result["unattended_provider_calls_enabled"] is False
    assert result["execution_authority"]=="NONE"
    assert "/aeo/" not in str(result)


def test_exactly_six_fixed_five_case_plans_and_no_unbounded_request():
    plans=[batch_plan(i) for i in range(6)]
    ids=[c["case_id"] for p in plans for c in p["case_keys"]]
    assert len(ids)==len(set(ids))==30
    assert all(p["max_requests"]==1 for p in plans)
    assert all(p["max_cost_usd"]==.001 for p in plans)
    assert all(len(p["request"]["questions"])==5 for p in plans)
    assert all(len(p["request"]["state"]["cases"])==5 for p in plans)
    assert all(s["first_party_path"].startswith("/aeo/")
               for p in plans for s in p["request"]["state"]["cases"])
    with pytest.raises(JevPageBatchHeld):
        batch_plan(6)


def test_typed_jev_five_answer_validation_without_external_network():
    p=batch_plan(0)
    answers={}
    for key in p["request"]["questions"]:
        answers[key]={
            "type":"choice",
            "choice":"SOURCE_AUDIT",
            "probabilities":{
                "SOURCE_AUDIT":.8,"TECHNICAL_REPAIR_REVIEW":.04,
                "EDITORIAL_REVIEW":.05,"MONITOR":.03,"ABSTAIN":.08,
            },
            "confidence":.8,
        }
    raw={"model":"typesafe/jev-1.13-20260917",
         "answers":answers,
         "usage":{"input_tokens":2500,"cost":.00009}}
    calls=[]
    class Response:
        status_code=200
        def json(self):return raw
    def fake_post(url,**kw):
        calls.append((url,kw))
        return Response()
    result=run_batch(p,api_key="sk-"+("X"*30),post=fake_post)
    assert len(calls)==1 and calls[0][1]["timeout"]==16
    assert calls[0][1]["allow_redirects"] is False
    assert result["cases_reviewed"]==5
    assert result["ground_truth_labels_verified"]==0
    assert result["authorised_publication"] is False
    assert all(x["human_ground_truth"] is False for x in result["case_reviews"])
    raw["answers"]["case_1"]["choice"]="PUBLISH_NOW"
    with pytest.raises(JevPageBatchHeld):
        run_batch(p,api_key="sk-"+("X"*30),post=fake_post)


def test_mutating_outbound_data_prevents_provider_call():
    p=batch_plan(0)
    p=deepcopy(p)
    p["request"]["state"]["cases"][0]["customer_email"]="SECRET"
    def forbidden(*args,**kwargs):
        pytest.fail("No external call authorised on tampered data")
    with pytest.raises(JevPageBatchHeld,match="OUTSIDE_PINNED"):
        run_batch(p,api_key="sk-"+("X"*30),post=forbidden)


def test_api_endpoints_return_scalar_summary_or_503(monkeypatch):
    client=TestClient(build_search_intelligence_service())
    for route in ("jev/ai-first/summary","jev/cases/summary"):
        response=client.get("/v1/search/"+route)
        assert response.status_code==200
        assert response.headers["cache-control"]=="no-store"
        assert "/aeo/" not in response.text
        assert "publication" in response.text
    import empire_os.search_intelligence.api as api
    monkeypatch.setattr(api,"reviewed_case_summary",
                        lambda: (_ for _ in ()).throw(JevCaseReceiptHeld("SECRET")))
    response=client.get("/v1/search/jev/cases/summary")
    assert response.status_code==503
    assert "SECRET" not in response.text


def test_modified_receipt_hash_rejected(tmp_path):
    import pathlib
    from empire_os.search_intelligence.jev_case_receipts import ROOT
    for i in range(6):
        p=ROOT/f"jev_page_batch_{i}_20261022.json"
        (tmp_path/p.name).write_bytes(p.read_bytes())
        (tmp_path/p.name).chmod(0o600)
    corrupted=tmp_path/"jev_page_batch_0_20261022.json"
    corrupted.write_bytes(corrupted.read_bytes()+b"\n")
    with pytest.raises(JevCaseReceiptHeld,match="HASH_MISMATCH"):
        reviewed_case_summary(tmp_path)
