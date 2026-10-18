#!/usr/bin/env python3
"""Read-only, fail-closed production readback for founder-approved six receipts.

No DB credentials and no direct database writes. Requires the existing
private Founder API (127.0.0.1:8766) to independently check all six
original provider receipts against restricted EmpireDB historical proof.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable
from urllib.request import Request, urlopen

from empire_os.workspace_solar_reply_tracking import ANCHORS

BASE="http://127.0.0.1:8766"
HIST="/v1/founder-mailbox/workspace-solar-historical-evidence-status"
GMAIL="/v1/founder-mailbox/workspace-solar-reply-review"
PROOF_COMPANIES={x[0] for x in ANCHORS}


class ReadbackHeld(ValueError):
    """Fail closed: no false verification of canonical commercial authority."""


def _read(path: str, *, opener: Callable[..., Any] = urlopen) -> dict:
    if path not in (HIST,GMAIL):
        raise ReadbackHeld("SOURCE_NOT_ALLOWLISTED")
    req=Request(BASE+path,headers={"Accept":"application/json"},method="GET")
    try:
        with opener(req, timeout=9) as response:
            if response.status != 200:
                raise ReadbackHeld("PRIVATE_READ_API_NOT_200")
            raw=response.read(18001)
    except ReadbackHeld:
        raise
    except Exception:
        raise ReadbackHeld("PRIVATE_READ_API_UNAVAILABLE") from None
    if len(raw)>18000:
        raise ReadbackHeld("REVIEW_RESPONSE_TOO_LARGE")
    try:
        data=json.loads(raw)
    except (UnicodeDecodeError,ValueError):
        raise ReadbackHeld("UNTRUSTED_JSON_REVIEW") from None
    if not isinstance(data,dict):
        raise ReadbackHeld("UNTRUSTED_REVIEW_SHAPE")
    return data


def verify(
    historical: dict,
    gmail: dict,
) -> dict:
    if (
        historical.get("schema_version")
          != "empire.workspace_historical_receipt_admission_status.v1"
        or historical.get("status") != "SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB"
        or historical.get("database_historical_receipt_table_active") is not True
        or historical.get("private_custody_receipts_verified") != 6
        or historical.get("database_historical_receipts_verified") != 6
        or historical.get("exact_historical_receipts") != 6
        or historical.get("mode") != "OBSERVE"
        or historical.get("canonical_outbound_intents_created") != 0
        or historical.get("historical_approvals_backfilled") != 0
        or historical.get("crm_records_created") != 0
        or historical.get("crm_handoff_authorized") is not False
        or historical.get("outbound_sent") is not False
        or historical.get("database_writes") is not False
        or historical.get("payment_executed") is not False
    ):
        raise ReadbackHeld("SIX_DATABASE_EVIDENCE_RECEIPTS_NOT_VERIFIED")
    items=historical.get("items")
    if not isinstance(items,list) or len(items)!=6:
        raise ReadbackHeld("INCOMPLETE_HISTORICAL_EVIDENCE")
    companies=set()
    for item in items:
        if not isinstance(item,dict):
            raise ReadbackHeld("INVALID_HISTORICAL_ITEM")
        company=item.get("company")
        if (company not in PROOF_COMPANIES or company in companies
                or item.get("original_sent_receipt_custody_verified") is not True
                or item.get("empiredb_historical_evidence_admitted") is not True
                or item.get("status") != "UNBOUND_HISTORICAL_EVIDENCE_IN_EMPIREDB"
                or item.get("historical_approval_verified") is not False
                or item.get("canonical_sent_intent_created") is not False
                or item.get("crm_contact_bound") is not False
                or item.get("commercial_revenue_verified") is not False):
            raise ReadbackHeld("UNVERIFIED_INDIVIDUAL_RECEIPT")
        companies.add(company)
    if companies != PROOF_COMPANIES:
        raise ReadbackHeld("SIX_COMPANY_PROVENANCE_INCOMPLETE")
    if (gmail.get("status") != "FRESH_WORKSPACE_REVIEW_QUEUE"
            or gmail.get("sent_anchors_verified") != 6
            or gmail.get("monitored_threads") != 6
            or gmail.get("crm_conversation_created") is not False
            or gmail.get("outbound_sent") is not False):
        raise ReadbackHeld("INDEPENDENT_GMAIL_ORIGINALS_NOT_VERIFIED")
    return {
        "status":"SIX_HISTORICAL_GMAIL_RECEIPTS_IN_EMPIREDB_VERIFIED",
        "evidence_receipts_verified":6,
        "founder_review":"UNBOUND_HISTORICAL_EVIDENCE_ONLY",
        "gmail_original_sends_verified":6,
        "new_reply_candidates":gmail.get("inbound_header_candidate_count"),
        "canonical_outbound_intents_created":0,
        "historical_approvals_backfilled":0,
        "crm_records_created":0,
        "emails_sent":False,
        "payment_executed":False,
        "database_writes":False,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-read-only",action="store_true",required=True)
    args=parser.parse_args()
    try:
        result=verify(_read(HIST),_read(GMAIL))
    except ReadbackHeld as exc:
        print(json.dumps({
            "status":"HISTORICAL_SIX_IMPORT_VERIFICATION_HELD",
            "reason_code":str(exc),
            "database_writes":False,
            "emails_sent":False,
        },sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
