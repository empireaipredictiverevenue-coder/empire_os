"""Source custody readiness for the EXISTING EmpireOS enterprise diagnostic.

Classifies only signed-off OBSERVE snapshots of Revenue Pulse, Economic
Memory and Buyer Capacity. A self-described 'canonical' source or local
SHA256 does NOT prove original SQL custody, independently verified cash,
tenant authorisation, financial day census or client report release.
No DB connection, credentials, customer identities, source row exports.
"""
from __future__ import annotations

from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
from typing import Any

SCHEMA="empire.enterprise_finance_source_readiness.v1"
SOURCE_DEFINITIONS=(
    ("revenue_pulse","runtime/revenue_pulse/latest.json",
     "empire.revenue-pulse.v3","generated_at"),
    ("economic_memory","runtime/economic_memory/latest.json",
     "empire.economic_memory.v1","generated_at"),
    ("buyer_capacity","runtime/buyer_capacity_readiness/latest.json",
     "empire.buyer_capacity_readiness.v1","observed_at"),
)
MAX_BYTES=150_000
MAX_AGE=timedelta(hours=48)
FUTURE_GRACE=timedelta(minutes=5)
PROOFS=(
    ("ORIGINAL_CUSTOMER_LEDGER_CUSTODY",
     "Independently authenticated original customer ledger rows, tenant identity and a source-signed or independently verified selection receipt"),
    ("RECOGNISED_EVENT_ORDER_MATCH",
     "One canonical recognised event/order match through the existing dedicated role (a single event is not the daily total)"),
    ("SETTLEMENT_AND_REFUND_FINALITY",
     "Source-level settlement/payment reconciliation including refunds and reversals"),
    ("COMPLETE_DAY_CENSUS",
     "Bounded authoritative full-day recognised-event count with coverage, late-arrival cut-off and independent read rights"),
    ("BUYER_COMMERCIAL_AUTHORITY",
     "Independently verified buyer capacity, binding terms and deliverability"),
    ("FORECAST_OUTCOME_CALIBRATION",
     "Frozen forecast linked to independently finalised outcomes and baseline"),
    ("CUSTOMER_REPORT_RELEASE",
     "Specific customer tenant permissions, scope, reviewed report and signed release"),
)


def _source(root:Path,name:str,rel:str,schema:str,time_key:str,at:datetime):
    p=root/rel
    base={
        "source":name,"relative_path":rel,
        "status":"SOURCE_UNAVAILABLE_OR_INVALID",
        "local_file_sha256":None,
        "selected_schema":None,
        "snapshot_at_utc":None,
        "within_48h":False,
        "local_hash_is_source_attestation":False,
        "original_financial_rows_independently_verified":False,
    }
    try:
        if (p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root)
                or p.stat().st_size>MAX_BYTES):
            return base,None
        initial=p.stat()
        b=p.read_bytes()
        final=p.stat()
        if (initial.st_size!=len(b) or final.st_size!=len(b)
                or initial.st_mtime_ns!=final.st_mtime_ns or
                initial.st_ino!=final.st_ino):
            return base,None
        result=json.loads(b)
        if not isinstance(result,dict):
            return base,None
        observed=datetime.fromisoformat(result[time_key].replace("Z","+00:00"))
        if observed.utcoffset() is None:
            return base,None
        timestamp=observed.astimezone(timezone.utc)
        fresh=-FUTURE_GRACE<=at-timestamp<=MAX_AGE
        if (result.get("schema_version")!=schema
                or result.get("mode")!="OBSERVE"
                or result.get("execution_authority")!="none"):
            return base,None
        base.update({
            "status":("INTERNAL_SNAPSHOT_ONLY" if fresh else
                      "STALE_OR_FUTURE_INTERNAL_SNAPSHOT"),
            "local_file_sha256":sha256(b).hexdigest(),
            "selected_schema":schema,
            "snapshot_at_utc":timestamp.isoformat(),
            "within_48h":fresh,
        })
        return base,result
    except (ValueError,TypeError,KeyError,AttributeError,OSError,UnicodeError,
            json.JSONDecodeError):
        return base,None


def _bounded(value:Any)->int|None:
    return value if type(value) is int and 0<=value<=9_000_000_000_000_000 else None


