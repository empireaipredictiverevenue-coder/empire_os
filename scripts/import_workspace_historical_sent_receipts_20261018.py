#!/usr/bin/env python3
"""Separate DBA-gated import of six immutable Gmail sent evidence receipts.

Requires separately approved migration 052 in EmpireDB and explicit DBA
invocation. NEVER called by timers, frontend, CRM or email operations.
It only INSERTS into public.workspace_historical_sent_receipts and does not
create canonical outbound_intents, approvals, buyer rows, or replies.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd
import stat
from typing import Any, Callable

from empire_os.workspace_solar_historical_manifest import (
    HistoricalManifestHeld, SCHEMA, read_source_build_manifest,
)
from scripts.prepare_workspace_solar_historical_evidence_20261018 import OUTPUT

SELECT_SQL = """
SELECT original_provider_message_id,gmail_thread_id,
       original_recipient_sha256,original_sent_at,source_scanned_at,
       evidence_sha256,source_kind,linkage_state,
       historical_approval_attested,crm_contact_bound,
       customer_revenue_verified
FROM public.workspace_historical_sent_receipts
WHERE original_provider_message_id = ANY(%s)
ORDER BY original_provider_message_id
"""
INSERT_SQL = """
INSERT INTO public.workspace_historical_sent_receipts
(original_provider_message_id,gmail_thread_id,original_recipient_sha256,
 original_sent_at,source_scanned_at,evidence_sha256,source_kind)
