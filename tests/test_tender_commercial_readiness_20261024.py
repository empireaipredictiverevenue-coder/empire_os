"""CA18567 commercial evidence gate: real provider receipts only; no bid promotion."""
from __future__ import annotations

from datetime import datetime,timezone
import json
import os
from pathlib import Path
import stat
import pytest
from empire_os.tender_commercial_readiness_20261024 import (
    EXPECTED_SENDS,INCOMING,OUTPUT,_valid_sent_receipt,
    _hypothetical_economics,assess,save_private
)

NOW=datetime(2026,10,24,15,55,tzinfo=timezone.utc)

@pytest.fixture
def root(tmp_path:Path)->Path:
    folder=tmp_path/"runtime/acquisition_research"
    folder.mkdir(parents=True,mode=0o700)
    os.chmod(folder,0o700)
    return tmp_path


def _good_receipt()->dict:
    return {
        "schema_version":"empire.tender_ca18567_approved_outreach_receipt.v1",
        "reference":"CA18567",
        "source":"Gmail connected business mailbox send_draft responses",
        "state":"PROVIDER_SENT_CONFIRMED_NOT_DELIVERY_CONFIRMED",
        "sent_count":5,
        "delivery_confirmed_count":0,
        "replies_verified_count":0,
        "supplier_quotes_verified_count":0,
        "supplier_contracts_verified_count":0,
        "rfq_obtained":False,
        "bid_submitted":False,
        "crm_writes":False,
        "payment_actions":False,
        "messages":[{"recipient":recipient,"message_id":v[0],
                     "thread_id":v[1],"provider_label":"SENT"}
                    for recipient,v in EXPECTED_SENDS.items()],
    }


def _write_receipt(root:Path,receipt:dict)->None:
    file=root/INCOMING
    file.write_text(json.dumps(receipt))
    os.chmod(file,0o600)


def test_valid_exact_five_provider_sends(root:Path):
    receipt=_good_receipt()
    _write_receipt(root,receipt)
    assert _valid_sent_receipt(receipt)
    report=assess(root,now=NOW)
    assert report["status"]=="NOT_BID_READY_AUTHENTIC_RFQ_AND_PARTNER_CAPACITY_MISSING"
    assert report["approved_emails_sent_provider_count"]==5
    assert report["confirmed_deliveries_on_original_send_receipt"]==0
    assert report["genuine_inbound_partner_replies_at_receipt_creation"]==0
    assert report["current_inbound_replies_live_checked_by_module"] is False
    assert report["current_partner_reply_count"] is None
    assert report["genuine_supplier_quotes"]==0
    assert report["authenticated_complete_rfq_verified"] is False
    assert report["supplier_document_count"]==0
    assert report["bid_submission_authorised"] is False
    assert report["decision"]=="NO_BID_DEFAULT_UNTIL_ALL_GATES_INDEPENDENTLY_SATISFIED"
    assert report["outbound_sent_by_this_module"] is False
    assert report["empiredb_writes"] is False
    assert len(report["dispatches"])==5
    assert all(x["recipient_delivery_verified_at_original_receipt"] is False for x in report["dispatches"])
    assert all(x["current_delivery_and_reply_status"]=="UNKNOWN_REQUIRES_FRESH_GMAIL_CHECK" for x in report["dispatches"])
    p=save_private(root,report)
    assert p.name==OUTPUT.name
    assert stat.S_IMODE(p.stat().st_mode)==0o600
    reloaded=json.loads(p.read_text())
    assert reloaded["bid_submitted"] is False


