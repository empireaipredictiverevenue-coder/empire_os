"""Protect original commercial intake provenance and evidence promotion gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

import scripts.review_predictive_commercial_requirements_20261020 as cli
from empire_os.predictive_commercial_requirements import (
    review_commercial_requirement, tampa_roofing_founder_example,
)
from empire_os.predictive_commercial_supply_readiness import review_original_lead_readiness
from empire_os.predictive_commercial_fulfilment import plan_commercial_fulfilment
from empire_os.predictive_existing_owner_pickup import (
    review_department_owner_pickup, review_existing_a2a_owner_research,
)
from empire_os.enterprise_finance_evidence_readiness import review_finance_source_readiness
from empire_os.predictive_commercial_evidence_chain import review_original_commercial_evidence_chain
from test_predictive_commercial_requirements_fulfilment import NOW, source_packets


def original_packets(tmp_path):
    req=review_commercial_requirement(
        tampa_roofing_founder_example(),as_of=NOW,
        source_instruction_kind="FOUNDER_OR_CUSTOMER_UNVERIFIED_REQUIREMENT_DRAFT",
    )
    supply=review_original_lead_readiness(
        *source_packets(),as_of=NOW,
        industry=req["industry"],country=req["country"],
        state=req["state"],city=req["city"],
    )
    plan=plan_commercial_fulfilment(req,supply,as_of=NOW)
    a2a=review_existing_a2a_owner_research(req,None,None,as_of=NOW)
    finance=review_finance_source_readiness(tmp_path,as_of=NOW)
    owners=review_department_owner_pickup(req,plan,supply,finance,a2a)
    return req,plan,supply,finance,a2a,owners


def test_evidence_gates_reject_unverified_originals_and_preserve_digest(tmp_path):
    pkt=original_packets(tmp_path)
    value=review_original_commercial_evidence_chain(
        *pkt,original_intake_bytes_sha256="a"*64,
    )
    assert value["status"]=="ORIGINAL_COMMERCIAL_EVIDENCE_NOT_YET_ADMITTED"
    assert value["original_requirement_revision_sha256"]==pkt[0]["requirement_revision_sha256"]
    assert value["original_intake_bytes_sha256_untrusted_file_identity"]=="a"*64
    assert len(value["stages"])==6
    assert value["first_unmet_stage"]=="CUSTOMER_ORDER_AND_BUYING_AUTHORITY"
    assert value["existing_owner_queue_count"]==8
    assert value["authenticated_customer_order_verified"] is False
    assert value["verified_customer_specific_lead_inventory"] is None
    assert value["authenticated_realized_gross_profit_minor"] is None
    assert value["cloud_learning_eligible"] is False
    assert value["commercial_execution_eligible"] is False
    assert value["database_writes"] is False
    assert value["outbound_sent"] is False


def test_example_is_not_a_customer_record_and_has_no_file_digest(tmp_path):
    value=review_original_commercial_evidence_chain(
        *original_packets(tmp_path),original_intake_bytes_sha256=None,
    )
    assert value["source_intake_fingerprinted_not_customer_authenticated"] is False
    assert value["existing_owner_acceptance_verified"] is False


@pytest.mark.parametrize("tamper",["wrong_revision","cross_market","fake_owner_ack","unauthorized_dispatch","fake_customer_order","invalid_digest"])
def test_chain_fail_closed_on_forged_or_mixed_upstream_reports(tmp_path,tamper):
    req,plan,supply,finance,a2a,owners=deepcopy(original_packets(tmp_path))
    digest="a"*64
    if tamper=="wrong_revision":
        plan["original_requirement_revision_sha256"]="b"*64
    elif tamper=="cross_market":
        supply["research_target_market_city"]="Chicago"
    elif tamper=="fake_owner_ack":
        owners["owner_required_action_queue"][0]["original_cryptographic_owner_acknowledgement"]={"signed": True}
    elif tamper=="unauthorized_dispatch":
        owners["owner_handoffs_dispatched"]=1
    elif tamper=="fake_customer_order":
        req["source_customer_order_authenticated"]=True
    elif tamper=="invalid_digest":
        digest="untrusted"
    with pytest.raises(ValueError):
        review_original_commercial_evidence_chain(
            req,plan,supply,finance,a2a,owners,
            original_intake_bytes_sha256=digest,
        )


def test_original_input_sha_is_hash_of_exact_bytes_and_source_untouched(tmp_path):
    src=tmp_path/"customer.json"
    payload=json.dumps(tampa_roofing_founder_example(),separators=(",",":")).encode()
    src.write_bytes(payload)
    value,digest=cli._read_with_custody(str(src))
    assert value["requested_qualified_leads"]==20
    assert digest==sha256(payload).hexdigest()
    assert src.read_bytes()==payload
    assert cli._read(str(src))==value


def test_symlink_and_non_regular_file_rejected_without_read(tmp_path):
    src=tmp_path/"valid.json"
    src.write_bytes(b'{"bounded":true}')
    alias=tmp_path/"indirect.json"
    alias.symlink_to(src)
    with pytest.raises((OSError,ValueError)):
        cli._read_with_custody(str(alias))
    with pytest.raises((OSError,ValueError)):
        cli._read_with_custody(str(tmp_path))
    if hasattr(os,"mkfifo"):
        fifo=tmp_path/"pipe"
        os.mkfifo(fifo)
        with pytest.raises((OSError,ValueError)):
            cli._read_with_custody(str(fifo))


def test_completed_planning_intake_exposes_only_untrusted_source_digest(tmp_path,monkeypatch,capsys):
    from test_predictive_commercial_requirements_operator import fixture_root, fake_clock
    fixture_root(tmp_path)
    fake_clock(monkeypatch)
    payload=json.dumps(tampa_roofing_founder_example()).encode()
    source=tmp_path/"requirement.json"
    source.write_bytes(payload)
    monkeypatch.setattr("sys.argv",[
        "operator","--read-only","--repo-root",str(tmp_path),
        "--a2a-owner-root",str(tmp_path),"--requirement-intake",str(source),
    ])
    assert cli.main()==0
    report=json.loads(capsys.readouterr().out)
    chain=report["authenticated_original_commercial_evidence_chain"]
    assert chain["original_intake_bytes_sha256_untrusted_file_identity"]==sha256(payload).hexdigest()
    assert chain["original_requirement_revision_sha256"]==report["commercial_requirement"]["requirement_revision_sha256"]
    assert chain["commercial_execution_eligible"] is False
    assert report["dispatch_performed"] is False
    assert report["database_writes"] is False
    assert source.read_bytes()==payload
