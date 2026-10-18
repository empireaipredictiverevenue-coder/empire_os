#!/usr/bin/env python3
"""Read live EmpireOS financial source *observations*, not audited claims.

No DB, CRM or customer source rows are opened. This reads three permitted,
bounded local status snapshots, each with a SHA256 local integrity fingerprint.
No write mode, credentials, scheduling, customer activation or money movement.
"""
from __future__ import annotations

from pathlib import Path
import argparse,json

from empire_os.enterprise_finance_evidence_readiness import (
    review_finance_source_readiness,
)

ROOT=Path("/srv/empire_os")


def main(argv=None,*,repo_root=ROOT)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({
            "status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED",
            "report_distribution_authorized":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 2
    try:
        payload=review_finance_source_readiness(Path(repo_root))
    except (OSError,ValueError,TypeError):
        print(json.dumps({
            "status":"HOLD_FINANCE_SOURCE_REVIEW_FAILED",
            "report_distribution_authorized":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 2
    print(json.dumps(payload,sort_keys=True,allow_nan=False))
    return 0 if payload["status"]=="SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED" else 2


if __name__=="__main__":
    raise SystemExit(main())