def review_finance_source_readiness(
    root:Path,*,as_of:datetime|None=None
)->dict[str,Any]:
    now=as_of or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware readiness review as_of required")
    now=now.astimezone(timezone.utc)
    root=Path(root).resolve()
    reviewed={}
    read={}
    for name,path,schema,time_key in SOURCE_DEFINITIONS:
        safe,data=_source(root,name,path,schema,time_key,now)
        reviewed[name]=safe
        read[name]=data if safe["within_48h"] else None
    pulse=read["revenue_pulse"]
    memory=read["economic_memory"]
    buyers=read["buyer_capacity"]
    pulse_view={
        "status":"UNKNOWN_NOT_PROVEN",
        "reported_24h_recognized_cents":None,
        "reported_24h_verified_payment_count":None,
        "reported_24h_fulfilment_count":None,
        "source_snapshot_not_authoritative_day_census":True,
    }
    if pulse is not None:
        truth=pulse.get("recognized_revenue_truth")
        win=pulse.get("current_window")
        if (pulse.get("snapshot_source")=="canonical_empiredb_postgres"
                and isinstance(truth,dict) and isinstance(win,dict)
                and truth.get("forecast_included_in_truth") is False
                and pulse.get("execution_allowed") is False
                and pulse.get("payment_mutation") is False
                and pulse.get("accounting_mutation") is False):
            fields=(
                _bounded(win.get("recognized_revenue_cents")),
                _bounded(win.get("verified_payments")),
                _bounded(win.get("fulfilments")),
                _bounded(truth.get("recognized_revenue_cents")),
            )
            if (all(x is not None for x in fields)
                    and win.get("hours")==24
                    and fields[0]==fields[3]):
                pulse_view.update({
                    "status":"OBSERVED_CANONICAL_LABELLED_SNAPSHOT_NOT_AUDIT",
                    "reported_24h_recognized_cents":fields[0],
                    "reported_24h_verified_payment_count":fields[1],
                    "reported_24h_fulfilment_count":fields[2],
                })
    economic={
        "status":"UNKNOWN_NOT_PROVEN",
        "reported_calibration_evidence_count":None,
        "promoted_learning":None,
    }
    if memory is not None and (memory.get("accounting_authority")=="none"
          and memory.get("commercial_authority")=="none"
          and memory.get("promoted_learning") is False):
        n=_bounded(memory.get("calibration_evidence_count"))
        if n is not None:
            economic.update({
                "status":"OBSERVED_SHADOW_LEARNING_NOT_FINANCIAL_PROOF",
                "reported_calibration_evidence_count":n,
                "promoted_learning":False,
            })
    commercial={
        "status":"UNKNOWN_NOT_PROVEN",
        "reported_verified_capacity_count":None,
        "reported_verified_terms_count":None,
        "reported_verified_delivery_count":None,
    }
    if buyers is not None and buyers.get("revenue_recognition") is False:
        values=tuple(_bounded(buyers.get(k)) for k in (
            "capacity_verified","terms_verified","delivery_verified"
        ))
        if all(v is not None for v in values):
            commercial.update({
                "status":"OBSERVED_BUYER_CAPACITY_SNAPSHOT_NOT_AUTHENTICATION",
                "reported_verified_capacity_count":values[0],
                "reported_verified_terms_count":values[1],
                "reported_verified_delivery_count":values[2],
            })
    # These conclusions do NOT depend on snapshot values. A 'canonical'
    # string, zero, a matching report digest or a caller-supplied extraction
    # cannot establish source finality or customer-specific attestation.
    requirements=[{
        "evidence_gap":code,
        "status":"NO_INDEPENDENT_PROOF_ADMITTED",
        "required_to_close":explanation,
    } for code,explanation in PROOFS]
    healthy_sources=sum(s["within_48h"] for s in reviewed.values())
    return {
        "schema_version":SCHEMA,
        "status":("SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED"
                  if healthy_sources==len(SOURCE_DEFINITIONS) and
                  pulse_view["status"]!="UNKNOWN_NOT_PROVEN" and
                  economic["status"]!="UNKNOWN_NOT_PROVEN" and
                  commercial["status"]!="UNKNOWN_NOT_PROVEN"
                  else "HOLD_MISSING_STALE_OR_INCONSISTENT_SOURCE_OBSERVATIONS"),
        "as_of_utc":now.isoformat(),
        "canonical_database":"EmpireDB",
        "read_only":True,
        "source_snapshot_count":len(reviewed),
        "current_internal_source_snapshot_count":healthy_sources,
        "source_receipts":reviewed,
        "revenue_pulse_observation":pulse_view,
        "economic_memory_observation":economic,
        "buyer_capacity_observation":commercial,
        "independent_finance_evidence_requirements":requirements,
        "required_proofs_not_admitted_count":len(requirements),
        "canonical_single_event_reader_role_provisioning_independently_checked":False,
        "source_report_consistency_is_independent_custody":False,
        "source_file_hash_is_external_signature":False,
        "customer_record_completeness_verified":False,
        "actual_recognised_revenue_independently_verified":False,
        "customer_invoice_or_statement_approved":False,
        "independent_money_movement_proof_obtained":False,
        "report_distribution_authorized":False,
        "commercial_automation_authorized":False,
        "empiredb_reads_performed":False,
        "new_source_credentials_used":False,
        "execution_authority":"none","mode":"OBSERVE",
    }
