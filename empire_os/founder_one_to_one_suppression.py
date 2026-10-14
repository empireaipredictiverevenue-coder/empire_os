"""Exact-recipient and domain suppression for a governed first-touch email.

Canonical governor context currently checks exact-address suppressions. This
bounded query supplements it with the whole-domain and @domain records and
existing canonical first-touch history. A failure is never send clearance.
"""
from __future__ import annotations

import re
from typing import Any, Callable

EMAIL = re.compile(r"^[^@\s]{1,64}@[a-zA-Z0-9][a-zA-Z0-9.-]{1,251}\.[a-zA-Z]{2,24}$")
SUPPRESSION_SQL = """
SELECT count(*) FROM public.outbound_suppressions
WHERE lower(btrim(normalized_contact)) IN (%s, %s, %s)
"""
HISTORY_SQL = """
SELECT count(*) FROM public.outbound_intents
WHERE channel = 'email' AND lower(btrim(normalized_recipient)) = %s
AND id <> %s::uuid
AND status IN ('sent','delivered','replied','failed','suppressed')
"""


class OneToOnePreflightUnavailable(RuntimeError):
    """Never include DB credentials or private provider errors in responses."""


def read_one_to_one_preflight(
    dsn: str, *, recipient: str, intent_id: str,
    connect_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    address = str(recipient or "").strip().casefold()
    if (not EMAIL.fullmatch(address)
            or not re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", str(intent_id or ""))
            or not isinstance(dsn, str) or not dsn.strip()):
        raise OneToOnePreflightUnavailable("BOUND_CANONICAL_RECIPIENT_READER_REQUIRED")
    domain = address.rsplit('@', 1)[-1]
    if connect_factory is None:
        try:
            import psycopg
        except ImportError:
            raise OneToOnePreflightUnavailable("CANONICAL_READER_DRIVER_MISSING") from None
        connect_factory = psycopg.connect
    try:
        with connect_factory(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE empire_outbound_sender")
                cur.execute("SET LOCAL statement_timeout = '3000ms'")
                cur.execute(SUPPRESSION_SQL, (address, domain, '@' + domain))
                suppressed = cur.fetchone()
                cur.execute(HISTORY_SQL, (address, intent_id))
                earlier = cur.fetchone()
                cur.execute("ROLLBACK")
    except Exception:
        raise OneToOnePreflightUnavailable("CANONICAL_ONE_TO_ONE_PREFLIGHT_FAILED") from None
    if (not isinstance(suppressed, (tuple, list)) or len(suppressed) != 1
            or not isinstance(earlier, (tuple, list)) or len(earlier) != 1
            or type(suppressed[0]) is not int or type(earlier[0]) is not int
            or suppressed[0] < 0 or earlier[0] < 0):
        raise OneToOnePreflightUnavailable("INVALID_SUPPRESSION_OR_HISTORY_EVIDENCE")
    return {
        "schema_version": "empire.founder.one_to_one_preflight.v1",
        "source": "CANONICAL_EMPIREDB",
        "mode": "READ_ONLY",
        "exact_and_domain_suppression_cleared": suppressed[0] == 0,
        "no_existing_canonical_contact_history": earlier[0] == 0,
        "existing_suppression_match_count": suppressed[0],
        "existing_canonical_contact_count": earlier[0],
        "other_mailboxes_checked": False,
        "send_authorized": False,
        "database_writes": False,
    }
