"""Global multi-industry commercial requirement planning (OBSERVE-only).

No implicit customer or geographic default. Use --requirement-intake for an
original typed request; --example-tampa-roofing is explicitly demonstrative.
Read-only owner snapshots, no dispatch, quotes or commercial promises.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from empire_os.predictive_commercial_requirements import (
    tampa_roofing_founder_example,review_commercial_requirement,
)
from empire_os.predictive_commercial_supply_readiness import (
    review_lead_readiness_runtime,
)
from empire_os.predictive_commercial_fulfilment import plan_commercial_fulfilment

MAX_SIZE=200_000

def _read(pathname:str)->dict:
    p=Path(pathname)
    if (p.is_symlink() or not p.is_file()
            or not 0<p.stat().st_size<=MAX_SIZE):
        raise ValueError("approved source input unavailable or oversized")
    x=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(x,dict):
        raise ValueError("expected bounded original owner JSON packet")
    return x


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--repo-root",default="/srv/empire_os")
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
    raw=_read(args.requirement_intake) if args.requirement_intake else tampa_roofing_founder_example()
    req=review_commercial_requirement(
        raw,as_of=now,
        source_instruction_kind=(
            "FOUNDER_EXAMPLE_TARGET_NOT_CUSTOMER_ORDER" if args.example_tampa_roofing
            else "FOUNDER_OR_CUSTOMER_UNVERIFIED_REQUIREMENT_DRAFT"),
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