VALUES (%s,%s,%s,%s,%s,%s,%s)
"""
EXPECTED_LINKAGE = "UNBOUND_EXTERNAL_SENT_OBSERVED"


class HistoricalImportHeld(ValueError):
    pass


def _items_from_manifest(
    manifest: dict, *, verified_source: dict | None = None,
) -> list[dict]:
    if (not isinstance(manifest, dict)
            or manifest.get("schema_version") != SCHEMA
            or manifest.get("evidence_count") != 6
            or manifest.get("database_writes") is not False
            or manifest.get("outbound_sent") is not False
            or manifest.get("production_schema_activation_authorized") is not False
            or not isinstance(manifest.get("items"),list)
            or len(manifest["items"])!=6):
        raise HistoricalImportHeld("CUSTODY_CONTRACT_INVALID")
    # The root operator must obtain verified_source BEFORE irrevocably
    # dropping to OS postgres: the source is 0600 owned by ubuntu.
    current=(read_source_build_manifest() if verified_source is None
             else verified_source)
    if not isinstance(current,dict) or not isinstance(current.get("items"),list):
        raise HistoricalImportHeld("SOURCE_PROOF_CONTRACT_INVALID")
    original = current["items"]
    preserved = manifest["items"]
    if sorted(original, key=lambda x:x["gmail_thread_id"]) != sorted(
        preserved, key=lambda x:x["gmail_thread_id"]
    ):
        # Compare ALL provider metadata and authority flags, not just IDs or
        # a supplied digest whose underlying fields could be tampered with.
        raise HistoricalImportHeld("LIVE_WORKSPACE_SOURCE_DRIFT")
    if current.get("evidence_count") != 6:
        raise HistoricalImportHeld("INCOMPLETE_CURRENT_EVIDENCE")
    return sorted(manifest["items"],key=lambda r:r["original_provider_message_id"])


def load_private_custody() -> dict:
    if OUTPUT.is_symlink() or not OUTPUT.is_file():
        raise HistoricalImportHeld("PRIVATE_CUSTODY_UNAVAILABLE")
    s=OUTPUT.stat()
    if not 0 < s.st_size <= 25000 or stat.S_IMODE(s.st_mode) != 0o600:
        raise HistoricalImportHeld("UNSAFE_PRIVATE_CUSTODY_PERMISSIONS")
    try:
        manifest=json.loads(OUTPUT.read_text("utf-8"))
    except (OSError,UnicodeError,ValueError):
        raise HistoricalImportHeld("PRIVATE_CUSTODY_CORRUPT") from None
    _items_from_manifest(manifest)
    return manifest


def _expected(item: dict, source_scan: str) -> tuple:
    return (
        item["original_provider_message_id"], item["gmail_thread_id"],
        item["recipient_sha256"],item["sent_at"],source_scan,
        item["evidence_sha256"],item["source_kind"],
        EXPECTED_LINKAGE, False,False,False,
    )


def import_exact_six_receipts(
    manifest: dict, *, connect_factory: Callable[...,Any],
    dsn: str="dbname=empiredb user=postgres",
    verified_source: dict | None = None,
) -> dict:
    items=_items_from_manifest(manifest,verified_source=verified_source)
    expected={x["original_provider_message_id"]:_expected(
        x,manifest["source_scanned_at"]) for x in items}
    if len(expected)!=6:
        raise HistoricalImportHeld("DUPLICATE_PROVIDER_RECEIPTS")
    try:
        with connect_factory(dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE")
                cur.execute("SET LOCAL statement_timeout='7000ms'")
                cur.execute(
                    "SELECT current_database(),current_user,"
                    "(SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user)"
                )
                db,user,is_super=cur.fetchone()
                if (db!="empiredb" or user!="postgres" or is_super is not True):
                    raise HistoricalImportHeld("EXACT_PRIVILEGED_EMPIREDB_SESSION_REQUIRED")
                cur.execute(
                    "SELECT c.relrowsecurity,c.relforcerowsecurity FROM pg_catalog.pg_class c"
                    " WHERE c.oid=pg_catalog.to_regclass('public.workspace_historical_sent_receipts')"
                )
                security=cur.fetchone()
                if security!=(True,True):
                    raise HistoricalImportHeld("HISTORICAL_RECEIPT_SCHEMA_NOT_ACTIVATED")
                cur.execute(
                    "SELECT count(*) FROM pg_catalog.pg_trigger t"
                    " WHERE t.tgrelid=pg_catalog.to_regclass("
                    "'public.workspace_historical_sent_receipts')"
                    " AND t.tgname='workspace_historical_receipts_append_only' AND NOT t.tgisinternal"
                )
                trigger=cur.fetchone()
                if trigger!=(1,):
                    raise HistoricalImportHeld("APPEND_ONLY_GUARD_NOT_VERIFIED")
                cur.execute(SELECT_SQL,(list(expected),))
                existing=cur.fetchall()
                seen={}
                for row in existing:
                    if not isinstance(row,(tuple,list)) or len(row)!=11:
                        raise HistoricalImportHeld("INVALID_EXISTING_RECEIPT")
                    key=str(row[0])
                    if key not in expected or key in seen:
                        raise HistoricalImportHeld("UNEXPECTED_EXISTING_RECEIPT")
                    actual=list(row)
                    # DB timestamptz must compare as timezone-aware instants.
                    from datetime import datetime,timezone
                    actual[3]=actual[3].astimezone(timezone.utc).isoformat()
                    actual[4]=actual[4].astimezone(timezone.utc).isoformat()
                    if tuple(actual)!=expected[key]:
                        raise HistoricalImportHeld("EXISTING_HISTORICAL_EVIDENCE_CONFLICT")
                    seen[key]=True
                new_ids=[key for key in expected if key not in seen]
                for key in new_ids:
                    r=expected[key]
                    cur.execute(INSERT_SQL,r[:7])
                cur.execute(SELECT_SQL,(list(expected),))
                after=cur.fetchall()
                if not isinstance(after,list) or len(after)!=6:
                    raise HistoricalImportHeld("POST_IMPORT_COUNT_MISMATCH")
                for row in after:
                    key=str(row[0])
                    if key not in expected:
                        raise HistoricalImportHeld("POST_IMPORT_UNEXPECTED_ID")
                    actual=list(row)
                    from datetime import datetime,timezone
                    actual[3]=actual[3].astimezone(timezone.utc).isoformat()
                    actual[4]=actual[4].astimezone(timezone.utc).isoformat()
                    if tuple(actual)!=expected[key]:
                        raise HistoricalImportHeld("POST_IMPORT_EVIDENCE_MISMATCH")
                conn.commit()
    except HistoricalImportHeld:
        raise
    except Exception:
        raise HistoricalImportHeld("RESTRICTED_EVIDENCE_IMPORT_FAILED") from None
    return {
        "status":"SIX_EXTERNAL_SENT_OBSERVATIONS_STORED_UNBOUND",
        "verified_receipts":6,
        "new_receipts":len(new_ids),
        "replayed_identical_receipts":len(seen),
        "canonical_outbound_intents_created":0,
        "historical_approvals_backfilled":0,
        "crm_rows_created":0,
        "emails_sent":False,
        "payments_executed":False,
        "crm_handoff_authorized":False,
    }


def _connect_as_postgres_after_private_custody_validation(
    dsn: str, **kwargs: Any
) -> Any:
    """Root reads exact 0600 evidence first; DB connection uses postgres peer.

    This is a one-way privilege drop: never set effective UID back to root,
    never use a credential-bearing DSN, never keep root capabilities for SQL.
    """
    if os.geteuid() != 0:
        raise HistoricalImportHeld("ROOT_PRIVATE_CUSTODY_OPERATOR_REQUIRED")
    try:
        account=pwd.getpwnam("postgres")
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
        if os.geteuid() != account.pw_uid:
            raise HistoricalImportHeld("POSTGRES_PRIVILEGE_DROP_UNVERIFIED")
        import psycopg
        return psycopg.connect(dsn, **kwargs)
    except HistoricalImportHeld:
        raise
    except Exception:
        raise HistoricalImportHeld("POSTGRES_PEER_CONNECTION_UNAVAILABLE") from None


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    m=parser.add_mutually_exclusive_group()
    m.add_argument("--preflight",action="store_true")
    m.add_argument("--apply-founder-approved-historical-receipts-only",action="store_true")
    args=parser.parse_args()
    report={"database_mutation":False,"emails_sent":False,"crm_handoff_authorized":False}
    try:
        manifest=load_private_custody()
        if args.apply_founder_approved_historical_receipts_only:
            if os.geteuid() != 0:
                raise HistoricalImportHeld("ROOT_PRIVATE_CUSTODY_OPERATOR_REQUIRED")
            # Capture the authenticated provider-derived source while root
            # can read the mode-0600 snapshot. The peer connection then
            # permanently drops to postgres; no private-file reread follows.
            root_verified_source=read_source_build_manifest()
            _items_from_manifest(manifest,verified_source=root_verified_source)
            result=import_exact_six_receipts(
                manifest,
                verified_source=root_verified_source,
                connect_factory=_connect_as_postgres_after_private_custody_validation,
            )
            report.update(result,database_mutation=result["new_receipts"]>0)
        else:
            report.update(status="HISTORICAL_RECEIPT_CUSTODY_READY_DBA_APPROVAL_HELD",
                          verified_receipts=6,schema_activation_executed=False)
    except (HistoricalImportHeld, HistoricalManifestHeld):
        report.update(status="HELD_HISTORICAL_RECEIPT_IMPORT")
    print(json.dumps(report,sort_keys=True))
    return 0 if report.get("verified_receipts")==6 else 2


if __name__=="__main__":
    raise SystemExit(main())
