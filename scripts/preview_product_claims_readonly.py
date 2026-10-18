#!/usr/bin/env python3
"""Explicit private proof-of-claim preview for an existing Empire data product.

No customer/export/send/CRM action. Restricts input to official source claim
kind and exact BIN/BBL pair; the AI/user does not supply arbitrary prose.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from empire_os.data_product_claim_gate import review_data_product_claims

ROOT=Path("/srv/empire_os")


def main(argv=None,*,repo_root:Path=ROOT)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only",action="store_true")
    p.add_argument("--product",required=True)
    p.add_argument("--statement",required=True)
    p.add_argument("--bin",required=True)
    p.add_argument("--bbl",required=True)
    args=p.parse_args(argv)
    if not args.read_only:
        output={"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED",
                "customer_distribution_authorized":False,
                "execution_authority":"none"}
        print(json.dumps(output,sort_keys=True));return 2
    report=review_data_product_claims(
        product_key=args.product,
        requested_claims=[{
            "statement_id":args.statement,
            "bin":args.bin,
            "dob_bbl":args.bbl,
        }],
        repo_root=repo_root,
    )
    print(json.dumps(report,sort_keys=True,allow_nan=False))
    return 0 if report["status"]=="PRIVATE_SOURCE_BOUND_CLAIM_PREVIEW_ONLY" else 2


if __name__=="__main__":
    raise SystemExit(main())
