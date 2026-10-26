"""Read-only EmpireDB contact/suppression evidence for original Permit cohort.

An independently verified zero in the canonical suppression table advances
ONE readiness check. It does NOT prove complete external Gmail/CRM history,
actual reply delivery, contact rights, approval, or send authority.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
from typing import Any,Callable,Mapping

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_evidence_readiness import review
from scripts.audit_founder_email_db_visibility_20261023 import (
    policy_all_rows_visible,SQL_TABLE,SQL_POLICIES,
)
from empire_os.founder_one_to_one_suppression import SUPPRESSION_SQL as SQL_SUPPRESSIONS

ROLE="empire_outbound_sender"
SQL_IDENTITY = """
SELECT current_user, current_setting('transaction_read_only'),
       oid, rolsuper, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname=current_user
"""
SQL_HISTORY = """
SELECT
 count(*) FILTER (WHERE lower(btrim(normalized_recipient)) = %s),
 count(*)
FROM public.outbound_intents
WHERE channel = 'email'
  AND split_part(lower(btrim(normalized_recipient)), '@', 2) = %s
"""
CANONICAL_TABLES=("public.outbound_suppressions","public.outbound_intents")


def inspect(*,pilot:Mapping[str,Any],dsn:str,now:datetime,
            connect_factory:Callable[...,Any]|None=None)->dict:
    """Inspect exactly original ten bound, unsent drafts in one READ ONLY tx."""
    from empire_os.permit_national_buyer_pilot_readiness import validate_review
    validate_review(pilot)
    if (not isinstance(now,datetime) or now.utcoffset() is None or
        not isinstance(dsn,str) or not dsn.strip()):
        raise ValueError("PERMIT_CANONICAL_SENDER_READER_REQUIRED")
    rows=pilot["owner_review_queue"]
    if len(rows)!=10 or len({row["recipient"] for row in rows})!=10:
        raise ValueError("PERMIT_CANONICAL_EXACT_TEN_NOT_VERIFIED")
    if connect_factory is None:
        import psycopg
        connect_factory=psycopg.connect
    checked=[]
    try:
        with connect_factory(dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE empire_outbound_sender")
                cur.execute("SET LOCAL statement_timeout='3000ms'")
                cur.execute(SQL_IDENTITY)
                identity=cur.fetchone()
                if (not isinstance(identity,(tuple,list)) or len(identity)!=5
                    or identity[0]!=ROLE or identity[1]!="on"
                    or type(identity[2]) is not int
                    or identity[3] is not False or identity[4] is not False):
                    raise ValueError("PERMIT_CANONICAL_ROLE_AUTHORITY_NOT_VERIFIED")
                for table in CANONICAL_TABLES:
                    cur.execute(
                        "SELECT pg_catalog.has_table_privilege(current_user,%s,'SELECT')",
                        (table,))
                    if cur.fetchone()!=(True,):
                        raise ValueError("PERMIT_CANONICAL_TABLE_READ_UNAVAILABLE")
                    cur.execute(SQL_TABLE,(table,))
                    visibility=cur.fetchone()
                    if (not isinstance(visibility,(tuple,list)) or len(visibility)!=3):
                        raise ValueError("PERMIT_CANONICAL_RLS_NOT_VERIFIED")
                    cur.execute(SQL_POLICIES,(table,))
                    policies=cur.fetchall()
                    if not policy_all_rows_visible(
                        visibility[0],visibility[2],policies,identity[2]):
                        raise ValueError("PERMIT_CANONICAL_FULL_RLS_NOT_VERIFIED")
                for row in rows:
                    address=row["recipient"].strip().casefold()
                    domain=address.rsplit("@",1)[-1]
                    cur.execute(SQL_SUPPRESSIONS,(address,domain,"@"+domain))
                    suppressed=cur.fetchone()
                    cur.execute(SQL_HISTORY,(address,domain))
                    history=cur.fetchone()
                    if (not isinstance(suppressed,(tuple,list)) or len(suppressed)!=1
                        or type(suppressed[0]) is not int or suppressed[0]<0
                        or not isinstance(history,(tuple,list)) or len(history)!=2
                        or any(type(x) is not int or x<0 for x in history)
                        or history[0]>history[1]):
                        raise ValueError("PERMIT_CANONICAL_COUNT_UNTRUSTED")
                    checked.append({
                        "row":row,
                        "suppressed":suppressed[0],
                        "prior_exact":history[0],
                        "prior_domain":history[1],
                    })
                cur.execute("ROLLBACK")
    except ValueError:
        raise
    except Exception:
        raise ValueError("PERMIT_CANONICAL_AUTHORISED_READ_FAILED") from None
    # Generate trusted receipts ONLY from the same audited RLS-complete DB
    # snapshot. This verifier cannot be supplied as an untrusted JSON claim.
    fingerprint=sha256(digest({
        "checked_at":now.isoformat(),
        "source":"CANONICAL_EMPIREDB_FULL_RLS",
        "items":[(
            x["row"]["draft_id"],x["row"]["message_id"],
            x["suppressed"],x["prior_exact"],x["prior_domain"],
        ) for x in checked],
    }).encode()).hexdigest()[:24]
    trusted={}
    results=[]
    for entry in checked:
        row=entry["row"]
        supplied={}
        if entry["suppressed"]==0:
            proof={
                "source_kind":"EMPIREDB_SUPPRESSION_READER",
                "recipient_sha256":digest({"email":row["recipient"].casefold()}),
                "draft_id":row["draft_id"],
                "message_id":row["message_id"],
                "source_ref":"canonical-rlls-"+fingerprint+"-"+str(len(trusted)+1),
                "checked_at_utc":now.astimezone(timezone.utc).isoformat(),
                "independent_source_verified":True,
            }
            supplied["exact_domain_suppression"]=proof
            trusted[proof["source_ref"]]=(
                proof["recipient_sha256"],proof["draft_id"],proof["message_id"],
            )
        def verify(name:str,proof:Mapping[str,Any])->bool:
            expected=trusted.get(proof.get("source_ref"))
            return bool(name=="exact_domain_suppression" and expected is not None
                        and expected==(proof.get("recipient_sha256"),
                                       proof.get("draft_id"),proof.get("message_id")))
        readiness=review(
            draft=row,now=now,evidence=supplied,verify_source=verify)
        results.append({
            "state":(
                "HOLD_CANONICAL_SUPPRESSION_MATCH" if entry["suppressed"]>0
                else "REVIEW_CANONICAL_PRIOR_DOMAIN_CONTACT" if entry["prior_domain"]>0
                else "ZERO_CANONICAL_MATCHES_OTHER_HISTORY_NOT_VERIFIED"),
            "suppression_match_count":entry["suppressed"],
            "prior_exact_intents":entry["prior_exact"],
            "prior_domain_intents":entry["prior_domain"],
            "canonical_suppression_check_verified":(
                readiness["checks"]["exact_domain_suppression"]=="VERIFIED"),
            "format_checks_observed":readiness["observed_format_checks"],
            "external_checks_verified":readiness["independently_verified_checks"],
            "complete_contact_history_verified":False,
            "send_authorized":False,
        })
    counts=dict(sorted(Counter(x["state"] for x in results).items()))
    return {
        "schema_version":"empire.permit_canonical_history_suppression.readonly.v1",
        "status":"CANONICAL_TEN_READONLY_VERIFIED_NOT_SEND_CLEARANCE",
        "checked_at_utc":now.astimezone(timezone.utc).isoformat(),
        "source_role":ROLE,
        "full_rls_visibility_verified":True,
        "original_ten_verified":len(results),
        "canonical_zero_suppression_checks_verified":sum(
            x["canonical_suppression_check_verified"] for x in results),
        "canonical_suppression_matches_found":sum(
            x["suppression_match_count"] for x in results),
        "canonical_prior_domain_intents_found":sum(
            x["prior_domain_intents"] for x in results),
        "canonical_prior_exact_intents_found":sum(
            x["prior_exact_intents"] for x in results),
        "states":counts,
        "rows":results,  # no sender, recipient, message ID or raw mail body
        "workspace_reply_delivery_verified":False,
        "complete_contact_history_verified":False,
        "commercial_send_authorized":False,
        "emails_sent":False,
        "database_writes":False,
        "funds_moved":False,
    }
