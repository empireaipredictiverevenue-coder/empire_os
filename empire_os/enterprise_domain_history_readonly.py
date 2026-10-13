"""Bounded canonical EmpireDB domain-history inspection, strictly read-only.

A negative domain search is NOT recipient clearance or send-time suppression.
No recipient identity or private connection string is returned.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

_DOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])?\.[a-z]{2,24}")

SQL = """
WITH targets AS (
  SELECT unnest(%s::text[]) AS domain
)
SELECT t.domain,
  EXISTS (
    SELECT 1 FROM public.outbound_intents i
    WHERE i.channel='email'
      AND lower(split_part(btrim(i.normalized_recipient),'@',2))=t.domain
  ) AS any_prior_intent,
  EXISTS (
    SELECT 1 FROM public.outbound_events e
    JOIN public.outbound_intents i ON e.intent_id=i.id
    WHERE i.channel='email'
      AND lower(split_part(btrim(i.normalized_recipient),'@',2))=t.domain
      AND e.event_type IN ('send_attempt','sent','delivered','reply_received')
  ) AS any_send_or_reply_event,
  EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE lower(btrim(s.normalized_contact)) IN (t.domain,'@'||t.domain)
       OR lower(split_part(btrim(s.normalized_contact),'@',2))=t.domain
  ) AS any_domain_suppression
FROM targets t ORDER BY t.domain
"""


def inspect_domains(
    dsn: str,
    domains: list[str],
    *,
    connect_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """One parameterized read-only query. All authority flags remain false."""
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("CANONICAL_EMPIREDB_DSN_REQUIRED")
    if (not isinstance(domains, list) or not domains or len(domains) > 16
            or any(not isinstance(x, str) or not _DOMAIN.fullmatch(x) for x in domains)
            or len(set(domains)) != len(domains)):
        raise ValueError("INVALID_BOUNDED_DOMAIN_COHORT")
    if connect_factory is None:
        import psycopg
        connect_factory = psycopg.connect
    with connect_factory(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5000ms'")
            cur.execute(SQL, (sorted(domains),))
            rows = cur.fetchall()
            cur.execute("ROLLBACK")
    if not isinstance(rows, list) or len(rows) != len(domains):
        raise ValueError("INVALID_CANONICAL_DOMAIN_READER_SHAPE")
    output: dict[str, Any] = {}
    for row in rows:
        if (not isinstance(row, (tuple, list)) or len(row) != 4
                or row[0] not in domains or row[0] in output
                or any(type(flag) is not bool for flag in row[1:])):
            raise ValueError("UNTRUSTED_CANONICAL_DOMAIN_READER_ROWS")
        domain, prior, event, suppression = row
        output[domain] = {
            "prior_canonical_intent_observed": prior,
            "canonical_send_or_reply_event_observed": event,
            "any_suppression_on_domain_observed": suppression,
            "domain_contact_history_state": (
                "PRIOR_HISTORY_OBSERVED" if prior or event
                else "NO_DOMAIN_HISTORY_OBSERVED_NOT_SEND_CLEARANCE"
            ),
            "recipient_identity_verified": False,
            "individual_recipient_suppression_cleared": False,
            "outreach_authorized": False,
        }
    if set(output) != set(domains):
        raise ValueError("MISSING_CANONICAL_DOMAIN_EVIDENCE")
    return {
        "schema_version": "empire.enterprise-domain-history-readonly.v1",
        "source": "CANONICAL_EMPIREDB",
        "mode": "OBSERVE",
        "database_transaction": "READ_ONLY",
        "domain_count": len(output),
        "domain_results": output,
        "individual_recipient_suppression_cleared": False,
        "founder_send_authorized": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }
