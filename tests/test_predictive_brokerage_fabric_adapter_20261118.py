"""Original Predictive Fabric bridge receives only verified research features.

Uses the existing nine-data synthetic intake fixture; no test fixtures reach
EmpireDB, protected pinned model runners, CRM, tenant or customer files.
"""
from __future__ import annotations

from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from empire_os.predictive_cloud_brokerage_feature_adapter import (
    BrokerageResearchFabricAdapter,
    FEATURE_PATH, SCHEMA, build_internal_brokerage_features,
    refresh_internal_brokerage_features,
)
from empire_os.predictive_cloud_brokerage_research import (
    INDEX_PATH, read_internal_brokerage_rows,
)
from empire_os.predictive_cloud_fabric import (
    ExecutionAuthority, PredictiveCloudFabricContext, TenantContextSource,
)
from empire_os.predictive_fabric_production_bridge import (
    PredictiveFabricProductionBridge,
)

_spec = spec_from_file_location(
    "_brokerage_cloud_research_fixture",
    Path(__file__).parent / "test_predictive_cloud_brokerage_research_20261118.py",
)
_helper = module_from_spec(_spec)
_spec.loader.exec_module(_helper)
NOW = _helper.NOW
SYSTEM_CONTEXT = PredictiveCloudFabricContext(trace_id="system-private-observe")

def setup(tmp_path):
    root,data,source,views=_helper.fixture(tmp_path)
    assert _helper.transfer(root,data)["new_objects_written"] == 9
    return root,data,source,views

def ingest(root):
    return refresh_internal_brokerage_features(
        root, now=NOW, allow_noncanonical=True,
    )

def read(root,context=SYSTEM_CONTEXT,dataset_id=None):
    return PredictiveFabricProductionBridge().read_brokerage_research(
        context=context, repo_root=root, dataset_id=dataset_id, now=NOW,
    )

def test_all_nine_real_format_datasets_to_original_bridge(tmp_path):
    root,_,_,_=setup(tmp_path)
    r=ingest(root)
    assert r["status"]=="VERIFIED_INTERNAL_CLOUD_RESEARCH_FEATURES"
    assert r["sources_verified"]==5
    assert r["derived_views_verified"]==4
    assert r["feature_writes"]==1
    result=read(root)
    assert result["status"]=="VERIFIED_BROKERAGE_INTERNAL_RESEARCH_OBSERVATIONS"
    assert len(result["dataset_summaries"])==9
    assert result["feature_segment_count"]==4
    assert result["production_forecast_authorized"] is False
    assert result["model_training_authorized"] is False
    assert result["tenant_exposure_authorized"] is False
    assert result["commercial_conversion_probability"] is None
    assert result["customer_revenue"] is None
    assert result["buyer_outreach_authorized"] is False
    for segment in result["feature_segments"]:
        assert segment["observation_only"]
        assert segment["independent_buyer_demand_verified"] is False
        assert segment["commercial_forecast_input_admitted"] is False
        assert segment["source_snapshot_sha256"]
        assert segment["derived_view_sha256"]

def test_original_bridge_scoped_research_returns_only_one_dataset(tmp_path):
    root,_,_,_=setup(tmp_path)
    ingest(root)
    result=read(root,dataset_id="us_fda_regulatory_enforcement_landscape")
    assert len(result["dataset_summaries"])==1
    assert result["feature_segment_count"]==1
    assert result["feature_segments"][0]["metric"]=="published_enforcement_reports_in_bounded_sample"
    assert result["feature_segments"][0]["observed_count"]==2
    assert result["commercial_conversion_probability"] is None

def test_idempotent_feature_refresh_no_rewrites(tmp_path):
    root,_,_,_=setup(tmp_path)
    a=ingest(root)
    previous=(root/FEATURE_PATH).read_bytes()
    b=ingest(root)
    assert a["feature_writes"]==1
    assert b["feature_writes"]==0
    assert previous == (root/FEATURE_PATH).read_bytes()
    assert (root/FEATURE_PATH).stat().st_mode & 0o777 == 0o600

def test_public_or_tenant_contexts_denied(tmp_path):
    root,_,_,_=setup(tmp_path)
    ingest(root)
    contexts=[
        PredictiveCloudFabricContext(trace_id="proposal",authority=ExecutionAuthority.PROPOSE),
        PredictiveCloudFabricContext(trace_id="execution",authority=ExecutionAuthority.EXECUTE_BOUNDED),
        PredictiveCloudFabricContext(trace_id="tenant",tenant_id="tenant-1",tenant_source=TenantContextSource.AUTHENTICATED),
        PredictiveCloudFabricContext(trace_id="caller",approved_gates=frozenset({"execute:live_outbound"})),
        PredictiveCloudFabricContext(trace_id="buyer",buyer_id="buyer_1"),
    ]
    for context in contexts:
        with pytest.raises(PermissionError,match="SYSTEM_OBSERVE_CONTEXT"):
            read(root,context=context)

