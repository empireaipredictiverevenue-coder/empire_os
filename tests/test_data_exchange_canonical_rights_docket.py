"""V18 field-rights docket from canonical genesis: zero commercial grants."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest

from empire_os.data_exchange_canonical_rights_docket import (
    build_canonical_rights_docket, API_PROJECTION,
)
from empire_os.data_exchange_observation_custody import CustodyIntegrityError
from empire_os.data_exchange_rights_preflight import PLANNING_FIELDS
from scripts import inspect_data_exchange_v16_live as inspector
from tests.test_data_exchange_temporal_quality import NOW, custody, snap


def docket(rows=None):
    data=rows if rows is not None else custody(
        (NOW-timedelta(hours=2),"non-permissioned"))
    return build_canonical_rights_docket(data,assessed_at=NOW)


def test_first_canonical_observation_produces_reviewable_rights_docket():
    doc=docket()
    assert doc["status"]=="REVIEW_DOCKET_READY_NOT_LICENSE_APPROVAL"
    assert doc["canonical_observation_count_in_window"]==1
    assert doc["canonical_head_sequence"]==0
    assert doc["observed_pilot_entity_count"]==3
    assert doc["pinned_pilot_complete"] is True
    assert doc["source_field_count"]==len(PLANNING_FIELDS)==7
    assert len(doc["review_checklist"])==8
    assert doc["dataset_stated_licence"]=="Open Government Licence v3.0"
    assert doc["source_field_rights_cleared"] is False
    assert doc["customer_delivery_enabled"] is False
    assert doc["data_resale_authorized"] is False
    assert doc["production_writes"] is False


def test_raw_api_fields_not_mistaken_for_derived_or_empire_timestamp():
    doc=docket()
    by_field={field["product_field"]:field for field in doc["field_evidence_docket"]}
    assert set(by_field)==set(API_PROJECTION)
    assert by_field["planning_permission_status"]["input_field_or_derivation"]=="planning-permission-status"
    assert by_field["site_area_hectares"]["input_field_or_derivation"]=="hectares"
    assert by_field["source_entry_date"]["input_field_or_derivation"]=="entry-date"
    assert by_field["source_observed_at"]["origin_class"]=="empire_observation"
    assert by_field["observed_history_change"]["origin_class"]=="empire_derived_evaluation"
    assert by_field["observed_history_change"]["derivation_currently_observable"] is False
    assert not any(field["client_distribution_authorised"] for field in by_field.values())


def test_second_canonical_observation_only_enables_derived_field_presence():
    rows=custody((NOW-timedelta(hours=50),"non-permissioned"),
                 (NOW-timedelta(hours=25),"permissioned"))
    doc=docket(rows)
    by_field={x["product_field"]:x for x in doc["field_evidence_docket"]}
    assert by_field["observed_history_change"]["derivation_currently_observable"] is True
    assert doc["canonical_head_sequence"]==1
    assert doc["source_field_rights_cleared"] is False


def test_docket_has_no_record_emails_addresses_or_data_payloads():
    text=json.dumps(docket(),sort_keys=True)
    assert "private@example" not in text
    assert "site-address" in text # explicitly excluded, not ingested
    assert "1739547" not in text
    assert "person" not in text.lower() or "personal_data" in text.lower()


@pytest.mark.parametrize("tamper",[
    lambda r:r[0]["snapshot_json"]["records"][0].update({"email":"person@private.invalid"}),
    lambda r:r[0].update({"chain_sha256":"f"*64}),
    lambda r:r[0]["snapshot_json"].update({"data_resale_authorized":True}),
])
def test_custody_mutation_never_passes_licensing_docket(tamper):
    rows=deepcopy(custody((NOW-timedelta(hours=1),"non-permissioned")))
    tamper(rows)
    with pytest.raises((ValueError,CustodyIntegrityError)):
        docket(rows)


def test_scientific_and_rights_share_one_custody_read(monkeypatch):
    rows=custody((NOW-timedelta(hours=1),"non-permissioned"))
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    reads=[]
    class ReadOnly:
        def __init__(self,dsn):assert dsn=="fixture-only"
        def read_window(self):
            reads.append(1)
            return rows
        def append_once(self,*args,**kw):raise AssertionError("no write")
    report=inspector.inspect_live(
        now=NOW,dsn="fixture-only",scientific_review=True,rights_docket=True,
        store_factory=ReadOnly)
    assert reads==[1]
    assert report["canonical_field_rights_docket"]["canonical_head_sha256"]==report["canonical_head_sha256"]
    assert report["scientific_evidence_review"]["status"]=="HOLD_INSUFFICIENT_SCIENTIFIC_EVIDENCE"
    assert report["database_writes"] is False


def test_default_inspector_output_unchanged(monkeypatch):
    rows=custody((NOW-timedelta(hours=1),"non-permissioned"))
    monkeypatch.setattr(inspector,"RELEASED_GENESIS_SHA256",rows[0]["chain_sha256"])
    class ReadOnly:
        def __init__(self,dsn):pass
        def read_window(self):return rows
    report=inspector.inspect_live(now=NOW,dsn="fixture-only",store_factory=ReadOnly)
    assert "canonical_field_rights_docket" not in report


def test_rights_docket_flag_fails_root_guard(monkeypatch,capsys):
    monkeypatch.setattr(inspector.os,"geteuid",lambda:1000)
    monkeypatch.setattr(inspector,"protected_dsn",
        lambda:(_ for _ in ()).throw(AssertionError("no secret read")))
    assert inspector.main(["--read-only","--rights-docket"])==2
    output=json.loads(capsys.readouterr().out)
    assert output["reason_code"]=="AUTHORISED_ROOT_READ_ACCESS_REQUIRED"
    assert output["database_writes"] is False
