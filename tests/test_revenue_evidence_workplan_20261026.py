"""Work plan uses the ORIGINAL department queue contract; no queue mutation."""
from __future__ import annotations
from copy import deepcopy
import pytest

from empire_os.revenue_evidence_workplan import build_workplan, RESTORE
from tests.test_unified_revenue_loop_review_20261026 import payloads

def inputs():
    supervisor, relationships = payloads()
    source = supervisor["cross_system_cohesion"]
    handoffs = supervisor["canonical_opportunity_handoffs"]
    for key in RESTORE:
        source["sources"].setdefault(key, {"status": "CURRENT_OBSERVATION"})
    source["sources"] = {key: {"status": "CURRENT_OBSERVATION",
                               "sha256": "a"*64 if key == "opportunity_factory" else None}
                         for key in RESTORE}
    source["evidence_population_counts"] = {"fully_activated_buyers": 0}
    handoffs.update(
        source_reviewed=True,
        items=[{"review_id": "research_review:0123456789abcdef01234567",
                "opportunity_key": "market:hvac:detroit, mi",
                "next_action": "COMPLETE_REAL_FACTORY_VALIDATION",
                "handoff_ready": False, "commercial_authority": False}],
    )
    return source, handoffs, relationships["buyer_evidence_brain"]

def test_original_owners_get_stable_deduped_proof_tasks_no_queue_writes():
    inputs_ = inputs()
    first = build_workplan(*inputs_)
    second = build_workplan(*deepcopy(inputs_))
    assert first == second
    assert first["work_count"] >= 3
    assert first["work_proposals"][0]["action"] == "VERIFY_ONE_CONTRACTED_DOWNSTREAM_PAYER_BUYBOX"
    assert any(x["evidence_ref"] == "research_review:0123456789abcdef01234567"
               for x in first["work_proposals"])
    assert first["original_queue"] == "empire_os.department_work_queue.DepartmentWorkQueue"
    assert not first["queue_mutated"]
    assert first["work_dispatched"] == 0
    assert not first["database_writes"]
    assert not first["payments_executed"]
    assert all(not x["enqueue_authorized"] and x["review_only"]
               for x in first["work_proposals"])

def test_stale_sources_do_not_create_research_promotion_tasks():
    c,h,b=inputs()
    c["sources"]["opportunity_factory"]["status"] = "STALE_OR_FUTURE"
    v=build_workplan(c,h,b)
    assert any(x["action"] == "RECHECK_FACTORY_ORIGINAL_SOURCE" for x in v["work_proposals"])
    assert not any(x["action"] == "COMPLETE_REAL_FACTORY_VALIDATION" for x in v["work_proposals"])

def test_real_publisher_report_creates_one_buyer_verification_only():
    c,h,b=inputs()
    b["commercial_proof_task_count"]=1
    b["commercial_proof_tasks"]=[{
        "task": "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE",
        "gmail_source_ref": "gmail:1a159bed9fcc61ac",
        "execution_authority": "NONE",
        "outbound_authorized": False,
    }]
    work=build_workplan(c,h,b)
    publisher=[x for x in work["work_proposals"] if x["evidence_ref"] == "gmail:1a159bed9fcc61ac"]
    assert len(publisher)==1
    assert publisher[0]["original_owner"]=="BuyerAcquisition"
    assert publisher[0]["action"]=="VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE"
    assert not publisher[0]["outbound_authorized"]
    assert not publisher[0]["money_movement_authorized"]

@pytest.mark.parametrize("mutate", [
    lambda c,h,b: c.update(db_writes=True),
    lambda c,h,b: h.update(outbound_authorized=True),
    lambda c,h,b: h.update(handoff_ready_count=1),
    lambda c,h,b: b.update(new_emails_sent=True),
    lambda c,h,b: b.update(commercial_proof_task_count=1),
    lambda c,h,b: c["sources"].pop("jev"),
])
def test_untrusted_or_inconsistent_inputs_fail_closed(mutate):
    c,h,b=inputs()
    mutate(c,h,b)
    with pytest.raises(ValueError):
        build_workplan(c,h,b)

def test_report_contains_original_workplan_without_authorising_enqueue():
    from scripts.review_unified_revenue_loop_20261026 import report
    s,r=payloads()
    v=report(s,r)
    assert v["original_department_queue_mutated"] is False
    assert v["evidence_work_proposal_count"] >= 2
    assert all(row["enqueue_authorized"] is False for row in v["next_evidence_work"])


def test_concurrent_factory_refresh_never_creates_mixed_generation_work():
    c,h,b=inputs()
    h["factory_source_sha256"]="b"*64
    v=build_workplan(c,h,b)
    assert v["factory_snapshot_generation_consistent"] is False
    assert any(x["action"] == "RECHECK_COHERENT_FACTORY_GENERATION"
               for x in v["work_proposals"])
    assert not any(x["action"] == "COMPLETE_REAL_FACTORY_VALIDATION"
                   for x in v["work_proposals"])
    assert v["work_dispatched"] == 0
    assert v["queue_mutated"] is False


def test_malformed_gmail_message_reference_cannot_enter_original_workplan():
    c,h,b=inputs()
    b["commercial_proof_task_count"]=1
    b["commercial_proof_tasks"]=[{
        "task": "VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE",
        "gmail_source_ref": "gmail:not-a-provider-receipt",
        "execution_authority": "NONE",
        "outbound_authorized": False,
    }]
    with pytest.raises(ValueError, match="UNTRUSTED_PUBLISHER_WORK"):
        build_workplan(c,h,b)


def test_exact_existing_buyer_reply_generates_review_not_new_send():
    c,h,b=inputs()
    c["existing_inbound_buyer_reply_reviews"]=[{
        "review_ref":"founder_review:lead-smart",
        "existing_owner":"BuyerReplyOperations",
        "source_action":"REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT",
        "new_outbound_authorized":False,
        "buyer_contract_verified":False,
        "execution_authority":"NONE",
    }]
    v=build_workplan(c,h,b)
    rows=[x for x in v["work_proposals"]
          if x["evidence_ref"]=="founder_review:lead-smart"]
    assert len(rows)==1
    assert rows[0]["priority"]==98
    assert rows[0]["original_owner"]=="BuyerReplyOperations"
    assert rows[0]["enqueue_authorized"] is False
    assert rows[0]["outbound_authorized"] is False


def test_existing_buyer_reply_cannot_claim_approval_or_move_funds():
    c,h,b=inputs()
    c["existing_inbound_buyer_reply_reviews"]=[{
        "review_ref":"founder_review:lead-smart",
        "existing_owner":"BuyerReplyOperations",
        "source_action":"REVIEW_EXISTING_ROUTING_RECORDING_REPLY_NO_REPEAT",
        "new_outbound_authorized":True,
        "buyer_contract_verified":False,
        "execution_authority":"NONE",
    }]
    with pytest.raises(ValueError,match="UNTRUSTED_EXISTING_BUYER_REPLY"):
        build_workplan(c,h,b)