@pytest.mark.parametrize("mutation",[
    lambda x:x.update(sent_count=6),
    lambda x:x.update(delivery_confirmed_count=5),
    lambda x:x.update(replies_verified_count=1),
    lambda x:x.update(rfq_obtained=True),
    lambda x:x.update(bid_submitted=True),
    lambda x:x["messages"].append(x["messages"][0]),
    lambda x:x["messages"][0].update(message_id="fabricated"),
    lambda x:x["messages"][0].update(recipient="someone@example.com"),
    lambda x:x["messages"][2].update(provider_label="DELIVERED"),
])
def test_fails_closed_on_counter_or_source_tamper(root:Path,mutation):
    receipt=_good_receipt()
    mutation(receipt)
    _write_receipt(root,receipt)
    assert not _valid_sent_receipt(receipt)
    report=assess(root,now=NOW)
    assert report["status"]=="HELD_INVALID_OR_MISSING_SENT_RECEIPT"
    assert report["approved_emails_sent_provider_count"]==0
    assert report["bid_submission_authorised"] is False


def test_absent_or_insecure_receipt_holds(root:Path):
    missing=assess(root,now=NOW)
    assert missing["approved_emails_sent_provider_count"]==0
    receipt=_good_receipt()
    _write_receipt(root,receipt)
    os.chmod(root/INCOMING,0o644)
    wrongmode=assess(root,now=NOW)
    assert wrongmode["status"]=="HELD_INVALID_OR_MISSING_SENT_RECEIPT"
    assert wrongmode["bid_submission_authorised"] is False


def test_symlink_input_rejected(root:Path):
    source=root/"outside.json"
    source.write_text(json.dumps(_good_receipt()))
    (root/INCOMING).symlink_to(source)
    r=assess(root,now=NOW)
    assert r["approved_emails_sent_provider_count"]==0
    assert r["decision"]=="NO_BID_DEFAULT_UNTIL_ALL_GATES_INDEPENDENTLY_SATISFIED"


def test_different_deadline_stages(root:Path):
    _write_receipt(root,_good_receipt())
    open_=assess(root,now=datetime(2026,10,26,8,0,tzinfo=timezone.utc))
    assert open_["questions_window_open"] is True
    assert open_["questions_deadline_uk"]=="2026-10-26T12:00:00+00:00"
    assert open_["submission_deadline_uk"]=="2026-10-30T12:00:00+00:00"
    later=assess(root,now=datetime(2026,10,27,9,tzinfo=timezone.utc))
    assert later["status"]=="CLARIFICATION_WINDOW_CLOSED_BID_STILL_NOT_READY"
    closed=assess(root,now=datetime(2026,10,30,12,tzinfo=timezone.utc))
    assert closed["status"]=="SUBMISSION_DEADLINE_PASSED_NO_BID_AUTHORITY"
    assert closed["submission_window_open"] is False


def test_illustrative_model_never_approved_price_or_revenue():
    c=_hypothetical_economics()
    assert c["illustrative_bid_ex_vat_gbp"]=="24500.00"
    assert c["hypothetical_lean_all_in_cost_gbp"]=="20104.00"
    assert c["hypothetical_lean_contribution_gbp"]=="4396.00"
    assert c["hypothetical_full_contribution_gbp"]=="-7987.50"
    assert c["max_all_in_cost_at_20pct_contribution_gbp"]=="19600.00"
    assert c["max_all_in_cost_at_25pct_contribution_gbp"]=="18375.00"
    assert c["actual_verified_delivery_cost_gbp"] is None
    assert c["revenue_gbp"] is None


def test_naive_datetime_is_invalid(root:Path):
    _write_receipt(root,_good_receipt())
    with pytest.raises(ValueError,match="AWARE_TIME_REQUIRED"):
        assess(root,now=datetime(2026,10,24,16,0))


def test_output_symlink_rejected(root:Path):
    protected=root/"protected"
    protected.write_text("do not overwrite")
    (root/OUTPUT).symlink_to(protected)
    with pytest.raises(ValueError,match="UNSAFE_PRIVATE"):
        save_private(root,{"status":"test"})
    assert protected.read_text()=="do not overwrite"


def test_private_parent_required(root:Path):
    _write_receipt(root,_good_receipt())
    os.chmod(root/INCOMING.parent,0o755)
    with pytest.raises(ValueError,match="PRIVATE_EMPIREOS_TENDER_DIRECTORY_REQUIRED"):
        assess(root,now=NOW)
