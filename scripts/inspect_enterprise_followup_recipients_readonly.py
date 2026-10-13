#!/usr/bin/env python3
"""One-shot, canonical EmpireDB recipient review for the existing Redwood/Sila threads.

Strictly read-only. Never sends, approves, suppresses, unsuppresses or changes
the outbound governor, and never treats a missing provider event as clearance.
Do not use this as a substitute for a fresh send-time governor claim.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable

RECIPIENTS = (
    "richard@redwoodservices.com",
    "kmartin@sila.com",
)
SQL = """
WITH targets AS (
    SELECT lower(btrim(value)) AS email
    FROM unnest(%s::text[]) AS target(value)
)
SELECT
    t.email,
    EXISTS (
        SELECT 1 FROM public.outbound_suppressions s
        WHERE lower(btrim(s.normalized_contact)) IN (
            t.email,
            split_part(t.email, '@', 2),
            '@' || split_part(t.email, '@', 2)
        )
    ) AS suppression_match,
    (
        SELECT count(*) FROM public.outbound_intents i
        WHERE i.channel='email'
          AND lower(btrim(i.normalized_recipient))=t.email
    ) AS matching_empiredb_intents,
    (
        SELECT count(*) FROM public.outbound_events e
        JOIN public.outbound_intents i ON i.id=e.intent_id
        WHERE i.channel='email'
          AND lower(btrim(i.normalized_recipient))=t.email
          AND e.event_type IN ('send_attempt','sent','delivered','reply_received')
    ) AS matching_send_or_reply_events
FROM targets t ORDER BY t.email
"""

def check(
    dsn: str, *, connect_factory: Callable[..., Any] | None = None
) -> dict[str, Any]:
    """Read canonical records once. Fails closed; never confers send authority."""
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("CANONICAL_EMPIREDB_DSN_REQUIRED")
    if connect_factory is None:
        import psycopg
        connect_factory = psycopg.connect
    with connect_factory(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '4000ms'")
            cur.execute(SQL, (list(RECIPIENTS),))
            rows = cur.fetchall()
            cur.execute("ROLLBACK")

    if not isinstance(rows, list):
        raise ValueError("UNTRUSTED_CANONICAL_READER_ROWS")
    results = {}
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            raise ValueError("INVALID_CANONICAL_READER_SHAPE")
        email, suppressed, intents, events = row
        if (email not in RECIPIENTS or email in results
                or type(suppressed) is not bool
                or type(intents) is not int or intents < 0
                or type(events) is not int or events < 0):
            raise ValueError("INVALID_CANONICAL_READER_EVIDENCE")
        results[email] = {
            "suppression_match": suppressed,
            "canonical_prior_email_intents": intents,
            "canonical_send_or_reply_events": events,
            "previously_contacted_in_connected_gmail": True,
            "unsent_followup_draft_exists_in_connected_gmail": True,
            "decision": (
                "HOLD_SUPPRESSED"
                if suppressed else "HOLD_PRIOR_GMAIL_CONTACT_AND_FOUNDER_SEND_GATES"
            ),
            "recipient_send_authorized": False,
        }
    if set(results) != set(RECIPIENTS):
        raise ValueError("MISSING_CANONICAL_READER_EVIDENCE")
    return {
        "schema_version": "empire.enterprise_followup_recipient_preflight.v1",
        "source": "CANONICAL_EMPIREDB",
        "transaction": "READ_ONLY",
        "mode": "OBSERVE",
        "status": "REVIEW_ONLY",
        "recipients": results,
        "independent_live_gmail_reply_recheck": False,
        "mailbox_authentication_verified": False,
        "founder_send_authorized": False,
        "outbound_sent": False,
        "database_writes": False,
        "payment_action": False,
    }


def main() -> int:
    try:
        result = check(os.getenv("EMPIREDB_DSN", ""))
    except Exception:
        # Do not expose SQL errors, DSN, private role names or credentials.
        print(json.dumps({
            "status": "HELD_CANONICAL_READER_UNAVAILABLE",
            "mode": "OBSERVE",
            "source": "CANONICAL_EMPIREDB",
            "recipient_send_authorized": False,
            "outbound_sent": False,
            "database_writes": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
