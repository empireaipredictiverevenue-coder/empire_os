"""Exact two founder-approved Gmail followups: canonical read-only suppression proof.

No send, suppression change, SQL mutation, permission/role change, credential
output, or inference from negative historical Gmail searches. Must execute via
the EXISTING authorised sender credential owner (root-protected environment).
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_founder_email_db_visibility_20261023 import (
    load_sender_dsn, policy_all_rows_visible,
)

RECIPIENTS = ("info@spcgc.com", "team@dentalranking.co.uk")
SENDER_ENV = Path("/srv/empire_os/runtime/secrets/outbound.env")
TABLE = "public.outbound_suppressions"
ROLE = "empire_outbound_sender"
SQL_SUPPRESSIONS = """
SELECT count(*)
FROM public.outbound_suppressions
WHERE lower(btrim(normalized_contact)) IN (%s, %s, %s)
"""
SQL_HISTORY = """
SELECT count(*)
FROM public.outbound_intents
WHERE channel='email' AND lower(btrim(normalized_recipient)) = %s
"""
SQL_IDENTITY = """
SELECT current_user, current_setting('transaction_read_only'),
       oid, rolsuper, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname=current_user
"""
SQL_TABLE = """
SELECT c.relrowsecurity, c.relforcerowsecurity,
       row_security_active(c.oid::regclass)
FROM pg_catalog.pg_class c
WHERE c.oid=pg_catalog.to_regclass(%s)
"""
SQL_POLICIES = """
SELECT polcmd,polpermissive,pg_get_expr(polqual,polrelid),polroles
FROM pg_catalog.pg_policy
WHERE polrelid=%s::regclass
"""


def assess(dsn: str, *, connect_factory=None) -> dict:
    if not isinstance(dsn,str) or not dsn.strip():
        raise ValueError("EXISTING_CANONICAL_SENDER_CREDENTIAL_REQUIRED")
    if connect_factory is None:
        import psycopg
        connect_factory=psycopg.connect
    with connect_factory(dsn,connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE empire_outbound_sender")
            cur.execute("SET LOCAL statement_timeout = '3000ms'")
            cur.execute(SQL_IDENTITY)
            ident=cur.fetchone()
            if (not isinstance(ident,(tuple,list)) or len(ident)!=5
                or ident[0]!=ROLE or ident[1]!="on"
                or type(ident[2]) is not int
                or ident[3] is not False or ident[4] is not False):
                raise ValueError("ROLE_OR_READONLY_AUTHORITY_INVALID")
            for table in ("public.outbound_suppressions", "public.outbound_intents"):
                cur.execute(
                    "SELECT pg_catalog.has_table_privilege(current_user,%s,'SELECT')",
                    (table,),
                )
                if cur.fetchone()!=(True,):
                    raise ValueError("REQUIRED_CANONICAL_READ_PRIVILEGE_UNAVAILABLE")
                cur.execute(SQL_TABLE,(table,))
                visibility=cur.fetchone()
                if not isinstance(visibility,(tuple,list)) or len(visibility)!=3:
                    raise ValueError("CANONICAL_TABLE_UNAVAILABLE")
                cur.execute(SQL_POLICIES,(table,))
                policies=cur.fetchall()
                if not policy_all_rows_visible(visibility[0],visibility[2],policies,ident[2]):
                    raise ValueError("GLOBAL_CANONICAL_ROW_VISIBILITY_NOT_VERIFIED")
            # Fixed exact addresses: other recipients cannot be substituted via CLI.
            results=[]
            for recipient in RECIPIENTS:
                domain=recipient.rsplit("@",1)[1]
                cur.execute(SQL_SUPPRESSIONS,(recipient,domain,"@"+domain))
                count=cur.fetchone()
                cur.execute(SQL_HISTORY,(recipient,))
                earlier=cur.fetchone()
                if (not isinstance(count,(tuple,list)) or len(count)!=1
                    or type(count[0]) is not int or count[0]<0
                    or not isinstance(earlier,(tuple,list)) or len(earlier)!=1
                    or type(earlier[0]) is not int or earlier[0]<0):
                    raise ValueError("INVALID_CANONICAL_COUNTS")
                results.append({
                    "recipient":recipient,
                    "exact_and_domain_suppression_matches":count[0],
                    "canonical_prior_intent_count":earlier[0],
                    "suppression_verified_clear":count[0]==0,
                    "existing_gmail_first_touch_acknowledged":True,
                    "send_authorized_by_this_tool":False,
                })
            cur.execute("ROLLBACK")
    return {
        "schema_version":"empire.two_followups.suppression_readonly.v1",
        "source":"CANONICAL_EMPIREDB",
        "source_role":ROLE,
        "full_row_visibility_verified":True,
        "transaction":"READ_ONLY",
        "status":("SUPPRESSION_CLEAR_FOR_MANUAL_SEND_REVIEW" if
                  all(r["suppression_verified_clear"] for r in results)
                  else "HELD_CANONICAL_SUPPRESSION_MATCH"),
        "recipients":results,
        "mailbox_bounces_and_new_replies_rechecked_here":False,
        "existing_gmail_drafts_modified":False,
        "gmail_messages_sent":False,
        "sender_governor_authority_changed":False,
        "outbound_send_authorized":False,
        "database_writes":False,
        "money_moved":False,
    }


def main() -> int:
    try:
        dsn=load_sender_dsn(SENDER_ENV)
        report=assess(dsn)
    except Exception:
        report={
            "schema_version":"empire.two_followups.suppression_readonly.v1",
            "status":"HELD_CANONICAL_SUPPRESSION_READER_UNAVAILABLE",
            "source":"CANONICAL_EMPIREDB",
            "full_row_visibility_verified":False,
            "recipient_count":2,
            "outbound_send_authorized":False,
            "gmail_messages_sent":False,
            "database_writes":False,
        }
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="SUPPRESSION_CLEAR_FOR_MANUAL_SEND_REVIEW" else 2


if __name__=="__main__":
    raise SystemExit(main())
