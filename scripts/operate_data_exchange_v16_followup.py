"""V16 manual time-separated second observation, using existing V15 custody.

Default is DB read-only due check; APPEND requires the existing founder
OBSERVE-only authority and its protected first-party DSN, never a timer.
Calls the existing 3-ID bounded official fetcher and custody transaction.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os

from empire_os.data_exchange_observation_custody import (
    CustodyIntegrityError, parse_at, verify_custody_window,
)
from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from empire_os.data_exchange_temporal_quality import (
    PILOT_IDS, build_temporal_quality,
)
from scripts.operate_data_exchange_observation_custody import (
    capture, DSN_ENV, RELEASE,
)

SCHEMA="empire.data_exchange.followup_operator.v16"
MIN_ELAPSED=timedelta(hours=24)
MAX_ELAPSED=timedelta(days=90)


def due_check(rows: list[dict], *, now: datetime) -> dict:
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise CustodyIntegrityError("timezone-aware clock required")
    now=now.astimezone(timezone.utc)
    proof=verify_custody_window(rows)
    latest=rows[-1]
    at=parse_at(latest["source_observed_at"])
    elapsed=now-at
    ids={r["record_id"] for r in latest["snapshot_json"]["records"]}
    if ids!=PILOT_IDS:
        raise CustodyIntegrityError("three-entity custody scope incomplete")
    if elapsed<timedelta(0):
        raise CustodyIntegrityError("custody head is in the future")
    due=(elapsed>=MIN_ELAPSED and elapsed<=MAX_ELAPSED)
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":("ELIGIBLE_FOR_EXPLICIT_ONE_SHOT_CAPTURE"
                  if due else
                  "HOLD_MAX_90_DAY_GAP" if elapsed>MAX_ELAPSED
                  else "HOLD_MINIMUM_24H_SEPARATION"),
        "eligible":due,
        "next_capture_not_before":(at+MIN_ELAPSED).isoformat(),
        "canonical_previous_sequence":proof["last_sequence"],
        "canonical_previous_head_sha256":proof["head_chain_sha256"],
        "canonical_observation_count_in_window":len(rows),
        "seconds_until_eligible":max(0,int((MIN_ELAPSED-elapsed).total_seconds())),
        "database_writes":False,
        "customer_delivery_enabled":False,
        "data_resale_authorized":False,
        "outbound_enabled":False,
        "payment_execution":False,
        "execution_authority":"NONE",
    }


def run_once(*, reader: EmpireDBConstructionCustody, now: datetime, append: bool,
             fetch_snapshot=capture) -> dict:
    before=reader.read_window()
    readiness=due_check(before,now=now)
    if not append or not readiness["eligible"]:
        return readiness
    snap=fetch_snapshot(now=now)  # existing allowlisted 3 official IDs
    if {r["record_id"] for r in snap["records"]}!=PILOT_IDS:
        raise CustodyIntegrityError("official second snapshot incomplete")
    result=reader.append_once(snap,now=datetime.now(timezone.utc))
    if (result["mode"]!="CANONICAL_APPEND_COMMITTED"
        or result["database_writes"] is not True):
        raise CustodyIntegrityError("append result not newly committed")
    # No automatic retries after this point. Re-read canonical head only.
    after=reader.read_window()
    if (after[-1]["sequence"]!=readiness["canonical_previous_sequence"]+1
        or after[-1]["chain_sha256"]!=result["head_chain_sha256"]):
        raise CustodyIntegrityError("append committed but readback not verified")
    quality=build_temporal_quality(after,assessed_at=datetime.now(timezone.utc))
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"SECOND_CANONICAL_OBSERVATION_COMMITTED",
        "canonical_head_sequence":after[-1]["sequence"],
        "canonical_head_sha256":result["head_chain_sha256"],
        "source_record_count":len(snap["records"]),
        "observation_count_in_window":len(after),
        "board_status":quality["v14_board_status"],
        "observed_source_field_changes":quality["observed_source_field_changes"],
        "comparison_held_count":quality["held_comparison_count"],
        "market_coverage_verified":False,
        "customer_delivery_enabled":False,
        "source_field_rights_cleared":False,
        "data_resale_authorized":False,
        "outbound_enabled":False,
        "payment_execution":False,
        "database_writes":True,
        "external_anchor_verified":False,
        "execution_authority":"NONE",
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--append",action="store_true")
    p.add_argument("--approved-custody-only",action="store_true")
    args=p.parse_args(argv)
    attempted_write=False
    try:
        dsn=os.environ.get(DSN_ENV,"")
        if not dsn:
            raise ValueError("EXISTING_DEDICATED_CUSTODY_DSN_REQUIRED")
        if args.append:
            if (not args.approved_custody_only or
                os.environ.get("EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE")!=RELEASE):
                raise ValueError("APPROVED_OBSERVE_AUTHORITY_REQUIRED")
        elif args.approved_custody_only:
            raise ValueError("APPROVAL_FLAG_ONLY_FOR_APPEND")
        store=EmpireDBConstructionCustody(dsn)
        # If the write is requested, an unexpected exception/timeout after
        # the attempt has UNCERTAIN transaction state. Never auto-retry.
        if args.append:
            # The due check runs inside run_once before the network fetch.
            attempted_write=True
        report=run_once(reader=store,now=datetime.now(timezone.utc),
                        append=args.append)
        print(json.dumps(report,sort_keys=True,allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "schema_version":SCHEMA,"mode":"OBSERVE","status":"HOLD",
            "error_type":type(exc).__name__,
            "database_writes":None if attempted_write else False,
            "customer_delivery_enabled":False,
            "outbound_enabled":False,"payment_execution":False,
            "execution_authority":"NONE",
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
