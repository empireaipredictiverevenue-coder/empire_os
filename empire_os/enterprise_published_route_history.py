"""Exact published-mailbox history evidence without recipient send authority.

This reader checks only a first-party published address supplied through an
existing internal review. It never discovers, infers or guesses a person's mail.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

_EMAIL = re.compile(r"[a-z0-9][a-z0-9._+%-]{0,63}@[a-z0-9][a-z0-9.-]{1,251}\.[a-z]{2,24}")
SQL = """
WITH target AS (
  SELECT lower(btrim(%s::text)) AS email
)
SELECT
  EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE lower(btrim(s.normalized_contact)) IN (
      t.email, split_part(t.email, '@', 2), '@'||split_part(t.email, '@', 2)
    )
  ) AS suppression_match,
  (SELECT count(*) FROM public.outbound_intents i
   WHERE i.channel='email' AND lower(btrim(i.normalized_recipient))=t.email
  ) AS existing_outbound_intents,
  (SELECT count(*) FROM public.outbound_events e
   JOIN public.outbound_intents i ON i.id=e.intent_id
   WHERE i.channel='email' AND lower(btrim(i.normalized_recipient))=t.email
     AND e.event_type IN ('send_attempt','sent','delivered','reply_received')
  ) AS existing_send_or_reply_events
FROM target t
"""


def review_published_route(
    dsn: str, *, email: str, source_url: str, company_domain: str,
    connect_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Check an exact public route only, never a guessed individual address."""
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("CANONICAL_EMPIREDB_DSN_REQUIRED")
    address = str(email or "").strip().lower()
    company = str(company_domain or "").strip().lower()
    if not _EMAIL.fullmatch(address) or company != "championsgroupholdings.com":
        raise ValueError("INVALID_CURATED_PUBLISHED_ROUTE")
    if address != "partnerships@championsgh.com":
        raise ValueError("UNVERIFIED_EMAIL_OR_INFERRED_PERSON_MAILBOX")
    source = urlsplit(str(source_url or ""))
    if (source.scheme != "https" or source.hostname != company
            or source.path.rstrip("/") != "/contact"):
        raise ValueError("NOT_OFFICIAL_PUBLISHED_CONTACT_PAGE")
    if connect_factory is None:
        import psycopg
        connect_factory = psycopg.connect
    with connect_factory(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '4000ms'")
            cur.execute(SQL, (address,))
            rows = cur.fetchall()
            cur.execute("ROLLBACK")
    if (not isinstance(rows, list) or len(rows) != 1
            or not isinstance(rows[0], (tuple, list)) or len(rows[0]) != 3
            or type(rows[0][0]) is not bool
            or type(rows[0][1]) is not int or rows[0][1] < 0
            or type(rows[0][2]) is not int or rows[0][2] < 0):
        raise ValueError("INVALID_CANONICAL_ROUTE_HISTORY_READBACK")
    suppressed, intents, events = rows[0]
    return {
        "schema_version": "empire.enterprise-published-route-history.v1",
        "mode": "OBSERVE",
        "source": "CANONICAL_EMPIREDB",
        "database_transaction": "READ_ONLY",
        "company_domain": company,
        "published_email": address,
        "published_on_company_site_url": source_url,
        "published_route_context": "HOME_SERVICES_BUSINESS_PARTNERSHIPS",
        "suppression_match_observed": suppressed,
        "prior_exact_outbound_intent_count": intents,
        "prior_exact_send_or_reply_event_count": events,
        "known_domain_alias_on_official_site": True,
        "verified_software_procurement_route": False,
        "person_bound": False,
        "recipient_identity_verified": False,
        "recipient_send_time_suppression_cleared": False,
        "founder_send_authorized": False,
        "outreach_authorized": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }
