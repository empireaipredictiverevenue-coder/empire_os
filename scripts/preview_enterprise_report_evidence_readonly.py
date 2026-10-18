#!/usr/bin/env python3
"""On-demand, source-truth-checked internal enterprise diagnostic preview.

Uses the existing EmpireOS report assembler / renderer without modifying them,
new route, CRM import, entitlement or customer distribution. Defaults to a
minimal verifier result; --format provides a guarded renderer on stdout.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from empire_os.enterprise_report_claim_guard import (
    guarded_enterprise_report_render,validate_enterprise_report_before_render,
)

ROOT=Path("/srv/empire_os")


def main(argv=None,*,repo_root:Path=ROOT)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    parser.add_argument("--finance-readiness",action="store_true",
                        help="Include only internally observed financial evidence gaps; never claim audited finance")
    parser.add_argument("--format",choices=("verify","markdown","html"),
                        default="verify")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({
            "status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED",
            "customer_delivery_authorized":False,
            "execution_authority":"none",
        }))
        return 2
    if args.finance_readiness and args.format!="verify":
        print(json.dumps({
            "status":"HOLD_FINANCE_READINESS_REQUIRES_VERIFY_FORMAT",
            "customer_delivery_authorized":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 2
    try:
        from empire_os.predictive_revenue_enterprise_report import (
            build_enterprise_diagnostic_report,
        )
        report=build_enterprise_diagnostic_report(Path(repo_root))
        outcome=validate_enterprise_report_before_render(report)
        if args.format=="verify":
            if args.finance_readiness:
                from empire_os.enterprise_finance_evidence_readiness import (
                    review_finance_source_readiness,
                )
                finance=review_finance_source_readiness(Path(repo_root))
                outcome={
                    "report_guard":outcome,
                    "finance_source_readiness":finance,
                    "customer_delivery_authorized":False,
                    "execution_authority":"none",
                }
                if finance["status"]!="SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED":
                    print(json.dumps(outcome,sort_keys=True,allow_nan=False))
                    return 2
            print(json.dumps(outcome,sort_keys=True,allow_nan=False))
        else:
            # Exactly the same guard is run on the deep-copied instance
            # before entering either existing renderer.
            content=guarded_enterprise_report_render(report,format=args.format)
            print(content)
        return 0
    except (ValueError,TypeError,KeyError,OSError,ImportError) as err:
        # Avoid disclosing source extracts / customer-supplied content.
        print(json.dumps({
            "status":"HOLD_ENTERPRISE_REPORT_EVIDENCE_CHECK",
            "reason_code":type(err).__name__,
            "customer_delivery_authorized":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