def test_original_ingest_changes_require_feature_refresh(tmp_path):
    root,data,sources,views=setup(tmp_path)
    ingest(root)
    name="global_legal_entity_identity_gb"
    p=data/(name+".csv")
    p.write_bytes(p.read_bytes().replace(b"SAMPLE1",b"SAMPLE9"))
    sources["datasets"][name]["source_snapshot_sha256"]=_helper.digest(p.read_bytes())
    _helper.save(root/_helper.SOURCE_RECEIPT,sources)
    assert _helper.transfer(root,data,now=NOW+timedelta(minutes=1))["new_objects_written"]==1
    with pytest.raises(ValueError,match="SOURCE_DRIFT_OR_INJECTION"):
        read(root)
    result=refresh_internal_brokerage_features(root,now=NOW+timedelta(minutes=1),allow_noncanonical=True)
    assert result["feature_writes"]==1
    # Subsequent read uses updated current-clock source facts.
    after=PredictiveFabricProductionBridge().read_brokerage_research(
        context=SYSTEM_CONTEXT,repo_root=root,now=NOW+timedelta(minutes=1))
    assert after["feature_segment_count"]==4

def test_forged_segmentation_rejected_independent_recomputation(tmp_path):
    root,_,_,_=setup(tmp_path)
    index_file=root/INDEX_PATH
    j=json.loads(index_file.read_text())
    for item in j["dataset_records"]:
        if item["dataset_id"]=="us_fda_regulatory_enforcement_landscape":
            item["segments"][0]["observed_sample_count"]=9_999
            break
    index_file.write_text(json.dumps(j))
    with pytest.raises(ValueError,match="SEGMENT_RECOMPUTE_MISMATCH"):
        ingest(root)

def test_private_feature_object_tamper_rejected(tmp_path):
    root,_,_,_=setup(tmp_path)
    ingest(root)
    p=root/FEATURE_PATH
    j=json.loads(p.read_text())
    j["features"]["segments"][0]["observed_count"]=1_000_000
    p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match="SOURCE_DRIFT_OR_INJECTION"):
        read(root)

def test_upstream_source_hold_blocks_feature_reader(tmp_path):
    root,data,sources,_=setup(tmp_path)
    ingest(root)
    sources["datasets"]["global_legal_entity_identity_gb"]["source_status"]="SOURCE_REFRESH_HELD"
    _helper.save(root/_helper.SOURCE_RECEIPT,sources)
    with pytest.raises(ValueError,match="SOURCE_STALE_OR_UNTRUSTED"):
        read(root)

def test_missing_or_corrupted_cloud_object_blocks_feature_reader(tmp_path):
    root,_,_,_=setup(tmp_path)
    ingest(root)
    matches=list((root/INDEX_PATH.parent/"objects").glob("us_fda_regulatory_enforcement_landscape_*.csv"))
    assert len(matches)==1
    matches[0].write_bytes(b"tampered")
    with pytest.raises(ValueError,match="SOURCE_OWNER_SHA256_MISMATCH"):
        read(root)

def test_default_noncanonical_write_held(tmp_path):
    root,_,_,_=setup(tmp_path)
    assert refresh_internal_brokerage_features(root,now=NOW)["status"]=="NONCANONICAL_PRIVATE_RESEARCH_OWNER_HELD"
    assert not (root/FEATURE_PATH).exists()
    with pytest.raises(ValueError,match="MISSING_OR_UNSAFE_BROKERAGE_RECEIPT"):
        read(root)

def test_systemd_receipt_attests_cloud_feature_without_writes():
    """Exercise the original owner's receipt in memory, not on disk."""
    from empire_os import data_brokerage_enterprise_feed as feed
    writes=[]
    def capture(path,data):
        writes.append((path,json.loads(data)))
    with patch.dict(os.environ,{"INVOCATION_ID":"a"*32}), patch.object(
            feed,"_atomic",side_effect=capture):
        result=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),
            {"status":"PROFESSIONAL_FEED_ALL_SOURCES_WITHIN_CADENCE","network_requests":0},
            {"status":"ALL_VERIFIED_VIEWS_CURRENT_OR_SOURCES_HELD","view_writes":0},
            now=NOW,
            cloud_research={"status":"VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL"},
            fabric_research={"status":"VERIFIED_UNCHANGED_CLOUD_RESEARCH_FEATURES",
                             "feature_segments":75},
        )
    assert result["timer_receipt_written"] is True
    assert len(writes)==1
    assert writes[0][1]["predictive_cloud_research_status"]=="VERIFIED_BROKERAGE_RESEARCH_INPUTS_INTERNAL"
    assert writes[0][1]["predictive_fabric_research_feature_segments"]==75
    assert writes[0][1]["predictive_fabric_production_training_authorized"] is False
    assert writes[0][1]["customer_delivery_authorized"] is False
    with patch.dict(os.environ,{"INVOCATION_ID":"bogus"}), patch.object(
            feed,"_atomic",side_effect=AssertionError("FALSE_SYSTEMD_RECEIPT")):
        held=feed.record_scheduled_owner_observation(
            Path("/srv/empire_os"),{}, {},now=NOW,
            cloud_research={"status":"FAKE"},fabric_research={"feature_segments":999},
        )
    assert held["timer_receipt_written"] is False


def test_bad_tenant_feature_manifest_never_admitted(tmp_path):
    root,_,_,_=setup(tmp_path)
    ingest(root)
    p=root/FEATURE_PATH
    j=json.loads(p.read_text())
    j["tenant_exposure_authorized"]=True
    p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match="MANIFEST_AUTHORITY_HELD"):
        read(root)
