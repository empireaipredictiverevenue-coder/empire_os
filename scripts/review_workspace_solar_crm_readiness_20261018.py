#!/usr/bin/env python3
"""Read-only six-company revenue CRM handoff gap register; no new service.

Composes three already-private Founder evidence routes. Discloses only
company names, evidence statuses and next review actions. Neither
touches the database nor creates a CRM identity.
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.request import Request, urlopen

from empire_os.workspace_solar_crm_readiness import (
    CRMReadinessHeld,combine_six_company_crm_readiness,
)

HOST="http://127.0.0.1:8766"
PATHS={
    "history":"/v1/founder-mailbox/workspace-solar-historical-evidence-status",
    "canonical":"/v1/founder-mailbox/workspace-solar-canonical-intent-review",
    "gmail":"/v1/founder-mailbox/workspace-solar-reply-review",
}


def get_private(name: str) -> dict:
    if name not in PATHS:
        raise CRMReadinessHeld("READ_PATH_NOT_ALLOWLISTED")
    request=Request(HOST+PATHS[name],headers={"Accept":"application/json"},method="GET")
    try:
        with urlopen(request,timeout=8) as response:
            if response.status!=200:
                raise CRMReadinessHeld("READ_SOURCE_UNAVAILABLE")
            raw=response.read(50001)
        if len(raw)>50000:
            raise CRMReadinessHeld("UNBOUNDED_SOURCE")
        result=json.loads(raw)
    except CRMReadinessHeld:
        raise
    except Exception:
        raise CRMReadinessHeld("PRIVATE_READER_UNAVAILABLE") from None
    if not isinstance(result,dict):
        raise CRMReadinessHeld("PRIVATE_READER_INVALID")
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args()
    try:
        output=combine_six_company_crm_readiness(
            get_private("history"),get_private("canonical"),get_private("gmail")
        )
    except CRMReadinessHeld as exc:
        print(json.dumps({
            "status":"CRM_READINESS_SOURCE_HELD",
            "reason_code":str(exc),
            "crm_records_created":0,
            "emails_sent":False,
            "database_writes":False,
        },sort_keys=True))
        return 2
    print(json.dumps(output,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
