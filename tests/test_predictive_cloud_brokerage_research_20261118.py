"""Cloud intake tests: all nine real-format datasets, admission, hash and privacy.

Synthetic fixtures ONLY under temp dirs, no database, internet, tenant data or
production scheduler side effects.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import unittest

from empire_os.data_brokerage_enterprise_feed import HEADERS, SOURCES, SCHEMA as SOURCE_SCHEMA, STATE as SOURCE_RECEIPT
from empire_os.data_brokerage_enterprise_packaging import VIEWS, SCHEMA as VIEW_SCHEMA, SNAPSHOT as VIEW_RECEIPT
from empire_os.predictive_cloud_brokerage_research import (
    import_brokerage_research_inputs, read_internal_brokerage_rows as _cloud_read_rows,
    _segments, INDEX_PATH,
)

from pytest import raises

NOW = datetime(2026, 11, 18, 14, 15, tzinfo=timezone.utc)
CONTEXT="EMPIRE_INTERNAL_RESEARCH_OBSERVE"

def read_internal_brokerage_rows(*args, **kwargs):
    return _cloud_read_rows(*args, now=NOW, **kwargs)

def encode(columns, rows):
    buf = io.StringIO(newline="")
    w=csv.DictWriter(buf,fieldnames=columns)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def save(path, doc):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc))

def sample_row(cols, dataset):
    row={k:"" for k in cols}
    if dataset == "us_disaster_territory_activity_sample":
        row.update(state="TX",distinct_declaration_count_in_sample="1",coverage_flag="LATEST_1000_SOURCE_ROWS_ONLY_NO_CLAIMS")
    elif dataset == "uk_healthcare_territory_coverage":
        row.update(region="London",service_type="Nursing",location_count="1",distinct_provider_count="1")
    elif dataset == "uk_renewable_projects_active_stage_research":
        row.update(project_ref="112",technology="Solar Photovoltaics",development_status="Planning Application Submitted",capacity_mw="2.2")
    elif dataset == "us_fda_regulatory_enforcement_landscape":
        row.update(sector="device",publisher_classification="Class II",published_state="CA",
                   report_month="2026-11",distinct_reports_in_sample="2")
    else:
        row[next(iter(cols))]="SAMPLE1"
    return row

def fixture(tmp_path):
    root=tmp_path/"root"
    data=tmp_path/"original_data"
    data.mkdir()
    src={"schema":SOURCE_SCHEMA,"customer_delivery_authorized":False,
         "source_redistribution_approved":False,"commercial_sales_authorized":False,
         "datasets":{}}
    views={"schema":VIEW_SCHEMA,"customer_delivery_authorized":False,
           "sales_authorized":False,"public_marketplace_enabled":False,"views":{}}
    for name,values in SOURCES.items():
        data_csv=encode(HEADERS[name],[sample_row(HEADERS[name],name)])
        (data/(name+".csv")).write_bytes(data_csv)
        src["datasets"][name]={
            "source_status":"VERIFIED_UNCHANGED","quality_pass":True,
            "source_snapshot_sha256":digest(data_csv),
            "last_success_at":(NOW-timedelta(hours=1)).isoformat(),
            "last_checked_at":(NOW-timedelta(hours=1)).isoformat(),
            "row_count":1,"publisher":values[3],
            "licence_release_approved":False,"customer_delivery_authorized":False,
            "commercial_sales_authorized":False,"source_url":"https://publisher.example.test/official",
            "sample_not_full_population":True,
        }
    for name,spec in VIEWS.items():
        csv_data=encode(spec["columns"],[sample_row(spec["columns"],name)])
        (data/(name+".csv")).write_bytes(csv_data)
        views["views"][name]={
            "status":"VIEW_VERIFIED_INTERNAL","row_count":1,
            "view_sha256":digest(csv_data),
            "source_sha256":src["datasets"][spec["source_id"]]["source_snapshot_sha256"],
            "customer_delivery_authorized":False,"sales_authorized":False,
            "resale_licence_cleared":False,
            "publisher_source_url":"https://publisher.example.test/official",
        }
    save(root/SOURCE_RECEIPT,src)
    save(root/VIEW_RECEIPT,views)
    return root,data,src,views

def transfer(root,data,now=NOW):
    return import_brokerage_research_inputs(root,dataset_root=data,now=now,
                                            allow_noncanonical=True)

def test_real_format_all_nine_datasets_cloud_accepted(tmp_path):
    root,data,_,_=fixture(tmp_path)
    r=transfer(root,data)
    assert r["source_datasets_admitted"]==5
    assert r["derived_views_admitted"]==4
    assert r["source_rows_accessible"]==5
    assert r["derived_view_rows_accessible"]==4
    assert r["new_objects_written"]==9
    assert r["production_training_samples_admitted"]==0
    index=json.loads((root/INDEX_PATH).read_text())
    assert len(index["dataset_records"])==9
    assert index["source_rows_accessible"]==5
    assert index["derived_view_rows_accessible"]==4
    assert index["not_additive_source_and_view_rows"]
    assert index["source_redistribution_authorized"] is False
    assert index["tenant_exposure_authorized"] is False
    assert index["model_calibration_ready"] is False
    assert (root/INDEX_PATH.parent).stat().st_mode & 0o777==0o700
    objdir=root/INDEX_PATH.parent/"objects"
    assert objdir.stat().st_mode & 0o777==0o700
    assert (root/INDEX_PATH).stat().st_mode & 0o777==0o600
    assert len(list(objdir.glob("*.csv")))==9
    assert all(f.stat().st_mode & 0o777==0o600 for f in objdir.glob("*.csv"))

def test_query_actual_cloud_rows_and_restrict_scope(tmp_path):
    root,data,_,_=fixture(tmp_path)
    transfer(root,data)
    with raises(PermissionError,match="SYSTEM_RESEARCH_CONTEXT"):
        read_internal_brokerage_rows(root,"us_fda_regulatory_enforcement_landscape")
    row=read_internal_brokerage_rows(root,
        "us_fda_regulatory_enforcement_landscape",system_research_context=CONTEXT,
        filters={"sector":"device"})
    assert len(row["rows"])==1
    assert row["rows"][0]["publisher_classification"]=="Class II"
    assert row["research_only"] and not row["training_authorized"]
    empty=read_internal_brokerage_rows(root,
        "us_fda_regulatory_enforcement_landscape",system_research_context=CONTEXT,
        filters={"sector":"drug"})
    assert empty["matched_rows_in_current_snapshot"]==0
    with raises(ValueError,match="UNKNOWN_BROKERAGE_DATASET"):
        read_internal_brokerage_rows(root,"../../../etc/passwd",system_research_context=CONTEXT)
    with raises(ValueError,match="LIMIT"):
        read_internal_brokerage_rows(root,"global_legal_entity_identity_gb",
                                     system_research_context=CONTEXT,limit=100_000)
    with raises(ValueError,match="FILTER_FIELD"):
        read_internal_brokerage_rows(root,"global_legal_entity_identity_gb",
                                     system_research_context=CONTEXT,filters={"password":"x"})

def test_idempotent_no_copy_duplicates(tmp_path):
    root,data,_,_=fixture(tmp_path)
    one=transfer(root,data)
    two=transfer(root,data,now=NOW+timedelta(minutes=1))
    assert one["new_objects_written"]==9
    assert two["new_objects_written"]==0
    assert len(list((root/INDEX_PATH.parent/"objects").glob("*.csv")))==9

def test_source_refresh_auto_version_changes_only_one_cloud_object(tmp_path):
    root,data,src,_=fixture(tmp_path)
    first=transfer(root,data)
    assert first["new_objects_written"]==9
    name="global_legal_entity_identity_gb"
    original=(data/(name+".csv")).read_bytes()
    assert b"SAMPLE1" in original
    (data/(name+".csv")).write_bytes(original.replace(b"SAMPLE1",b"SAMPLE2"))
    src["datasets"][name]["source_snapshot_sha256"]=digest((data/(name+".csv")).read_bytes())
    src["datasets"][name]["last_checked_at"]=(NOW+timedelta(minutes=1)).isoformat()
    src["datasets"][name]["last_success_at"]=(NOW+timedelta(minutes=1)).isoformat()
    save(root/SOURCE_RECEIPT,src)
    # New source receipt is not automatically admitted by an old Cloud index.
    with raises(ValueError,match="SOURCE_STALE_OR_UNTRUSTED"):
        read_internal_brokerage_rows(root,name,system_research_context=CONTEXT)
    out=transfer(root,data,now=NOW+timedelta(minutes=2))
    assert out["new_objects_written"]==1
    assert len(list((root/INDEX_PATH.parent/"objects").glob("*.csv")))==10
    row=read_internal_brokerage_rows(root,name,system_research_context=CONTEXT)
    assert row["rows"][0]["lei"]=="SAMPLE2"
    assert row["tenant_exposure_authorized"] is False


def test_tampered_source_prevents_all_cloud_import(tmp_path):
    root,data,_,_=fixture(tmp_path)
    p=data/"uk_cqc_corporate_care_locations.csv"
    p.write_bytes(p.read_bytes()+b"\nBAD")
    with raises(ValueError,match="SOURCE_OWNER_SHA256_MISMATCH"):
        transfer(root,data)
    assert not (root/INDEX_PATH).exists()

def test_cross_derived_source_provenance_fails(tmp_path):
    root,data,src,views=fixture(tmp_path)
    views["views"]["us_disaster_territory_activity_sample"]["source_sha256"]="f"*64
    save(root/VIEW_RECEIPT,views)
    with raises(ValueError,match="BROKERAGE_DERIVED_VIEW_HOLD"):
        transfer(root,data)
    assert not (root/INDEX_PATH).exists()

def test_hold_or_overdue_source_fails_closed(tmp_path):
    root,data,src,views=fixture(tmp_path)
    src["datasets"]["us_fda_regulatory_enforcement_sample"]["quality_pass"]=False
    save(root/SOURCE_RECEIPT,src)
    with raises(ValueError,match="BROKERAGE_UPSTREAM_SOURCE_HOLD"):
        transfer(root,data)
    src["datasets"]["us_fda_regulatory_enforcement_sample"]["quality_pass"]=True
    src["datasets"]["us_fda_regulatory_enforcement_sample"]["last_checked_at"]=(NOW-timedelta(days=9)).isoformat()
    save(root/SOURCE_RECEIPT,src)
    with raises(ValueError,match="BROKERAGE_UPSTREAM_OVERDUE_HOLD"):
        transfer(root,data)

def test_historical_cloud_object_not_current_after_original_changed(tmp_path):
    root,data,src,_=fixture(tmp_path)
    transfer(root,data)
    src["datasets"]["global_legal_entity_identity_gb"]["source_status"]="SOURCE_REFRESH_HELD"
    save(root/SOURCE_RECEIPT,src)
    with raises(ValueError,match="SOURCE_STALE_OR_UNTRUSTED"):
        read_internal_brokerage_rows(root,"global_legal_entity_identity_gb",
                                    system_research_context=CONTEXT)

def test_cloud_object_tamper_failclosed(tmp_path):
    root,data,_,_=fixture(tmp_path)
    transfer(root,data)
    p=next((root/INDEX_PATH.parent/"objects").glob("us_fda_regulatory_enforcement_landscape_*.csv"))
    p.write_bytes(p.read_bytes()+b"FOREIGN")
    with raises(ValueError,match="SOURCE_OWNER_SHA256_MISMATCH"):
        read_internal_brokerage_rows(root,"us_fda_regulatory_enforcement_landscape",
                                    system_research_context=CONTEXT)

def test_no_public_distribution_enablement_on_source(tmp_path):
    root,data,src,_=fixture(tmp_path)
    src["customer_delivery_authorized"]=True
    save(root/SOURCE_RECEIPT,src)
    with raises(ValueError,match="BROKERAGE_OWNER_AUTHORITY_MISMATCH"):
        transfer(root,data)

def test_fda_segment_counts_only_from_published_reports():
    sample=[
       {"sector":"device","distinct_reports_in_sample":"4"},
       {"sector":"drug","distinct_reports_in_sample":"2"},
       {"sector":"device","distinct_reports_in_sample":"1"},
    ]
    segs=_segments("us_fda_regulatory_enforcement_landscape",sample)
    assert [(s["value"],s["observed_sample_count"]) for s in segs]==[("device",5),("drug",2)]
    assert all(s["commercial_forecast_input_admitted"] is False for s in segs)
    with raises(ValueError,match="FDA_SEGMENT_MEASUREMENT_INVALID"):
        _segments("us_fda_regulatory_enforcement_landscape",[{"sector":"food","distinct_reports_in_sample":"not a count"}])

def test_noncanonical_automatic_import_held(tmp_path):
    root,data,_,_=fixture(tmp_path)
    r=import_brokerage_research_inputs(root,dataset_root=data,now=NOW)
    assert r["status"]=="NONCANONICAL_RESEARCH_IMPORT_HELD"
    assert not (root/INDEX_PATH).exists()
