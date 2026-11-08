"""Read-only genuine-source-to-original Predictive Cloud acceptance audit.

Independent verifier of the original 066 rights receipt and existing live
Predictive Cloud predictive-materializer/output states. It is NOT a new
ingestion/model/registry/release module. No customer delivery, DB mutation,
provider calls, synthetic source "predictions" or revenue claims.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from urllib.request import urlopen

ROOT=Path("/home/ubuntu/empire_worktrees/predictive_cloud_usage_review_20261107")
PACKET=ROOT/"docs/PREDICTIVE_CLOUD_FIRST_PARTY_RESEARCH_COHORT_20261108.json"
PINNED_PACKET_SHA="18e6dd0947989fceae071940b0177dfad6c7fdf83b2905cfe4b4f73f850da9ef"
ORIGINAL_VERIFIER=ROOT/"scripts/verify_original_crm_ich_held_binding_readonly_20261108.py"
SOURCE="31787934624aac98439d48603641951d910e6df96880de9dafe4e35cb2614b5d"
TREND=Path("/srv/empire_os/runtime/predictive_cloud/future_trend_latest.json")
FORMULA=Path("/srv/empire_os/runtime/predictive_cloud/formula_latest.json")
STATUS=Path("/srv/empire_os/runtime/predictive_cloud/status_latest.json")
V4_URL="http://127.0.0.1:8766/v1/predictive-cloud/v4/shadow-readiness"

def _json_file(p:Path)->dict:
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 500_000:
        raise RuntimeError("original_source_or_materializer_snapshot_unavailable")
    o=json.loads(p.read_text(encoding="utf-8"))
    if type(o) is not dict:raise RuntimeError("unexpected_original_snapshot_type")
    return o

def audit(*,packet:dict,rights:dict,trend:dict,formula:dict,
          status:dict,v4:dict,now:datetime)->dict:
    if type(now) is not datetime or now.tzinfo is None:
        raise RuntimeError("independent_utc_clock_required")
    rows=packet.get("records")
    if type(rows) is not list or len(rows)!=4:raise RuntimeError("original_fixed_source_cohort_changed")
    ich=[r for r in rows if r.get("domain")=="ich-services.co.uk"]
    if len(ich)!=1 or ich[0].get("research_policy")!="PASS_RESEARCH_ONLY":
        raise RuntimeError("original_ich_research_record_not_admitted_for_review")
    e=ich[0].get("official_uk_source_observation")
    if (type(e) is not dict or e.get("source_evidence_digest")!=SOURCE
        or e.get("customer_delivery_authorized") is not False
        or e.get("production_source_admitted") is not False
        or e.get("source_rights_document_has_been_owner_attested") is not False
        or ich[0].get("customer_delivery_authorized") is not False):
        raise RuntimeError("independent_public_register_source_rights_promotion_forbidden")
    if (rights.get("result")!="INDEPENDENT_GENUINE_CRM_TENANT_ICH_HELD_BINDING_VERIFIED"
        or rights.get("canonical_owner_tenant_verified") is not True
        or rights.get("cross_tenant_rejected") is not True
        or rights.get("wrong_source_rejected") is not True
        or rights.get("source_review_state")!="PENDING_HELD"
        or rights.get("customer_source_admitted") is not False
        or rights.get("customer_forecast_enabled") is not False):
        raise RuntimeError("original_crm_066_source_rights_readback_not_held")
    for model in (trend,formula):
        stamp=model.get("generated_at")
        try:
            ts=datetime.fromisoformat(stamp).astimezone(timezone.utc)
        except (TypeError,ValueError,AttributeError):
            raise RuntimeError("current_predictive_model_snapshot_timestamp_invalid") from None
        age=now.astimezone(timezone.utc)-ts
        if not timedelta(0)<=age<=timedelta(minutes=30):
            raise RuntimeError("predictive_model_snapshot_stale_or_future")
        if (model.get("mode")!="OBSERVE"
            or model.get("status")!="AVAILABLE"
            or model.get("prediction_ready") is not False
            or model.get("independent_source_admitted") is not False
            or model.get("source_admission_state")!="UNVERIFIED_LOCAL_SNAPSHOT_ONLY"
            or model.get("execution_authority")!="none"):
            raise RuntimeError("model_snapshot_inconsistent_with_held_source")
    if (trend.get("analysis_executed") is not False
        or trend.get("probability_ready_product_count")!=0
        or trend.get("timing_ready_product_count")!=0
        or trend.get("verified_terminal_outcome_count")!=0
        or trend.get("unknown_is_zero") is not False):
        raise RuntimeError("unverified_probability_or_outcome_promoted")
    for model in (status,v4):
        if type(model) is not dict:raise RuntimeError("original_cloud_status_not_a_mapping")
    if (status.get("mode")!="OBSERVE"
        or status.get("framework_operational") is not False
        or status.get("customer_forecast_verified") is not False
        or status.get("commercial_prediction_authorized") is not False
        or status.get("execution_authority")!="none"):
        raise RuntimeError("original_predictive_cloud_runtime_inconsistent")
    if any(v4.get(k) is not False for k in (
        "real_source_rights_verified",
        "production_tenant_source_admitted",
        "live_consumer_activated",
        "commercial_prediction_authorized",
    )):
        raise RuntimeError("shadow_source_admission_inconsistent_with_original_066")
    return {
        "schema_version":"empire.predictive_cloud.ich_original_acceptance_observation.v1",
        "status":"GENUINE_SOURCE_HELD_MODEL_NOT_READY_VERIFIED",
        "mode":"READ_ONLY_PRODUCTION_OBSERVATION",
        "checked_at_utc":now.astimezone(timezone.utc).isoformat(),
        "source":"Companies House ICH SERVICES LTD company number 02745893",
        "original_ich_evidence_digest":SOURCE,
        "official_record_independently_observed":True,
        "canonical_crm_tenant_reader_verified":True,
        "original_rights_decision":"PENDING_HELD",
        "company_corporate_facts_available_for_research":True,
        "source_rights_independently_attested_for_customer_use":False,
        "original_production_source_admitted":False,
        "original_future_trend_materializer_available":True,
        "original_future_trend_analysis_executed":False,
        "original_future_trend_prediction_ready":False,
        "real_customer_probability_cohort_verified":False,
        "verified_terminal_outcomes":0,
        "independently_validated_customer_forecast":False,
        "execution_authority":"none",
        "customer_data_delivery_authorized":False,
        "no_new_model_or_system_created":True,
        "no_paid_requests_or_database_changes":True,
        "next_required_gates":[
          "independent_source_rights_purpose_privacy_withdrawal_owner_attestation",
          "separately_authorised_tenant_source_admission_consumer",
          "independent_outcome_cohort_and_model_calibration",
          "authenticated_original_consumer_read_and_negative_tenant_receipts",
        ],
    }

def run()->dict:
    if os.geteuid()!=0:raise RuntimeError("original_root_owned_rights_verifier_required")
    if sha256(PACKET.read_bytes()).hexdigest()!=PINNED_PACKET_SHA:
        raise RuntimeError("original_independent_source_packet_modified")
    if ORIGINAL_VERIFIER.is_symlink() or not ORIGINAL_VERIFIER.is_file():
        raise RuntimeError("original_tenant_verifier_missing")
    p=subprocess.run(
        ["/srv/empire_os/.venv/bin/python","-B",str(ORIGINAL_VERIFIER)],
        cwd="/srv/empire_os",capture_output=True,text=True,timeout=20)
    if p.returncode:
        raise RuntimeError("original_rights_verifier_did_not_pass")
    try:rights=json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("original_rights_verification_report_malformed") from None
    with urlopen(V4_URL,timeout=4) as r:
        if r.status!=200:raise RuntimeError("original_v4_readiness_unavailable")
        v4=json.loads(r.read(200000))
    return audit(packet=_json_file(PACKET),rights=rights,trend=_json_file(TREND),
        formula=_json_file(FORMULA),status=_json_file(STATUS),v4=v4,
        now=datetime.now(timezone.utc))

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
