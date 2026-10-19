"""Real evidence gap -> one internal Business Development worker review."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.department_worker import run_one_department_work
from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.revenue_buyer_evidence_handoff import (
    CommercialResearchHold, EVIDENCE_CUSTODY,
    enqueue_one_commercial_evidence_request,
    review_one_commercial_evidence_request,
)
from empire_os.revenue_evidence_pathways import SOURCES
from test_revenue_evidence_pathways import payloads


def fixture(tmp_path):
    now = datetime.now(timezone.utc)
    sources = payloads(n=2)
    for name, (rel, _) in SOURCES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        sources[name]["generated_at"] = (now-timedelta(minutes=1)).isoformat()
        path.write_text(json.dumps(sources[name]))
    return now


def test_one_buyer_request_uses_real_missing_quant_contract(tmp_path):
    now = fixture(tmp_path)
    source = review_one_commercial_evidence_request(tmp_path, as_of=now)
    assert source["status"] == "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
    assert source["candidate_count_in_authoritative_view"] == 2
    assert source["quant_complete_count"] == 0
    request = source["request"]
    assert request["niche"] in ("solar", "hvac")
    assert request["first_missing_evidence"] == "buyer_intent_normalized_score_required"
    assert request["required_authoritative_source"] == "CANONICAL_REPLY_OR_SIGNED_BUYING_BRIEF"
    assert len(request["quant_gaps"]) == 11
    assert set(x["factor"] for x in request["quant_gaps"]).issubset(EVIDENCE_CUSTODY)
    assert request["quant_probability_source_verified"] is False
    assert request["automatic_email_or_offer_authorized"] is False
    assert source["internal_work_created"] is False
    assert source["forecast_created"] is False
    for secret in ("hidden@example.com","someone@example.net","market:solar:uk"):
        assert secret not in json.dumps(source)


def test_existing_astra_worker_handles_handoff_idempotently(tmp_path):
    now = fixture(tmp_path)
    original = review_one_commercial_evidence_request(tmp_path, as_of=now)
    first = enqueue_one_commercial_evidence_request(
        tmp_path, original, as_of=now, allow_noncanonical_test=True,
    )
    again = enqueue_one_commercial_evidence_request(
        tmp_path, original, as_of=now, allow_noncanonical_test=True,
    )
    assert first["status"] == "QUEUED"
    assert again["status"] == "ALREADY_QUEUED"
    assert first["work_id"] == again["work_id"]
    assert DepartmentWorkQueue(tmp_path).counts()["ready"] == 1
    run = run_one_department_work(tmp_path)
    assert run["state"] == "DONE"
    assert run["internal_desk_triage_completed"] is True
    assert run["first_party_buyer_verification_completed"] is False
    records = list((tmp_path/"runtime/departments/work/done").glob("*.json"))
    assert len(records) == 1
    result = json.loads(records[0].read_text())["result"]
    assert result["status"] == "INTERNAL_BUYER_EVIDENCE_GAP_REVIEWED"
    assert result["crm_buyer_outcome_checked"] is False
    assert result["buyer_terms_verified"] is False
    assert result["prediction_registered"] is False
    assert result["economic_memory_updated"] is False
    assert result["payments_moved"] is False
    assert result["outbound_sent"] is False


@pytest.mark.parametrize("change", [
    lambda p: p["request"].update(first_missing_evidence="NO_EVIDENCE_NEEDED"),
    lambda p: p["request"]["quant_gaps"].clear(),
    lambda p: p.update(forecast_created=True),
    lambda p: p.update(execution_authority="full"),
])
def test_task_tampering_cannot_create_internal_work(tmp_path, change):
    now = fixture(tmp_path)
    proposed = deepcopy(review_one_commercial_evidence_request(tmp_path, as_of=now))
    change(proposed)
    with pytest.raises(CommercialResearchHold, match="tampering"):
        enqueue_one_commercial_evidence_request(
            tmp_path, proposed, as_of=now, allow_noncanonical_test=True,
        )
    assert not (tmp_path/"runtime/departments/work").exists()


def test_production_queue_scope_is_not_implicitly_granted(tmp_path):
    now = fixture(tmp_path)
    result = review_one_commercial_evidence_request(tmp_path, as_of=now)
    with pytest.raises(PermissionError, match="canonical"):
        enqueue_one_commercial_evidence_request(
            tmp_path, result, as_of=now,
        )
    assert not (tmp_path/"runtime/departments/work").exists()


def test_changed_quant_evidence_blocks_old_worker_task(tmp_path):
    now = fixture(tmp_path)
    original = review_one_commercial_evidence_request(tmp_path, as_of=now)
    enqueue_one_commercial_evidence_request(
        tmp_path, original, as_of=now, allow_noncanonical_test=True,
    )
    quant = tmp_path/SOURCES["quant"][0]
    body = json.loads(quant.read_text())
    body["items"][0]["decision_packet"]["missing_fields"].remove("confidence")
    quant.write_text(json.dumps(body))
    result = run_one_department_work(tmp_path)
    assert result["state"] == "BLOCKED"
    blocked = next((tmp_path/"runtime/departments/work/blocked").glob("*.json"))
    receipt = json.loads(blocked.read_text())
    assert receipt["error"] == "buyer_evidence_snapshot_or_contract_hold"
    assert receipt["result"]["crm_mutated"] is False
    assert receipt["result"]["outbound_sent"] is False


def test_stale_authority_or_tenant_records_never_create_request(tmp_path):
    now = fixture(tmp_path)
    source = tmp_path/SOURCES["intake"][0]
    body = json.loads(source.read_text())
    body["items"][0]["tenant_id"] = "tenant-private"
    source.write_text(json.dumps(body))
    review = review_one_commercial_evidence_request(tmp_path, as_of=now)
    assert review["status"] == "HELD_NO_CURRENT_FIRST_PARTY_GAP"
    assert review["request"] is None
    assert review["forecast_created"] is False


def test_empty_authoritative_inventory_never_creates_fake_buyer(tmp_path):
    now = fixture(tmp_path)
    from test_revenue_evidence_pathways import payloads
    items = payloads(n=0)
    for name,(rel,_) in SOURCES.items():
        items[name]["generated_at"]=(now-timedelta(minutes=1)).isoformat()
        (tmp_path/rel).write_text(json.dumps(items[name]))
    review = review_one_commercial_evidence_request(tmp_path, as_of=now)
    assert review["status"] == "HELD_NO_CURRENT_FIRST_PARTY_GAP"
    assert review["request"] is None


def test_single_task_does_not_request_external_model_or_spend(tmp_path):
    now = fixture(tmp_path)
    result = review_one_commercial_evidence_request(tmp_path, as_of=now)
    queued = enqueue_one_commercial_evidence_request(
        tmp_path, result, as_of=now, allow_noncanonical_test=True,
    )
    task = next((tmp_path/"runtime/departments/work/ready").glob("*.json"))
    payload = json.loads(task.read_text())
    assert payload["authority"] == "observe"
    assert payload["department_keys"] == ["business_development"]
    assert payload["intelligence_request"]["budget"] == {
        "requested_model_tokens": 0,
        "requested_external_cost_cents": 0,
    }
    assert payload["intelligence_request"]["first_party_buyer_evidence"]["model_training_authorized"] is False
    assert queued["crm_mutated"] is False


def test_untrusted_niche_text_not_echoed_to_existing_astra_task(tmp_path):
    now = fixture(tmp_path)
    radar = tmp_path/SOURCES["radar"][0]
    body = json.loads(radar.read_text())
    body["candidates"][0]["niche"] = "PRIVATE BUYER CONTACT jane@example.com"
    radar.write_text(json.dumps(body))
    prepared = review_one_commercial_evidence_request(tmp_path, as_of=now)
    assert prepared["status"] == "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
    serialized = json.dumps(prepared)
    assert "jane@example.com" not in serialized
    enqueue_one_commercial_evidence_request(
        tmp_path, prepared, as_of=now, allow_noncanonical_test=True,
    )
    work_file = next((tmp_path/"runtime/departments/work/ready").glob("*.json"))
    assert "jane@example.com" not in work_file.read_text()
