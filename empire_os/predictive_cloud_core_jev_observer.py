"""Bounded Predictive Cloud/Jev infrastructure snapshot review; no authority."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from hashlib import sha256
from typing import Any

SCHEMA="empire.predictive_cloud.core_jev_observation.v1"
SERVICES=("postgresql@18-main","pgbouncer","empire-founder-dashboard-api",
          "empire-laya-shadow","empire-predictive-cloud-materializer.timer")
SOURCES={
 "cloud":("runtime/predictive_cloud/status_latest.json","empire.predictive_cloud.status.v2","generated_at"),
 "predictive":("runtime/predictive_intelligence/latest.json","empire.predictive_intelligence.v1","generated_at"),
 "jev":("runtime/jev_client_pain_discovery/aggregate_latest.json","empire.jev.client_pain_production_observe.v1","generated_at_utc"),
}
CORE_FILE="empire_os/predictive_cloud_materializer.py"
RUNNER="scripts/run_predictive_cloud_materializer.py"


def _read(root:Path,relative:str)->tuple[dict[str,Any],str|None]:
    file=root/relative
    try:
        if file.is_symlink() or not file.is_file() or file.stat().st_size>1000000:
            return {},None
        raw=file.read_bytes()
        if len(raw)>1000000:return {},None
        obj=json.loads(raw)
        if type(obj) is not dict:return {},None
        return obj,sha256(raw).hexdigest()
    except (OSError,UnicodeError,ValueError):
        return {},None


def _recent(value:object,now:datetime,days:int)->bool:
    if type(value) is not str or len(value)>40:return False
    try:
        moment=datetime.fromisoformat(value.replace("Z","+00:00"))
        if moment.utcoffset() is None:return False
        age=now-moment.astimezone(timezone.utc)
        return timedelta(0)<=age<=timedelta(days=days)
    except (TypeError,ValueError,OverflowError):
        return False


def _count(value:object,max_value:int=1000000)->int|None:
    return value if type(value) is int and 0<=value<=max_value else None


def _hash_file(file:Path)->str|None:
    try:
        if file.is_symlink() or not file.is_file() or file.stat().st_size>250000:
            return None
        return sha256(file.read_bytes()).hexdigest()
    except OSError:return None


def inspect_cloud_core_jev(*,repo_root:Path,guard_root:Path,
                           effective_runner:str,services:dict[str,str],
                           now:datetime)->dict[str,Any]:
    if (type(now) is not datetime or now.utcoffset() is None
        or not isinstance(repo_root,Path) or not isinstance(guard_root,Path)):
        raise ValueError("EXPLICIT_PATHS_AND_AWARE_CLOCK_REQUIRED")
    if (type(effective_runner) is not str or len(effective_runner)>4096
        or type(services) is not dict or set(services)!=set(SERVICES)
        or any(type(x) is not str or x not in
               ("active","inactive","failed","unknown") for x in services.values())):
        raise ValueError("EXACT_CORE_SERVICE_CONTRACT_REQUIRED")
    root=repo_root.resolve()
    guard=guard_root.resolve()
    current=now.astimezone(timezone.utc)
    observed={}
    digests={}
    for name,(relative,schema,clock_field) in SOURCES.items():
        raw,digest=_read(root,relative)
        observed[name]=raw
        digests[name]=digest
    cloud=observed["cloud"]
    prediction=observed["predictive"]
    jev=observed["jev"]
    def base_ok(name,max_age_days):
        obj=observed[name]
        return (
            obj.get("schema_version")==SOURCES[name][1]
            and obj.get("mode")=="OBSERVE"
            and obj.get("execution_authority")=="none"
            and _recent(obj.get(SOURCES[name][2]),current,max_age_days))
    cloud_ok=(base_ok("cloud",1)
              and _count(cloud.get("component_count"),1000) is not None
              and _count(cloud.get("available_component_count"),1000) is not None
              and cloud["available_component_count"]<=cloud["component_count"])
    prediction_ok=(base_ok("predictive",1)
                   and _count(prediction.get("matched_outcome_count")) is not None)
    jev_ok=(base_ok("jev",2)
            and jev.get("status")=="CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY"
            and type(jev.get("model_calls")) is int and jev["model_calls"]==0
            and jev.get("database_writes") is False
            and jev.get("crm_writes") is False)
    canonical_hash=_hash_file(root/CORE_FILE)
    guarded_hash=_hash_file(guard/CORE_FILE)
    runner_hash=_hash_file(guard/RUNNER)
    guard_selected=bool(
        effective_runner==str(guard/RUNNER)
        and guarded_hash and runner_hash)
    parity=bool(canonical_hash and guarded_hash
                and canonical_hash==guarded_hash)
    services_up=all(value=="active" for value in services.values())
    blockers=[]
    if not services_up:blockers.append("CORE_SERVICE_INACTIVE")
    if not cloud_ok:blockers.append("CLOUD_INVENTORY_NOT_TRUSTED_OR_FRESH")
    if not prediction_ok:blockers.append("PREDICTIVE_INTELLIGENCE_NOT_FRESH")
    if not jev_ok:blockers.append("JEV_RESEARCH_EVIDENCE_UNAVAILABLE_OR_STALE")
    if not guard_selected:blockers.append("PROTECTED_MATERIALIZER_NOT_SELECTED")
    if not parity:blockers.append("CANONICAL_MATERIALIZER_NOT_IN_PARITY_WITH_GUARD")
    blockers.append("INDEPENDENT_TENANT_ISSUER_AND_FROZEN_OUTCOME_PROOFS_REQUIRED")
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE",
        "status":"CORE_INFRASTRUCTURE_OBSERVATION_NO_FINANCIAL_AUTHORITY",
        "core_services":dict(services),"core_services_operational":services_up,
        "cloud_inventory_observed":bool(cloud_ok),
        "cloud_components_available":cloud["available_component_count"] if cloud_ok else None,
        "cloud_components_total":cloud["component_count"] if cloud_ok else None,
        "predictive_intelligence_observed":bool(prediction_ok),
        "source_reported_matched_outcomes":prediction.get("matched_outcome_count") if prediction_ok else None,
        "jev_research_observation_available":bool(jev_ok),
        "jev_model_predictions_admitted":False,
        "jev_revenue_ground_truth_admitted":False,
        "protected_materializer_selected":guard_selected,
        "canonical_materializer_parity":parity,
        "canonical_materializer_digest":canonical_hash,
        "protected_materializer_digest":guarded_hash,
        "protected_runner_digest":runner_hash,
        "input_snapshot_digests":digests,
        "blockers":sorted(set(blockers)),
        "canonical_database":"EmpireDB",
        "bank_settled_cash_minor":None,
        "training_examples_eligible":0,
        "model_weights_updated":False,
        "outbound_authorized":False,
        "external_jev_calls":0,"bank_or_wallet_actions":0,
        "database_actions":0,"service_restarts":0,
        "execution_authority":"none",
    }
