"""Existing CRM reader integration refuses forged counts and customer claims."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from empire_os.predictive_existing_founder_crm_bridge import (
    SCHEMA, PROBE_SCHEMA, held, review_existing_crm_reader,
    run_existing_founder_crm_review,
)
import scripts.review_predictive_founder_crm_visibility_20261020 as cli

NOW=datetime(2026,10,20,15,tzinfo=timezone.utc)


def source(commercial=0,predictive=0,total=0):
    return {
        "schema_version":PROBE_SCHEMA,
        "mode":"OBSERVE",
        "status":("TENANT_VISIBLE_SALES_PROSPECTS_PRESENT" if commercial+predictive
                  else "NO_TENANT_VISIBLE_SALES_PROSPECTS"),
        "reason_code":"CANONICAL_SOURCE_RECEIPTS_NOT_CHECKED",
        "read_only":True,
        "raw_customer_rows_read":False,
        "tenant_binding_mutated":False,
        "prospect_ingest_performed":False,
        "outbound_authorized":False,
        "payment_authorized":False,
        "execution_authority":"NONE",
        "canonical_global_intake_count_proven":False,
        "website_to_founder_visibility_proven":False,
        "visible_commercial_sales_prospects":commercial,
        "visible_predictive_revenue_prospects":predictive,
        "visible_total_prospects":total,
    }


def test_exact_zero_snapshot_reports_visibility_only():
    report=review_existing_crm_reader(source(),read_at=NOW)
    assert report["schema_version"]==SCHEMA
    assert report["status"]=="NO_TENANT_VISIBLE_SALES_PROSPECTS_SOURCE_UNVERIFIED"
    assert report["counts"]["visible_total_prospects"]==0
    assert report["canonical_original_acquisition_probe_checked"] is False
    assert report["original_customer_order_authenticated"] is False
    assert report["crm_customer_specific_source_receipt_authenticated"] is False
    assert report["realized_revenue_proven"] is False
    assert report["crm_write_performed"] is False


def test_nonzero_visibility_does_not_promote_customer_or_revenue():
    r=review_existing_crm_reader(source(2,1,9),read_at=NOW)
    assert r["counts"]["visible_total_prospects"]==9
    assert r["status"]=="TENANT_VISIBLE_SALES_COHORT_PRESENT_SOURCE_UNVERIFIED"
    assert r["first_customer_purchasing_authority_verified"] is False
    assert r["realized_revenue_proven"] is False


@pytest.mark.parametrize("field,value",[
    ("schema_version","other"),("mode","LIVE"),("read_only",False),
    ("execution_authority","send"),("raw_customer_rows_read",True),
    ("tenant_binding_mutated",True),("prospect_ingest_performed",True),
    ("outbound_authorized",True),("payment_authorized",True),
    ("canonical_global_intake_count_proven",True),
    ("website_to_founder_visibility_proven",True),
    ("reason_code","SOURCE_RECEIPT_TRUSTED"),("status","UNVERIFIED"),
    ("visible_commercial_sales_prospects",False),
    ("visible_commercial_sales_prospects",-1),
    ("visible_commercial_sales_prospects",2),
    ("visible_total_prospects",True),
])
def test_bad_upstream_claims_fail_closed(field,value):
    p=source()
    p[field]=value
    r=review_existing_crm_reader(p,read_at=NOW)
    assert r["status"]=="EXISTING_FOUNDER_CRM_READER_HELD"
    assert r["counts"] is None
    assert r["original_customer_order_authenticated"] is False


def test_hidden_foreign_prospects_not_relabelled_as_sales():
    p=source(total=5)
    r=review_existing_crm_reader(p,read_at=NOW)
    assert r["status"]=="NO_TENANT_VISIBLE_SALES_PROSPECTS_SOURCE_UNVERIFIED"
    assert r["counts"]["visible_total_prospects"]==5


def test_status_count_contradiction_fail_closed():
    p=source(commercial=1,total=1)
    p["status"]="NO_TENANT_VISIBLE_SALES_PROSPECTS"
    assert review_existing_crm_reader(p,read_at=NOW)["counts"] is None


@pytest.mark.parametrize("code,payload",[
    (1,json.dumps(source())),(0,"not JSON"),(0,"[]"),
    (0,"x"*12001),(True,json.dumps(source())),
])
def test_bad_reader_no_leak_and_no_customer_promotion(code,payload):
    r=run_existing_founder_crm_review(reader=lambda:(code,payload),as_of=NOW)
    assert r["status"]=="EXISTING_FOUNDER_CRM_READER_HELD"
    assert "not JSON" not in json.dumps(r)
    assert r["original_customer_order_authenticated"] is False


def test_read_only_consumer_uses_provided_owning_report_without_mutation():
    original=source(commercial=1,total=2)
    snap=deepcopy(original)
    r=run_existing_founder_crm_review(
        reader=lambda:(0,json.dumps(original)),as_of=NOW,
    )
    assert original==snap
    assert r["counts"]["visible_commercial_sales_prospects"]==1
    assert r["canonical_original_acquisition_probe_checked"] is False


def test_cli_outputs_bounded_hold_when_owner_reader_unavailable(monkeypatch,capsys):
    monkeypatch.setattr(cli,"run_existing_founder_crm_review",
                        lambda:held("EXISTING_CRM_PROBE_UNAVAILABLE"))
    monkeypatch.setattr("sys.argv",["crm","--read-only"])
    assert cli.main()==0
    x=json.loads(capsys.readouterr().out)
    assert x["counts"] is None
    assert x["execution_authority"]=="none"
