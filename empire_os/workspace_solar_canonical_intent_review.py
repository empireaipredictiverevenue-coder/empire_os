"""Private six-thread Gmail -> canonical EmpireDB intent existence review.

Bounded read-only aggregate using the EXISTING systemd-credential-backed
closer observer. No new login, migration, CRM insert, message/body read,
public API, send, payment or customer identifier disclosure.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from empire_os.empiredb_founder_reply_mailbox import EmpireDBFounderReplyMailbox
from empire_os.workspace_solar_reply_tracking import ANCHORS

SCHEMA = "empire.workspace_solar_canonical_intent_review.v1"
READ_ROLE = "empire_closer_observer"

# The only PII in this code is six existing, exact, previously emailed
# recipient addresses used as SQL parameters. Never return or log them.
SQL = """
WITH targets AS (
 SELECT thread_id, expected_recipient, original_provider_sent_id
 FROM unnest(%s::text[],%s::text[],%s::text[])
      AS target(thread_id,expected_recipient,original_provider_sent_id)
)
SELECT t.thread_id,
       COUNT(i.id)::bigint,
       COUNT(i.id) FILTER (
         WHERE i.status IN ('sent','delivered','replied')
           AND lower(btrim(i.normalized_recipient))=t.expected_recipient
       )::bigint,
       COUNT(i.id) FILTER (
         WHERE i.status IN ('sent','delivered','replied')
           AND lower(btrim(i.normalized_recipient))=t.expected_recipient
           AND i.approved_at IS NOT NULL AND i.approved_by IS NOT NULL
       )::bigint,
       COUNT(i.id) FILTER (
         WHERE i.status IN ('sent','delivered','replied')
           AND lower(btrim(i.normalized_recipient))=t.expected_recipient
           AND (
             i.metadata->>'gmail_message_id'=t.original_provider_sent_id
             OR i.metadata->>'provider_message_id'=t.original_provider_sent_id
           )
       )::bigint
FROM targets t
LEFT JOIN public.outbound_intents i
  ON i.channel='email'
 AND i.metadata->>'provider'='gmail'
 AND i.metadata->>'gmail_thread_id'=t.thread_id
GROUP BY t.thread_id
ORDER BY t.thread_id
"""


class CanonicalIntentReviewUnavailable(ValueError):
    """Source visibility or read authority is missing: never claim zero."""


def _parse_counts(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list) or len(rows) != len(ANCHORS):
        raise CanonicalIntentReviewUnavailable("INCOMPLETE_CANONICAL_PROBE")
    counts: dict[str, tuple[int, int, int, int]] = {}
    known = {anchor[3] for anchor in ANCHORS}
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 5:
            raise CanonicalIntentReviewUnavailable("CANONICAL_PROBE_SCHEMA_INVALID")
        tid, total, matching, approved, sent_provenance = row
        if (not isinstance(tid, str) or tid not in known or tid in counts
                or any(type(x) is not int or not 0 <= x <= 100000
                       for x in (total, matching, approved, sent_provenance))
                or not (sent_provenance <= matching <= total)
                or approved > matching):
            raise CanonicalIntentReviewUnavailable("CANONICAL_PROBE_CONTRADICTORY")
        counts[tid] = (total, matching, approved, sent_provenance)
    if set(counts) != known:
        raise CanonicalIntentReviewUnavailable("CANONICAL_PROBE_COVERAGE_MISSING")
    items = []
    for company, _, _, tid, _ in ANCHORS:
        total, matching, approved, original_id = counts[tid]
        if total == 0:
            status = "NO_CANONICAL_GMAIL_THREAD_INTENT_VISIBLE_TO_READER"
            next_action = "REVIEW_HISTORICAL_SENT_EVIDENCE_FOR_CANONICAL_ADMISSION"
        elif matching == 0:
            status = "GMAIL_THREAD_PRESENT_ORIGINAL_RECIPIENT_NOT_BOUND"
            next_action = "REVIEW_EXACT_ORIGINAL_RECIPIENT_MISMATCH"
        elif matching > 1:
            status = "AMBIGUOUS_CANONICAL_SENT_INTENT"
            next_action = "RESOLVE_CANONICAL_INTENT_AMBIGUITY"
        elif approved != 1:
            status = "CANONICAL_APPROVAL_EVIDENCE_NOT_COMPLETE"
            next_action = "VERIFY_ACTUAL_FOUNDER_APPROVAL_PROVENANCE"
        elif original_id != 1:
            status = "ORIGINAL_PROVIDER_SENT_MESSAGE_ID_NOT_BOUND"
            next_action = "RECONCILE_ORIGINAL_PROVIDER_MESSAGE_PROVENANCE"
        else:
            status = "STRUCTURAL_CANDIDATE_ONLY_REQUIRES_TENANT_AND_PROVIDER_REVIEW"
            next_action = "VERIFY_TENANT_CONTACT_SUPPRESSION_AND_BUYER_REPLY"
        items.append({
            "company": company,
            "status": status,
            "next_founder_review_action": next_action,
            "historical_send_reconciliation_automatically_authorized": False,
            "canonical_same_thread_intents_visible": total,
            "canonical_exact_recipient_sent_intents_visible": matching,
            "original_sent_provider_message_id_matches": original_id,
            "canonical_approval_rows_visible": approved,
            "canonical_contact_verified": False,
            "tenant_identity_verified": False,
            "crm_handoff_authorized": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "CANONICAL_INTENT_AGGREGATES_REVIEW_ONLY",
        "mode": "OBSERVE",
        "source": "existing_empiredb_closer_observer_reader",
        "read_only": True,
        "source_visibility_complete": False,
        "scope": "six_preexisting_exact_workspace_outbound_anchors",
        "threads_checked": len(items),
        "items": items,
        "zero_count_means_no_row_visible_not_global_absence": True,
        "founder_crm_delivery_verified": False,
        "crm_mutation": False,
        "outbound_sent": False,
        "payment_executed": False,
        "execution_authority": "none",
    }


def review_six_workspace_canonical_intents(
    *, connect_factory: Callable[..., Any] | None = None,
    dsn: str | None = None,
) -> dict[str, Any]:
    """Six exact parameterised aggregates under current authorised login."""
    credential = (
        dsn if dsn is not None else EmpireDBFounderReplyMailbox().dsn
    )
    if not isinstance(credential, str) or not credential.strip():
        raise CanonicalIntentReviewUnavailable("DEDICATED_READER_UNAVAILABLE")
    if connect_factory is None:
        import psycopg
        connect_factory = psycopg.connect
    try:
        with connect_factory(credential, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE " + READ_ROLE)
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                cur.execute(SQL, (
                    [a[3] for a in ANCHORS],
                    [a[2] for a in ANCHORS],
                    [a[4] for a in ANCHORS],
                ))
                rows = cur.fetchall()
                cur.execute("ROLLBACK")
    except Exception:
        raise CanonicalIntentReviewUnavailable(
            "DEDICATED_CANONICAL_READER_FAILED"
        ) from None
    return _parse_counts(rows)
