"""No-write acceptance of genuine sourced company evidence vs original model gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/review_ich_original_predictive_model_acceptance_readonly_20261108.py"
spec=importlib.util.spec_from_file_location("original_ich_predictive_acceptance",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def fixtures():
    now=datetime.now(timezone.utc)
    packet=json.loads(m.PACKET.read_text())
    rights={
        "result":"INDEPENDENT_GENUINE_CRM_TENANT_ICH_HELD_BINDING_VERIFIED",
        "canonical_owner_tenant_verified":True,
        "cross_tenant_rejected":True,"wrong_source_rejected":True,
        "source_review_state":"PENDING_HELD","customer_source_admitted":False,
        "customer_forecast_enabled":False
    }
    trend={
        "mode":"OBSERVE","status":"AVAILABLE",
        "generated_at":now.isoformat(),"prediction_ready":False,
        "independent_source_admitted":False,
        "source_admission_state":"UNVERIFIED_LOCAL_SNAPSHOT_ONLY",
        "execution_authority":"none","analysis_executed":False,
        "probability_ready_product_count":0,"timing_ready_product_count":0,
        "verified_terminal_outcome_count":0,"unknown_is_zero":False
    }
    formula={
        "mode":"OBSERVE","status":"AVAILABLE",
        "generated_at":now.isoformat(),"prediction_ready":False,
        "independent_source_admitted":False,
        "source_admission_state":"UNVERIFIED_LOCAL_SNAPSHOT_ONLY",
        "execution_authority":"none"
    }
    status={"mode":"OBSERVE","framework_operational":False,
            "customer_forecast_verified":False,
            "commercial_prediction_authorized":False,"execution_authority":"none"}
    v4={k:False for k in ("real_source_rights_verified",
                         "production_tenant_source_admitted",
                         "live_consumer_activated","commercial_prediction_authorized")}
    return dict(packet=packet,rights=rights,trend=trend,formula=formula,
                status=status,v4=v4,now=now)

def test_real_original_source_can_be_researched_but_not_predicted():
    o=m.audit(**fixtures())
    assert o["status"]=="GENUINE_SOURCE_HELD_MODEL_NOT_READY_VERIFIED"
    assert o["canonical_crm_tenant_reader_verified"] is True
    assert o["original_future_trend_materializer_available"] is True
    assert o["original_future_trend_analysis_executed"] is False
    assert o["verified_terminal_outcomes"]==0
    assert o["independently_validated_customer_forecast"] is False
    assert o["customer_data_delivery_authorized"] is False
    assert o["no_new_model_or_system_created"] is True

@pytest.mark.parametrize("group,key,value",[
    ("rights","customer_source_admitted",True),
    ("rights","cross_tenant_rejected",False),
    ("rights","source_review_state","CANDIDATE_REVIEW_HELD"),
    ("rights","result","unverified"),
    ("trend","independent_source_admitted",True),
    ("trend","prediction_ready",True),
    ("trend","probability_ready_product_count",1),
    ("trend","verified_terminal_outcome_count",1),
    ("trend","analysis_executed",True),
    ("trend","unknown_is_zero",True),
    ("formula","prediction_ready",True),
    ("formula","execution_authority","execute_bounded"),
    ("status","customer_forecast_verified",True),
    ("status","framework_operational",True),
    ("v4","production_tenant_source_admitted",True),
    ("v4","real_source_rights_verified",True),
])
def test_no_false_source_admission_or_fake_customer_forecast(group,key,value):
    f=fixtures()
    f[group][key]=value
    with pytest.raises(RuntimeError):
        m.audit(**f)

@pytest.mark.parametrize("tamper",[
    "customer_delivery_authorized","production_source_admitted",
    "source_rights_document_has_been_owner_attested",
])
def test_original_source_packet_cannot_forge_entitlement(tamper):
    f=fixtures()
    row=next(x for x in f["packet"]["records"] if x["domain"]=="ich-services.co.uk")
    if tamper=="customer_delivery_authorized":
        row[tamper]=True
    else:row["official_uk_source_observation"][tamper]=True
    with pytest.raises(RuntimeError,match="source_rights_promotion_forbidden"):
        m.audit(**f)

def test_fixed_corporate_record_sha_and_read_only_original_source():
    assert m.SOURCE=="31787934624aac98439d48603641951d910e6df96880de9dafe4e35cb2614b5d"
    assert m.PACKET.exists()
    assert m.TREND.name=="future_trend_latest.json"
    assert m.FORMULA.name=="formula_latest.json"
    assert m.ORIGINAL_VERIFIER.name=="verify_original_crm_ich_held_binding_readonly_20261108.py"
    source=SCRIPT.read_text()
    for prohibited in ("CREATE TABLE","CREATE ROLE","INSERT INTO","UPDATE public",
                       "DELETE FROM","ALTER SYSTEM","service restart"):
        assert prohibited not in source
