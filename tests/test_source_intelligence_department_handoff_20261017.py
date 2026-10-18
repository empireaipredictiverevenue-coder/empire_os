"""Existing acquisition signal -> bounded specialist team delivery checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.source_intelligence_handoff import (
    SCHEMA, SNAPSHOT, STATE, LANES, build_source_intelligence_handoffs,
    deliver_source_intelligence_review, dispatch_source_intelligence_handoffs,
)
from empire_os.department_worker import _run_one_department_work_impl


NOW = datetime(2026, 10, 17, 21, 25, tzinfo=timezone.utc)


def _record(index: int, now: datetime, *, status="resolved", source="permits_nyc",
            email="private.owner@example.test") -> dict:
    return {
        "signal_id": f"fixture-{index:03d}",
        "status": status,
        "source": source,
        "metro": "NYC",
        "last_seen_at": now.isoformat(),
        "created_at": now.isoformat(),
        "email": email,
        "phone": "+15551234567",
        "name": "Private Owner",
        "url": f"https://a810-biswebportal.nyc.gov/bisweb/PropertyOverflowDetails.jsp?job={index}",
        "raw": {"job__": str(index), "owner_s_first_name": "PRIVATE"},
    }


def _fixture_root(root: Path, *, now=NOW) -> Path:
    p = root / "runtime/acquisition/signal_inbox.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fixture-001": _record(1, now),
        "fixture-002": _record(2, now, status="unresolved"),
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    cap = root / "runtime/vertical_intelligence/private_capital_latest.json"
    cap.parent.mkdir(parents=True, exist_ok=True)
    cap.write_text(json.dumps({
        "schema_version": "empire.private-capital-snapshot.v1",
        "generated_at": now.isoformat(),
        "canonical_signal_count": 0,
        "canonical_fact_count": 0,
        "segment_membership_count": 0,
    }), encoding="utf-8")
    return root


def test_triad_analysis_routes_real_permits_to_correct_department_without_pii(tmp_path):
    root = _fixture_root(tmp_path)
    d = build_source_intelligence_handoffs(root, now=NOW)
    assert d["schema_version"] == SCHEMA
    assert d["lane_count"] == 5
    assert d["unique_underlying_nyc_permit_signal_count"] == 2
    routes = {row["lane"]:row for row in d["routes"]}
    assert set(routes) == set(LANES) - {"historical_search_graph"}
    assert routes["permit"]["department"] == "market_intelligence"
    assert routes["permit"]["counts"]["signal_count"] == 2
    assert routes["permit"]["counts"]["resolved_source_rows"] == 1
    assert routes["permit"]["counts"]["unresolved_source_rows"] == 1
    assert routes["permit"]["counts"]["markets"] == "NYC"
    assert routes["permit"]["counts"]["observed_or_refreshed_last_24h"] == 2
    assert routes["permit"]["counts"]["first_recorded_last_24h"] == 2
    assert routes["permit"]["counts"]["official_nyc_portal_source_count"] == 2
    assert routes["permit"]["status"] == "CURRENT_OBSERVED"
    assert routes["property"]["department"] == "product"
    assert routes["property"]["counts"]["underlying_permit_signal_count"] == 2
    assert routes["property"]["counts"]["verified_property_opportunity_count"] is None
    assert routes["private_capital"]["status"] == "MISSING_CANONICAL_EVIDENCE"
    assert routes["storm"]["status"] == "STALE_OR_UNTRUSTED_SOURCE"
    assert routes["warehouse"]["status"] == "SOURCE_INTEGRATION_REQUIRED"
    assert all(not row["model_semantic_review_performed"]
               and not row["sale_or_revenue_proven"] for row in routes.values())
    serialized = json.dumps(d)
    assert "private.owner" not in serialized
    assert "+15551234567" not in serialized
    assert "Private Owner" not in serialized
    assert "owner_s_first_name" not in serialized
    assert d["automatic_outreach_sent"] is False


def test_departments_receive_bounded_durable_work_not_repeated_7726_tasks(tmp_path):
    root = _fixture_root(tmp_path)
    first = dispatch_source_intelligence_handoffs(
        root, now=NOW, max_jobs=3, allow_noncanonical_test=True)
    assert first["handoffs_enqueued"] == 3
    snapshot = json.loads((root / SNAPSHOT).read_text())
    assert snapshot["unique_underlying_nyc_permit_signal_count"] == 2
    queue = DepartmentWorkQueue(root)
    assert queue.counts()["ready"] == 3
    receipts = [r for r in snapshot["routes"]
                if r.get("delivery_status") == "QUEUED"]
    assert [r["lane"] for r in receipts] == ["permit","property","private_capital"]
    for row in receipts:
        result = deliver_source_intelligence_review(
            root, lane=row["lane"], fingerprint=row["evidence_fingerprint"],
            department=row["department"])
        assert result["first_pass_analysis_completed"] is True
        assert result["semantic_model_review_performed"] is False
        assert result["payable_buyer_verified"] is False
    second = dispatch_source_intelligence_handoffs(
        root, now=NOW + timedelta(minutes=2), max_jobs=3,
        allow_noncanonical_test=True)
    assert second["handoffs_enqueued"] == 2  # initial backlog, not 7726 jobs
    third = dispatch_source_intelligence_handoffs(
        root, now=NOW + timedelta(minutes=3), max_jobs=3,
        allow_noncanonical_test=True)
    assert third["handoffs_enqueued"] == 0
    assert third["handoffs_unchanged"] == 5
    assert queue.counts()["ready"] == 5
    stable = json.loads((root / SNAPSHOT).read_text())
    assert len([r for r in stable["routes"] if r.get("department_work_id")]) == 5
    states = json.loads((root / STATE).read_text())
    assert len(states["lanes"]) == 5
    assert (root / SNAPSHOT).stat().st_mode & 0o777 == 0o600
    assert (root / STATE).stat().st_mode & 0o777 == 0o600
    raw_queue = " ".join(p.read_text()
                         for p in (root / "runtime/departments/work/ready").glob("*.json"))
    assert "private.owner" not in raw_queue and "+15551234567" not in raw_queue
    assert "owner_s_first_name" not in raw_queue


def test_source_growth_coalesces_same_hour_and_flows_on_next_hour(tmp_path):
    root = _fixture_root(tmp_path)
    initial = dispatch_source_intelligence_handoffs(
        root, now=NOW, max_jobs=5, allow_noncanonical_test=True)
    assert initial["handoffs_enqueued"] == 5
    p = root / "runtime/acquisition/signal_inbox.json"
    data=json.loads(p.read_text())
    data["fixture-003"]=_record(3,NOW+timedelta(minutes=10))
    p.write_text(json.dumps(data))
    within = dispatch_source_intelligence_handoffs(
        root, now=NOW+timedelta(minutes=10),max_jobs=5,
        allow_noncanonical_test=True)
    assert within["handoffs_rate_held"] == 2
    assert within["handoffs_enqueued"] == 0
    after = dispatch_source_intelligence_handoffs(
        root, now=NOW+timedelta(hours=1),max_jobs=5,
        allow_noncanonical_test=True)
    assert after["handoffs_enqueued"] == 2
    assert DepartmentWorkQueue(root).counts()["ready"] == 7
    assert after["unique_underlying_nyc_permit_signal_count"] == 3
    another = dispatch_source_intelligence_handoffs(
        root, now=NOW+timedelta(hours=2),max_jobs=5,
        allow_noncanonical_test=True)
    assert another["handoffs_enqueued"] == 0


def test_noncanonical_default_never_mutates_or_reads_live_sources(tmp_path):
    result=dispatch_source_intelligence_handoffs(tmp_path)
    assert result["status"]=="NOT_CANONICAL_RUNTIME"
    assert result["handoffs_enqueued"]==0
    assert not list(tmp_path.iterdir())


def test_unknown_lane_and_changed_source_cannot_be_acknowledged(tmp_path):
    root=_fixture_root(tmp_path)
    dispatch_source_intelligence_handoffs(root,now=NOW,max_jobs=5,
                                          allow_noncanonical_test=True)
    first=json.loads((root / SNAPSHOT).read_text())["routes"][0]
    with pytest.raises(ValueError,match="wrong_department"):
        deliver_source_intelligence_review(
            root, lane="permit",fingerprint=first["evidence_fingerprint"],
            department="sales_revenue")
    with pytest.raises(ValueError,match="superseded"):
        deliver_source_intelligence_review(
            root,lane="permit",fingerprint="ab"*32,
            department="market_intelligence")


def test_unreadable_dispatch_state_holds_instead_of_overwriting(tmp_path):
    root=_fixture_root(tmp_path)
    p=root/STATE;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text("NOT VALID JSON")
    with pytest.raises(ValueError,match="state_unreadable"):
        dispatch_source_intelligence_handoffs(
            root,now=NOW,max_jobs=5,allow_noncanonical_test=True)
    assert p.read_text()=="NOT VALID JSON"
    assert not (root / "runtime/departments/work").exists()


def test_worker_consumes_only_queued_team_source_receipt_with_no_model(tmp_path):
    root=_fixture_root(tmp_path)
    dispatch_source_intelligence_handoffs(root,now=NOW,max_jobs=1,
                                          allow_noncanonical_test=True)
    result=_run_one_department_work_impl(root,worker_id="qa-test",timeout_seconds=20)
    assert result["ok"] is True
    assert result["state"] == "DONE"
    assert result["target_component"]=="source_intelligence_review"
    assert result["department"]=="market_intelligence"
    assert result["first_pass_analysis_completed"] is True
    assert result["semantic_model_review_performed"] is False
    queue=DepartmentWorkQueue(root)
    assert queue.counts()["done"]==1
    done=list((root/"runtime/departments/work/done").glob("*.json"))
    assert len(done)==1
    record=json.loads(done[0].read_text())
    assert record["result"]["payable_buyer_verified"] is False
    assert record["result"]["semantic_model_review_performed"] is False
    assert record["result"]["outbound_sent"] is False


def test_stale_primary_permit_data_never_claims_current_or_payable(tmp_path):
    root=_fixture_root(tmp_path,now=NOW-timedelta(days=3))
    d=build_source_intelligence_handoffs(root,now=NOW)
    permit=d["routes"][0]
    assert permit["status"]=="STALE_SOURCE"
    assert "fresh_official_permit_data_required" in permit["blockers"]
    assert permit["sale_or_revenue_proven"] is False
    assert permit["independent_buyer_intent_proven"] is False



def test_reobserving_older_signal_does_not_claim_new_discovery(tmp_path):
    root = _fixture_root(tmp_path, now=NOW - timedelta(days=4))
    p = root / "runtime/acquisition/signal_inbox.json"
    rows = json.loads(p.read_text())
    rows["fixture-001"]["last_seen_at"] = NOW.isoformat()
    p.write_text(json.dumps(rows))
    out = build_source_intelligence_handoffs(root, now=NOW)
    permit = out["routes"][0]
    assert permit["counts"]["signal_count"] == 2
    assert permit["counts"]["observed_or_refreshed_last_24h"] == 1
    assert permit["counts"]["first_recorded_last_24h"] == 0
    assert permit["status"] == "CURRENT_OBSERVED"


def test_display_age_change_does_not_create_new_work(tmp_path):
    root = _fixture_root(tmp_path)
    first = dispatch_source_intelligence_handoffs(
        root, now=NOW, max_jobs=5, allow_noncanonical_test=True)
    assert first["handoffs_enqueued"] == 5
    next_ = dispatch_source_intelligence_handoffs(
        root, now=NOW + timedelta(hours=3),
        max_jobs=5, allow_noncanonical_test=True)
    assert next_["handoffs_enqueued"] == 0
    assert next_["handoffs_unchanged"] == 5



class _LocalShadow:
    def __init__(self, response='{"action_index":1}'):
        self.response = response
        self.calls = []

    def chat(self, messages, system=None, temperature=None, max_tokens=None):
        self.calls.append((messages,system,temperature,max_tokens))
        return self.response


def test_bounded_local_model_selects_only_preapproved_research_task(tmp_path):
    root=_fixture_root(tmp_path)
    dispatch_source_intelligence_handoffs(root,now=NOW,max_jobs=5,
                                          allow_noncanonical_test=True)
    first=json.loads((root / SNAPSHOT).read_text())["routes"][0]
    model=_LocalShadow()
    review=deliver_source_intelligence_review(
        root,lane="permit",fingerprint=first["evidence_fingerprint"],
        department="market_intelligence",allow_local_model=True,
        model_client=model)
    shadow=review["model_shadow"]
    assert shadow["model_output_review_status"]=="VALIDATED_SHADOW_RESEARCH_CHOICE"
    assert shadow["suggested_next_action"]=="validate_permittee_business_identity_using_primary_source"
    assert shadow["model_inference_performed"] is True
    assert review["semantic_model_review_performed"] is True
    assert review["payable_buyer_verified"] is False
    assert review["outbound_sent"] is False
    message=json.dumps(model.calls)
    assert "private.owner" not in message
    assert "+15551234567" not in message
    assert "owner_s_first_name" not in message
    assert "project_scope" in message
    assert model.calls[0][2] == 0.0
    assert model.calls[0][3] == 64


@pytest.mark.parametrize("reply",[
    '{"action_index":3}', '{"action_index":-1}', '{"action_index":1,"buyer_verified":true}',
    '{"action_index":"0"}', 'I predict a paying customer', '[]',
    '{"error":"local_unavailable"}',
])
def test_model_invented_choices_hold_and_never_authorize_a_sale(tmp_path,reply):
    root=_fixture_root(tmp_path)
    dispatch_source_intelligence_handoffs(root,now=NOW,max_jobs=5,
                                          allow_noncanonical_test=True)
    first=json.loads((root / SNAPSHOT).read_text())["routes"][0]
    model=_LocalShadow(reply)
    review=deliver_source_intelligence_review(
        root,lane="permit",fingerprint=first["evidence_fingerprint"],
        department="market_intelligence",allow_local_model=True,
        model_client=model)
    assert review["semantic_model_review_performed"] is False
    assert review["model_shadow"]["suggested_next_action"] is None
    assert review["model_shadow"]["model_output_review_status"]=="HOLD_UNTRUSTED_MODEL_RESPONSE"
    assert review["payable_buyer_verified"] is False
    assert review["execution_authority"]=="none"


def test_without_recent_new_record_model_skips_inference(tmp_path):
    root=_fixture_root(tmp_path,now=NOW-timedelta(days=4))
    p=root / "runtime/acquisition/signal_inbox.json"
    d=json.loads(p.read_text())
    for row in d.values():
        row["last_seen_at"]=NOW.isoformat()
    p.write_text(json.dumps(d))
    dispatch_source_intelligence_handoffs(root,now=NOW,max_jobs=5,
                                          allow_noncanonical_test=True)
    first=json.loads((root / SNAPSHOT).read_text())["routes"][0]
    model=_LocalShadow()
    review=deliver_source_intelligence_review(
        root,lane="permit",fingerprint=first["evidence_fingerprint"],
        department="market_intelligence",allow_local_model=True,
        model_client=model)
    assert not model.calls
    assert review["model_shadow"]["model_output_review_status"]=="NOT_ELIGIBLE"
    assert review["semantic_model_review_performed"] is False



def test_aging_recent_cohort_without_new_source_identity_does_not_requeue(tmp_path):
    root = _fixture_root(tmp_path)
    dispatch_source_intelligence_handoffs(
        root, now=NOW, max_jobs=5, allow_noncanonical_test=True)
    # When the 24h display window expires, source identities have not
    # changed. A stale status change MAY prompt source refresh, but the
    # short-window count declining alone must never manufacture new work.
    after=dispatch_source_intelligence_handoffs(
        root, now=NOW+timedelta(hours=23, minutes=30),
        max_jobs=5, allow_noncanonical_test=True)
    assert after["handoffs_enqueued"] == 0
    assert after["handoffs_unchanged"] == 5
