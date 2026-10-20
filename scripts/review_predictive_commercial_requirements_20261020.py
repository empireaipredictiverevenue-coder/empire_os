"""Global multi-industry commercial requirement planning (OBSERVE-only).

No implicit customer or geographic default. Use --requirement-intake for an
original typed request; --example-tampa-roofing is explicitly demonstrative.
Read-only owner snapshots, no dispatch, quotes or commercial promises.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from empire_os.predictive_commercial_requirements import (
    tampa_roofing_founder_example,review_commercial_requirement,
)
from empire_os.predictive_commercial_supply_readiness import (
    review_lead_readiness_runtime,
)
from empire_os.predictive_commercial_fulfilment import plan_commercial_fulfilment
from empire_os.predictive_existing_owner_pickup import (
    read_existing_a2a_owner_reports,review_department_owner_pickup,
)
from empire_os.enterprise_finance_evidence_readiness import review_finance_source_readiness
from empire_os.predictive_commercial_intake_readiness import inspect_commercial_intake_draft
from empire_os.predictive_commercial_evidence_chain import review_original_commercial_evidence_chain

MAX_SIZE=200_000


def _report_incomplete_intake(status:str,*,readiness=None,code:str,source_sha256=None)->int:
    """Print a readable machine-safe hold without leaking user-entered details."""
    print(json.dumps({
        "schema_version":"empire.predictive_revenue.commercial_requirement_operator.v1",
        "status":status,"mode":"OBSERVE","hold_code":code,
        "commercial_intake_readiness":readiness,
        "original_intake_bytes_sha256_untrusted_file_identity":source_sha256,
        "next_action":"COMPLETE_OR_CORRECT_ORIGINAL_INTAKE_BEFORE_PLANNING",
        "review_command":"empire-predictive-observe commercial-intake /home/ubuntu/commercial_requirement.json",
        "template_command":"empire-predictive-observe commercial-template",
        "customer_order_authenticated":False,
        "lead_inventory_or_price_inferred":False,
        "owner_handoffs_prepared":0,"owner_handoffs_dispatched":0,
        "source_owner_reports_read":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    },sort_keys=True,allow_nan=False))
    return 0 if status=="COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS" else 2


def _read_with_custody(pathname:str)->tuple[dict,str]:
    """Hash the exact bounded bytes parsed, not a second mutable path read."""
    p=Path(pathname)
    if p.is_symlink():
        raise ValueError("source symlink refused")
    flags=os.O_RDONLY | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_NONBLOCK",0)
    fd=os.open(p,flags)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=MAX_SIZE:
            raise ValueError("approved regular bounded JSON file required")
        payload=os.read(fd,MAX_SIZE+1)
        after=os.fstat(fd)
        if (len(payload)!=before.st_size or
                (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise ValueError("original source changed while reading")
    finally:
        os.close(fd)
    x=json.loads(payload.decode("utf-8"))
    if not isinstance(x,dict):
        raise ValueError("expected bounded original owner JSON packet")
    return x,sha256(payload).hexdigest()


def _read(pathname:str)->dict:
    return _read_with_custody(pathname)[0]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--repo-root",default="/srv/empire_os")
    parser.add_argument("--a2a-owner-root",
                        default="/home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020",
                        help="Original A2A owner runtime, read-only and never published")
    parser.add_argument("--requirement-intake",default=None,
                        help="Exact tenant-scoped existing founder/customer intake JSON")
    parser.add_argument("--example-tampa-roofing",action="store_true",
                        help="Optional illustrative fixture, NOT a customer order or target market")
    parser.add_argument("--original-roof-survey",default=None)
    parser.add_argument("--supplier-owner-quotes",default=None)
    parser.add_argument("--cloud-what-if",default=None)
    parser.add_argument("--lead-owner-eligibility-preview",default=None)
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    if args.requirement_intake and args.example_tampa_roofing:
        parser.error("select original requirement OR an explicit fictional example")
    if not args.requirement_intake and not args.example_tampa_roofing:
        if any((args.original_roof_survey,args.supplier_owner_quotes,
                args.cloud_what_if,args.lead_owner_eligibility_preview)):
            parser.error("source evidence requires a specific original requirement")
        out={
            "schema_version":"empire.predictive_revenue.commercial_requirement_operator.v1",
            "status":"COMMERCIAL_REQUIREMENT_INPUT_REQUIRED",
            "mode":"OBSERVE","current_customer_order":None,
            "default_industry":None,"default_market":None,
            "example_tampa_roofing_used":False,
            "next_action":"SUPPLY_ORIGINAL_CUSTOMER_INTAKE_OR_SELECT_EXPLICIT_TEST_EXAMPLE",
            "recorded_live_customer_contract":False,
            "dispatch_performed":False,"database_writes":False,
            "outbound_sent":False,"execution_authority":"none",
        }
        print(json.dumps(out,sort_keys=True,allow_nan=False))
        return 0
    intake_source_sha256=None
    if args.requirement_intake:
        try:
            raw,intake_source_sha256=_read_with_custody(args.requirement_intake)
        except (OSError,ValueError,UnicodeError,TypeError):
            return _report_incomplete_intake(
                "COMMERCIAL_INTAKE_FILE_INVALID",code="READABLE_BOUNDED_JSON_OBJECT_REQUIRED",
            )
        intake_readiness=inspect_commercial_intake_draft(raw)
        if intake_readiness["status"]!="COMMERCIAL_INTAKE_PLANNING_FIELDS_SUPPLIED":
            return _report_incomplete_intake(
                intake_readiness["status"],readiness=intake_readiness,
                source_sha256=intake_source_sha256,
                code="COMPLETE_REQUIRED_PLANNING_FIELDS"
                if intake_readiness["status"]=="COMMERCIAL_INTAKE_MISSING_PLANNING_FIELDS"
                else "EXACT_INTAKE_SCHEMA_REQUIRED",
            )
    else:
        raw=tampa_roofing_founder_example()
        intake_readiness=None
    try:
        req=review_commercial_requirement(
            raw,as_of=now,
            source_instruction_kind=(
                "FOUNDER_EXAMPLE_TARGET_NOT_CUSTOMER_ORDER" if args.example_tampa_roofing
                else "FOUNDER_OR_CUSTOMER_UNVERIFIED_REQUIREMENT_DRAFT"),
        )
    except (ValueError,TypeError):
        return _report_incomplete_intake(
            "COMMERCIAL_INTAKE_INVALID_VALUES",
            readiness=intake_readiness,code="REVIEW_FIELD_TYPES_COUNTRY_CURRENCY_AND_APPROVAL_PROOFS",
            source_sha256=intake_source_sha256,
        )
    supply=review_lead_readiness_runtime(
        args.repo_root,as_of=now,
        industry=req["industry"],country=req["country"],
        state=req["state"],city=req["city"],
    )
    quotes=None
    if args.supplier_owner_quotes:
        source=_read(args.supplier_owner_quotes)
        if set(source)!={"source_owner_quote_claims"} or not isinstance(
                source["source_owner_quote_claims"],list):
            raise ValueError("original procurement owner bounded quote envelope required")
        quotes=source["source_owner_quote_claims"]
    plan=plan_commercial_fulfilment(
        req,supply,as_of=now,
        original_roof_project=(_read(args.original_roof_survey)
                               if args.original_roof_survey else None),
        supplier_owner_quotes=quotes,
        hypothetical_cloud=(_read(args.cloud_what_if) if args.cloud_what_if else None),
        lead_owner_eligibility_preview=(_read(args.lead_owner_eligibility_preview)
                                        if args.lead_owner_eligibility_preview else None),
    )
    owner_a2a=read_existing_a2a_owner_reports(
        args.a2a_owner_root,requirement=req,as_of=now,
    )
    finance=review_finance_source_readiness(Path(args.repo_root),as_of=now)
    owners=review_department_owner_pickup(req,plan,supply,finance,owner_a2a)
    chain=review_original_commercial_evidence_chain(
        req,plan,supply,finance,owner_a2a,owners,
        original_intake_bytes_sha256=intake_source_sha256,
    )
    out={
        "schema_version":"empire.predictive_revenue.commercial_requirement_operator.v1",
        "mode":"OBSERVE","status":(
            "ILLUSTRATIVE_REQUIREMENT_READINESS_REVIEWED"
            if args.example_tampa_roofing else
            "MULTI_INDUSTRY_COMMERCIAL_REQUIREMENT_READINESS_REVIEWED"),
        "example_tampa_roofing_used":bool(args.example_tampa_roofing),
        "commercial_requirement":req,
        "original_lead_supply_and_buyer_owner_readiness":supply,
        "governed_fulfilment_and_sourcing_plan":plan,
        "original_a2a_owner_research_overlap":owner_a2a,
        "existing_finance_proof_gate_status":{
            "status":finance["status"],
            "fresh_internal_source_count":finance["current_internal_source_snapshot_count"],
            "independent_finance_proof_gaps_remaining":finance["required_proofs_not_admitted_count"],
            "actual_customer_profit_authenticated":finance["actual_recognised_revenue_independently_verified"],
        },
        "department_owner_acceptance_and_next_actions":owners,
        "authenticated_original_commercial_evidence_chain":chain,
        "recorded_live_customer_contract":False,
        "dispatch_performed":False,
        "supplier_contacted":False,
        "customer_committed":False,
        "production_services_modified":False,
        "database_writes":False,"outbound_sent":False,
        "execution_authority":"none",
    }
    print(json.dumps(out,sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
