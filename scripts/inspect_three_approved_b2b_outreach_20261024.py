"""Founder-approved three B2B introductions: exact live EmpireDB read-only preflight.

One-off proof for three business addresses. No messaging, DML, role/ACL
mutation, identity disclosure or financial action. Must run through the
original protected sender credential; absence of access is a HOLD.
"""
from __future__ import annotations

import json

from scripts.audit_founder_email_db_visibility_20261023 import (
    load_sender_dsn, policy_all_rows_visible,
)
from scripts.inspect_two_approved_followups_suppression_20261024 import (
    ROLE, SENDER_ENV, SQL_IDENTITY, SQL_POLICIES, SQL_TABLE, SQL_SUPPRESSIONS,
)

RECIPIENTS = (
    "hello@roofingdemandlab.com",
    "insights@sectorial.io",
    "enquiries@connectcf.com",
)
# Checking the entire company domain detects a previous first touch to a
# different staff contact; no new email should be sent on a guessed blank slate.
SQL_HISTORY = """
SELECT
 count(*) FILTER (WHERE lower(btrim(normalized_recipient)) = %s),
 count(*)
FROM public.outbound_intents
WHERE channel = 'email'
  AND split_part(lower(btrim(normalized_recipient)), '@', 2) = %s
"""


def inspect(dsn: str, *, connect_factory=None) -> dict:
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("EXISTING_CANONICAL_CREDENTIAL_REQUIRED")
    if connect_factory is None:
        import psycopg
        connect_factory = psycopg.connect
    with connect_factory(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL ROLE empire_outbound_sender")
            cur.execute("SET LOCAL statement_timeout = '3000ms'")
            cur.execute(SQL_IDENTITY)
            identity = cur.fetchone()
            if (
                not isinstance(identity, (tuple, list))
                or len(identity) != 5
                or identity[0] != ROLE
                or identity[1] != "on"
                or type(identity[2]) is not int
                or identity[3] is not False
                or identity[4] is not False
            ):
                raise ValueError("ROLE_OR_READONLY_AUTHORITY_UNVERIFIED")
            for table in ("public.outbound_suppressions", "public.outbound_intents"):
                cur.execute(
                    "SELECT pg_catalog.has_table_privilege(current_user,%s,'SELECT')",
                    (table,),
                )
                if cur.fetchone() != (True,):
                    raise ValueError("CANONICAL_TABLE_SELECT_UNAVAILABLE")
                cur.execute(SQL_TABLE, (table,))
                visibility = cur.fetchone()
                if not isinstance(visibility, (tuple, list)) or len(visibility) != 3:
                    raise ValueError("CANONICAL_TABLE_OR_ROW_VISIBILITY_UNVERIFIED")
                cur.execute(SQL_POLICIES, (table,))
                policies = cur.fetchall()
                if not policy_all_rows_visible(
                    visibility[0], visibility[2], policies, identity[2]
                ):
                    raise ValueError("FULL_ROW_VISIBILITY_UNVERIFIED")
            recipients = []
            for address in RECIPIENTS:
                domain = address.rsplit("@", 1)[1]
                cur.execute(SQL_SUPPRESSIONS, (address, domain, "@" + domain))
                blocked = cur.fetchone()
                cur.execute(SQL_HISTORY, (address, domain))
                prior = cur.fetchone()
                if (
                    not isinstance(blocked, (tuple, list))
                    or len(blocked) != 1
                    or type(blocked[0]) is not int
                    or blocked[0] < 0
                    or not isinstance(prior, (tuple, list))
                    or len(prior) != 2
                    or any(type(x) is not int or x < 0 for x in prior)
                    or prior[0] > prior[1]
                ):
                    raise ValueError("CANONICAL_COUNTS_UNTRUSTED")
                recipients.append({
                    "recipient": address,
                    "exact_and_domain_suppression_matches": blocked[0],
                    "canonical_prior_exact_intents": prior[0],
                    "canonical_prior_domain_intents": prior[1],
                    "clear": blocked[0] == 0 and prior[1] == 0,
                })
            cur.execute("ROLLBACK")
    clear = all(r["clear"] for r in recipients)
    return {
        "schema_version": "empire.three_founder_approved_b2b.preflight.v1",
        "status": "THREE_RECIPIENTS_CLEAR_FOR_MANUAL_GMAIL_SEND"
        if clear else "HOLD_CANONICAL_SUPPRESSION_OR_PRIOR_OUTREACH",
        "source": "CANONICAL_EMPIREDB",
        "source_role": ROLE,
        "full_row_visibility_verified": True,
        "transaction": "READ_ONLY",
        "recipients": recipients,
        "new_gmail_mailbox_history_rechecked_here": False,
        "new_outbound_authorized_by_this_preflight": False,
        "new_message_sent": False,
        "database_writes": False,
        "money_moved": False,
    }


def main() -> int:
    try:
        report = inspect(load_sender_dsn(SENDER_ENV))
    except Exception:
        report = {
            "schema_version": "empire.three_founder_approved_b2b.preflight.v1",
            "status": "HOLD_PROTECTED_CANONICAL_DB_READER_UNAVAILABLE",
            "full_row_visibility_verified": False,
            "recipient_count": len(RECIPIENTS),
            "new_message_sent": False,
            "database_writes": False,
            "new_outbound_authorized_by_this_preflight": False,
        }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "THREE_RECIPIENTS_CLEAR_FOR_MANUAL_GMAIL_SEND" else 2


if __name__ == "__main__":
    raise SystemExit(main())
