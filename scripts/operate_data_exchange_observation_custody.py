"""One-shot official-source custody for the existing Data Exchange V14 board.

Default preview fetches at most three chosen Planning Data brownfield IDs
through the EXISTING official bounded GET adapter and prints only aggregate
status. Canonical INSERT needs a separate dedicated DSN, an explicit release
flag and --append. No new scanner, service, timer or other database.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os

from empire_os.data_exchange_construction import (
    build_construction_preview, normalise_official_brownfield_entities,
)
from empire_os.data_exchange_observation_custody import plan_custody_append
from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from scripts.probe_construction_official_entities import fetch_official_json

SCHEMA = "empire.data_exchange.custody_capture_operator.v15"
PILOT_ENTITY_IDS = (1722645, 1739516, 1739547)
RELEASE = "FOUNDER_APPROVED_OBSERVATION_APPEND_ONLY"
DSN_ENV = "EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN"


def capture(
    *,
    entity_ids: tuple[int, ...] = PILOT_ENTITY_IDS,
    now: datetime,
    fetch_json=fetch_official_json,
) -> dict:
    if (
        not isinstance(entity_ids, tuple)
        or len(entity_ids) != 3
        or any(type(item) is not int for item in entity_ids)
        or entity_ids != PILOT_ENTITY_IDS
    ):
        raise ValueError("LOCKED_OFFICIAL_SOURCE_PILOT_IDS_REQUIRED")
    # Existing source normalizer and fixed official host, no arbitrary crawl.
    normalized = normalise_official_brownfield_entities(
        list(entity_ids), fetch_json=fetch_json, observed_at=now
    )
    snapshot = build_construction_preview(normalized, observed_at=now)
    plan = plan_custody_append(snapshot, previous=None, assessed_at=now)
    if plan["mode"] != "APPEND_REQUIRED":
        raise ValueError("SOURCE_CAPTURE_NOT_CUSTODY_ELIGIBLE")
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--board", action="store_true")
    parser.add_argument("--approved-custody-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.board and args.append:
            raise ValueError("READ_AND_WRITE_ARE_SEPARATE")
        dsn = os.environ.get(DSN_ENV,"").strip()
        if args.board:
            if not dsn:
                raise ValueError("DEDICATED_CUSTODY_READER_DSN_REQUIRED")
            report = EmpireDBConstructionCustody(dsn).read_signal_board(
                now=datetime.now(timezone.utc)
            )
            # Bounded first-party source board only, no customer API.
            print(json.dumps(report, sort_keys=True, allow_nan=False))
            return 0 if report["feed_status"].startswith(
                ("OBSERVED_CHANGES", "NO_OBSERVED_FIELD_CHANGES")
            ) else 2
        if args.append and (
            not args.approved_custody_only
            or os.environ.get("EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE") != RELEASE
            or not dsn
        ):
            raise ValueError("DEDICATED_CUSTODY_WRITE_APPROVAL_OR_DSN_MISSING")
        if not args.append and args.approved_custody_only:
            raise ValueError("APPROVAL_FLAG_ONLY_VALID_FOR_APPEND")
        snap = capture(now=datetime.now(timezone.utc))
        if args.append:
            result = EmpireDBConstructionCustody(dsn).append_once(
                snap, now=datetime.now(timezone.utc)
            )
            output = {
                "schema_version":SCHEMA,"capture_mode":result["mode"],
                "source":"gb_planning_data","record_count":snap["dataset_record_count"],
                "sequence":result["sequence"],
                "head_chain_sha256":result["head_chain_sha256"],
                "database_writes":result["database_writes"],
                "customer_delivery_enabled":False,
                "external_anchor_verified":False,
                "execution_authority":"NONE",
            }
        else:
            output = {
                "schema_version":SCHEMA,"capture_mode":"PREVIEW_ONLY_NOT_STORED",
                "source":"gb_planning_data","record_count":snap["dataset_record_count"],
                "source_claim_verification":"NOT_INDEPENDENTLY_VERIFIED",
                "source_rights_status":"FIELD_RIGHTS_NOT_CLEARED",
                "canonical_observation_written":False,
                "database_writes":False,
                "customer_delivery_enabled":False,
                "execution_authority":"NONE",
            }
        print(json.dumps(output,sort_keys=True))
        return 0
    except Exception as exc:
        # Never leak HTTP payloads, tokens, DB error strings or source contacts.
        print(json.dumps({
            "schema_version":SCHEMA,"capture_mode":"HOLD",
            "reason_code":"CUSTODY_SOURCE_OR_AUTHORITY_NOT_VERIFIED",
            "error_type":type(exc).__name__,
            "database_writes":None if args.append else False,
            "customer_delivery_enabled":False,
            "execution_authority":"NONE",
        },sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
