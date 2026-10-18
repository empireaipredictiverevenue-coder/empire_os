"""Private Founder readout: six Gmail receipts in custody vs actually in EmpireDB.

This is NEVER an admission or an outbound intent. Reads the existing
private 0600 manifest, validates a fresh provider snapshot, then uses the
EXISTING least-privilege closer observer in a read-only transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from empire_os.empiredb_founder_reply_mailbox import EmpireDBFounderReplyMailbox
from empire_os.workspace_solar_historical_manifest import HistoricalManifestHeld
from scripts.import_workspace_historical_sent_receipts_20261018 import (
    HistoricalImportHeld, SELECT_SQL, EXPECTED_LINKAGE, _expected,
    load_private_custody,
)

READ_ROLE = "empire_closer_observer"
SCHEMA = "empire.workspace_historical_receipt_admission_status.v1"
TABLE = "public.workspace_historical_sent_receipts"
CATALOG_QUERY = "SELECT pg_catalog.to_regclass(%s) IS NOT NULL"


class HistoricalReadStatusUnavailable(ValueError):
    """Missing or inconsistent source evidence, not proof of zero."""


def _iso(value: Any) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise HistoricalReadStatusUnavailable("UNTRUSTED_DB_TIMESTAMP")
    return value.astimezone(timezone.utc).isoformat()


def _status_from_rows(manifest: dict, *, table_exists: bool, rows: Any) -> dict:
    if (manifest.get("evidence_count") != 6
            or len(manifest.get("items", [])) != 6
            or not isinstance(table_exists,bool)):
        raise HistoricalReadStatusUnavailable("UNVERIFIED_CUSTODY")
    if not table_exists and rows is not None:
        raise HistoricalReadStatusUnavailable("DB_SCHEMA_EVIDENCE_CONFLICT")
    if table_exists and (not isinstance(rows,list) or len(rows)>6):
        raise HistoricalReadStatusUnavailable("INVALID_HISTORICAL_DB_ROWS")
    expected={}
    for item in manifest["items"]:
        key=item["original_provider_message_id"]
        if key in expected:
            raise HistoricalReadStatusUnavailable("DUPLICATED_PRIVATE_ORIGINAL")
        expected[key]=_expected(item,manifest["source_scanned_at"])
    seen=set()
    if rows is not None:
        for row in rows:
            if not isinstance(row,(tuple,list)) or len(row)!=11:
                raise HistoricalReadStatusUnavailable("INVALID_DB_ROW_SHAPE")
            key=row[0]
            if key not in expected or key in seen:
                raise HistoricalReadStatusUnavailable("UNEXPECTED_DB_PROVIDER_KEY")
            seen.add(key)
            actual=list(row)
            actual[3]=_iso(actual[3])
            actual[4]=_iso(actual[4])
            if tuple(actual) != expected[key]:
                raise HistoricalReadStatusUnavailable("HISTORICAL_RECEIPT_EVIDENCE_CONFLICT")
    count=len(seen)
    status=(
        "PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD"
        if not table_exists else
        "SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB"
        if count == 6 else
        "HISTORICAL_DATABASE_IMPORT_PARTIAL_NEEDS_REVIEW"
        if count > 0 else
        "SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS"
    )
    items=[]
    for item in sorted(manifest["items"],key=lambda x:x["company"]):
        admitted=item["original_provider_message_id"] in seen
        items.append({
            "company":item["company"],
            "original_sent_receipt_custody_verified":True,
            "empiredb_historical_evidence_admitted":admitted,
            "status": (
                "UNBOUND_HISTORICAL_EVIDENCE_IN_EMPIREDB"
                if admitted else "PROVIDER_PROOF_ONLY_NOT_IN_EMPIREDB"
            ),
            "canonical_sent_intent_created":False,
            "historical_approval_verified":False,
            "crm_contact_bound":False,
            "commercial_revenue_verified":False,
        })
    return {
        "schema_version": SCHEMA,
        "status":status,
        "mode":"OBSERVE",
        "source":"private_workspace_verified_six_original_sends",
        "exact_historical_receipts":6,
        "private_custody_receipts_verified":6,
        "database_historical_receipt_table_active":table_exists,
        "database_historical_receipts_verified":count,
        "items":items,
        "source_visibility_complete":False,
        "canonical_outbound_intents_created":0,
        "historical_approvals_backfilled":0,
        "crm_records_created":0,
        "crm_handoff_authorized":False,
        "outbound_sent":False,
        "payment_executed":False,
        "database_writes":False,
        "execution_authority":"none",
    }


def review_six_historical_receipt_admission(
    *, connect_factory: Callable[...,Any] | None=None,
    dsn: str | None=None,
) -> dict:
    try:
        manifest=load_private_custody()
    except (HistoricalImportHeld,HistoricalManifestHeld,OSError,ValueError):
        raise HistoricalReadStatusUnavailable("PRIVATE_ORIGINAL_CUSTODY_NOT_VERIFIED") from None
    credential=dsn if dsn is not None else EmpireDBFounderReplyMailbox().dsn
    if not isinstance(credential,str) or not credential.strip():
        raise HistoricalReadStatusUnavailable("EXISTING_READONLY_CREDENTIAL_UNAVAILABLE")
    if connect_factory is None:
        import psycopg
        connect_factory=psycopg.connect
    try:
        with connect_factory(credential,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE " + READ_ROLE)
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute(CATALOG_QUERY,(TABLE,))
                result=cur.fetchone()
                if (not isinstance(result,(tuple,list)) or len(result)!=1
                        or type(result[0]) is not bool):
                    raise HistoricalReadStatusUnavailable("UNTRUSTED_SCHEMA_VISIBILITY")
                exists=result[0]
                rows=None
                if exists:
                    original_ids=[r["original_provider_message_id"] for r in manifest["items"]]
                    cur.execute(SELECT_SQL,(original_ids,))
                    rows=cur.fetchall()
                cur.execute("ROLLBACK")
    except HistoricalReadStatusUnavailable:
        raise
    except Exception:
        raise HistoricalReadStatusUnavailable("RESTRICTED_RECEIPT_READER_FAILED") from None
    return _status_from_rows(manifest,table_exists=exists,rows=rows)
