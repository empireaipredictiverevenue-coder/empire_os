"""V19 evidence collection scope and privacy truths: absolutely no release."""
import json
from copy import deepcopy
from datetime import timedelta

import pytest

from empire_os.data_exchange_observation_custody import CustodyIntegrityError
from empire_os.data_exchange_canonical_rights_docket import build_canonical_rights_docket
from empire_os.data_exchange_release_evidence_register import (
    build_release_evidence_register, REQUIREMENTS, SCHEMA,
)
from scripts import inspect_data_exchange_v16_live as inspector
from tests.test_data_exchange_temporal_quality import NOW, custody


def original():
    return custody((NOW-timedelta(hours=1),"non-permissioned"))


def register(rows=None):
    docket=build_canonical_rights_docket(original() if rows is None else rows,assessed_at=NOW)
    return build_release_evidence_register(docket)


def test_single_genesis_produces_full_review_work_queue_without_signoffs():
    result=register()
    assert result["schema_version"]==SCHEMA
    assert result["status"]=="EVIDENCE_COLLECTION_READY_RELEASE_HELD"
    assert result["review_controls_total"]==8
    assert result["review_controls_pending"]==8
    assert result["review_controls_completed"]==0
    assert result["field_scope_count"]==7
    assert result["canonical_head_sequence"]==0
    assert len(result["evidence_scope_sha256"])==64
    assert {x["control_id"] for x in result["evidence_collection_tasks"]}==set(REQUIREMENTS)
    assert all(not c["reviewer_signoff_verified"] for c in result["evidence_collection_tasks"])
    assert all(not c["customer_release_authority"] for c in result["evidence_collection_tasks"])
    assert not result["independent_reviewer_signed_off"]
    assert not result["founder_release_approved"]
    assert result["customer_delivery_enabled"] is False
    assert result["data_resale_authorized"] is False
    assert result["production_writes"] is False


def test_persistence_claim_precise_raw_source_privacy_still_unknown():
    doc=build_canonical_rights_docket(original(),assessed_at=NOW)
    assert "source_personal_information_collected" not in doc
    assert doc["source_personal_information_persisted"] is False
    assert doc["raw_source_response_transiently_decoded"] is True
    assert doc["raw_source_response_privacy_review_status"]=="NOT_PERFORMED"
    assert doc["raw_source_response_contains_personal_information"] is None
    result=build_release_evidence_register(doc)
    assert result["transient_raw_response_decoded_in_memory"] is True
    assert result["transient_raw_response_privacy_review"]=="NOT_PERFORMED"
    assert result["raw_source_personal_information_present"] is None
    assert result["custody_persisted_fields_allowlist_validated"] is True
    assert result["personal_contact_fields_persisted_in_custody"] is False
    assert result["privacy_erasure_requests_require_separate_review"] is True


def test_all_controls_require_specific_evidence_not_glib_approval():
    result=register()
    controls={c["control_id"]:c for c in result["evidence_collection_tasks"]}
    for c in controls.values():
        assert len(c["evidence_required"])==2
        assert c["review_status"]=="UNSUBMITTED_INDEPENDENT_REVIEW"
        assert c["evidence_received"] is False
        assert c["reviewer_identity_verified"] is False
        assert c["reviewer_signoff_verified"] is False
    assert "full transient JSON" in controls["privacy"]["evidence_required"][0]
    assert "corrections" in controls["retention"]["evidence_required"][0]
    assert "explicit founder release approval" in controls["release_authority"]["evidence_required"][1]


def test_same_source_history_replay_is_deterministic_but_unanchored():
    a=register()
    b=register()
    assert a==b
    assert a["digest_semantics"]=="LOCAL_UNANCHORED_DETERMINISTIC_SCOPE_NOT_SIGNATURE"


def test_second_snapshot_binds_new_evidence_scope_without_unlocking_rights():
    rows=custody((NOW-timedelta(hours=51),"non-permissioned"),
                 (NOW-timedelta(hours=25),"permissioned"))
    a=register()
    b=register(rows)
    assert a["canonical_head_sequence"]==0
    assert b["canonical_head_sequence"]==1
    assert a["evidence_scope_sha256"]!=b["evidence_scope_sha256"]
    assert b["review_controls_pending"]==8
    assert b["founder_release_approved"] is False
    assert b["execution_authority"]=="NONE"


@pytest.mark.parametrize("tamper",[
    lambda d:d.update({"customer_delivery_enabled":True}),
    lambda d:d.update({"source_field_rights_cleared":True}),
    lambda d:d.update({"source_personal_information_persisted":True}),
    lambda d:d.update({"raw_source_response_privacy_review_status":"CLEARED"}),
    lambda d:d.update({"raw_source_response_contains_personal_information":False}),
    lambda d:d["field_evidence_docket"][0].update({"client_distribution_authorised":True}),
    lambda d:d["review_checklist"][0].update({"signoff_artifact_present":True}),
    lambda d:d["proposed_attribution_preview"].update({"displayed_on_customer_product":True}),
])
def test_forged_scope_clearance_or_privacy_decision_is_rejected(tamper):
    d=build_canonical_rights_docket(original(),assessed_at=NOW)
    tamper(d)
    with pytest.raises((CustodyIntegrityError,ValueError)):
        build_release_evidence_register(d)


def test_legacy_inspector_returns_v19_without_second_db_read(monkeypatch):
    rows=original()
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    read_count=[]
    class Reader:
        def __init__(self,dsn):assert dsn=="test-only-dsn"
        def read_window(self):
            read_count.append(1)
            return rows
        def append_once(self,*args,**kwargs):
            raise AssertionError("release review must never write")
    result=inspector.inspect_live(now=NOW,dsn="test-only-dsn",rights_docket=True,
                                  store_factory=Reader)
    assert read_count==[1]
    rights=result["canonical_field_rights_docket"]
    assert rights["release_evidence_register"]["canonical_head_sha256"]==result["canonical_head_sha256"]
    assert rights["release_evidence_register"]["review_controls_pending"]==8
    assert rights["customer_delivery_enabled"] is False
    assert result["database_writes"] is False


def test_v19_stays_off_when_rights_docket_not_requested(monkeypatch):
    rows=original()
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    class Reader:
        def __init__(self,dsn):pass
        def read_window(self):return rows
    result=inspector.inspect_live(now=NOW,dsn="test-only-dsn",store_factory=Reader)
    assert "canonical_field_rights_docket" not in result
