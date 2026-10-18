#!/usr/bin/env python3
"""One bounded, genuinely pre-existing EmpireDB event, never a generated order.

Read only: exactly one admin candidate UUID and exactly one existing restricted
revenue function read; no customer PII, mass exports, secret disclosure, DDL,
payment movement, access changes, settlement or outbound.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from datetime import datetime,timezone
from typing import Callable
from uuid import UUID

from empire_os.predictive_revenue_canonical_reader import (
    CanonicalRevenueEvidenceUnavailable,read_recognized_revenue_event,
)
from scripts.provision_revenue_event_evidence_login_20261018 import (
    LOGIN, TENANT, pg,
)
from scripts.review_rev052_committed_login_readonly_20261018 import (
    CATALOG_SQL, private_password,
)

SCHEMA = "empire.rev053.one_real_ledger_event_review.v1"
MISSING="NO_ELIGIBLE_EXISTING_EVENT"
# The operator does not accept event UUIDs from callers. Query the fixed
# approved tenant's actual primary records, bounded to one candidate only.
# The source query deliberately mirrors every positive REV051 predicate.
DISCOVER_SQL = f"""BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';
SET LOCAL lock_timeout='1500ms';
SELECT COALESCE((
 SELECT e.id::text
 FROM public.commercial_events AS e
 JOIN public.fulfilment_orders AS o ON o.id=e.fulfilment_order_id
 JOIN public.buyers AS event_buyer ON event_buyer.id=e.buyer_id
 JOIN public.buyers AS order_buyer ON order_buyer.id=o.buyer_id
 WHERE event_buyer.org_id='{TENANT}'::uuid
   AND order_buyer.org_id='{TENANT}'::uuid
   AND e.event_type='revenue_recognized'
   AND e.payload->>'actual_revenue'='true'
   AND e.buyer_id=o.buyer_id
   AND e.product_id=o.product_id
   AND e.product_id IS NOT NULL
   AND e.amount_cents>0
   AND e.amount_cents=o.price_cents
   AND o.price_cents>0
   AND o.state IN ('settled','outcome_captured')
   AND o.settled_at IS NOT NULL
   AND e.occurred_at<=clock_timestamp()
   AND e.payload->'causal_lineage' IS NOT NULL
   AND e.payload->'causal_lineage'<>'{{}}'::jsonb
   AND e.payload->'causal_lineage'
       IS NOT DISTINCT FROM o.commercial_payload->'causal_lineage'
 ORDER BY e.occurred_at DESC,e.id DESC
 LIMIT 1
),'{MISSING}');
ROLLBACK;"""

def _safe_status(status: str, stage: str) -> dict:
    return {
        "schema_version":SCHEMA,
        "status":status, "stage":stage,
        "mode":"OBSERVE","execution_authority":"none",
        "database_writes":False,"source_rows_exported":0,
        "customer_identity_exposed":False,"password_printed":False,
        "customer_financial_report_authorized":False,
        "real_payment_settlement_verified":False,
        "payment_receipt_verified":False,
        "realised_revenue_verified":False,
        "complete_daily_revenue_census_verified":False,
        "outbound_sent":False
    }

def _canonical_uuid(value:str)->bool:
    try:
        return type(value) is str and str(UUID(value))==value
    except (ValueError,TypeError):
        return False

def _utf8_evidence_connection(dsn: str, **kwargs):
    """Session-only UTF8 decoding; source reader's validation stays intact.

    PostgreSQL SQL_ASCII test clusters may otherwise return text as bytes.
    Invalid/non-UTF8 values fail closed at the original reader validator.
    """
    import psycopg
    conn=psycopg.connect(dsn,**kwargs)
    try:
        conn.execute("SET client_encoding TO 'UTF8'")
        return conn
    except Exception:
        conn.close()
        raise


def execute_review(*, admin_query:Callable[[str],str]=pg,
                   private_key:Callable[[],str]=private_password,
                   event_reader:Callable=read_recognized_revenue_event,
                   now:datetime|None=None)->dict:
    result=_safe_status("HOLD_REV053_EVIDENCE_UNAVAILABLE","PRECHECK")
    stamp=now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        return result
    try:
        facts=json.loads(admin_query(CATALOG_SQL))
        if not isinstance(facts,dict) or len(facts)!=16 or (
            not all(v is True for v in facts.values())):
            result["stage"]="AUTHORITY_CATALOG_HOLD"
            return result
    except Exception:
        result["stage"]="AUTHORITY_CATALOG_UNAVAILABLE"
        return result
    result["restricted_login_catalog_pass"]=True

    try:
        candidate=admin_query(DISCOVER_SQL).strip()
    except Exception:
        result["stage"]="ONE_CANDIDATE_SOURCE_READ_UNAVAILABLE"
        return result
    if candidate==MISSING:
        result["status"]="REV053_NO_ELIGIBLE_EXISTING_EVENT_FOUND"
        result["stage"]="NO_MATCH"
        result["one_candidate_reviewed"]=False
        return result
    if not _canonical_uuid(candidate):
        result["stage"]="UNEXPECTED_CANDIDATE_SHAPE"
        return result
    result["one_candidate_reviewed"]=True
    result["stage"]="AUTHENTICATED_TENANT_READER"
    try:
        password=private_key()
        from psycopg.conninfo import make_conninfo
        dsn=make_conninfo(
            "host=/var/run/postgresql port=5432 dbname=empiredb",
            user=LOGIN,password=password,
        )
        verified=event_reader(
            event_id=candidate,tenant_id=TENANT,as_of=stamp,dsn=dsn,
            connect_factory=_utf8_evidence_connection,
        )
    except CanonicalRevenueEvidenceUnavailable:
        result["stage"]="CANONICAL_READER_EVIDENCE_HOLD"
        return result
    except Exception:
        result["stage"]="READER_UNAVAILABLE"
        return result

    if not (type(verified) is dict
        and verified.get("schema_version")==
            "empire.predictive_revenue.verified_event_read.v1"
        and verified.get("status")=="SINGLE_REVENUE_EVENT_VERIFIED"
        and verified.get("canonical_event_ref")==
            "canonical:commercial_events:"+candidate
        and verified.get("order_bound") is True
        and verified.get("tenant_lineage_matched") is True
        and verified.get("product_and_price_matched") is True
        and verified.get("single_event_not_daily_aggregate") is True
        and verified.get("daily_revenue_census_verified") is False
        and verified.get("forecast_source_verified") is False
        and verified.get("revenue_recognition_performed") is False
        and verified.get("execution_authority")=="none"
        and type(verified.get("amount_cents")) is int
        and verified.get("amount_cents")>0):
        result["stage"]="CANONICAL_EVENT_ATTESTATION_UNTRUSTED"
        return result

    result.update(
        status="REV053_ONE_EXISTING_CANONICAL_LEDGER_EVENT_MATCHED",
        stage="ONE_EVENT_VERIFIED",
        event_ref_fingerprint=hashlib.sha256(
            candidate.encode("ascii")).hexdigest()[:16],
        event_occurrence_utc=verified["occurred_at"],
        amount_minor_units=verified["amount_cents"],
        monetary_unit="UNVERIFIED_SOURCE_UNIT_NO_CURRENCY_ASSERTED",
        order_bound=True,tenant_lineage_matched=True,
        product_and_price_matched=True,
        single_event_not_daily_aggregate=True,
        existing_ledger_record_matched=True
    )
    return result

def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only-one-event",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only_one_event:
        print(json.dumps(_safe_status(
            "HOLD_EXPLICIT_ONE_EVENT_READ_ONLY_FLAG_REQUIRED","CLI")))
        return 2
    if os.geteuid()!=0:
        print(json.dumps(_safe_status("HOLD_ROOT_LOCAL_SESSION_REQUIRED","CLI")))
        return 2
    report=execute_review()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="REV053_ONE_EXISTING_CANONICAL_LEDGER_EVENT_MATCHED" else 2

if __name__=="__main__":
    raise SystemExit(main())
