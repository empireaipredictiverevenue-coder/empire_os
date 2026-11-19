#!/usr/bin/env python3
"""Canonical reply → intent → conversation join cardinality, aggregate only.

This is an independently bounded, read-only diagnostic of the *actual* foreign
key edges. A structural join, provider field, or contact string is NEVER proof
of original message authenticity, tenant consent, purchase intent or authority
for outbound/CRM writes. No raw IDs, bodies or addresses leave the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

import psycopg

# The old metadata-driven identity bridge only discovers same-named join keys;
# these three original tables use different names for their canonical edges.
# Count DISTINCT id on EACH relation, otherwise duplicate conversation rows
# multiply the outbound-intent count and conceal the real cardinality defect.
SQL = """
WITH recent AS MATERIALIZED (
    SELECT id, intent_id, provider_message_id, normalized_from_contact
    FROM public.outbound_replies
    ORDER BY received_at DESC NULLS LAST, id DESC
    LIMIT 100
),
joined AS (
    SELECT
        r.id,
        r.provider_message_id,
        r.normalized_from_contact,
        COUNT(DISTINCT i.id) AS intent_count,
        COUNT(DISTINCT c.id) AS conversation_count,
        COUNT(DISTINCT i.id) FILTER (
            WHERE i.channel = 'email'
              AND i.status IN ('sent', 'delivered', 'replied')
        ) AS email_sent_intent_count,
        COUNT(DISTINCT i.id) FILTER (
            WHERE i.channel = 'email'
        ) AS email_intent_count,
        COUNT(DISTINCT i.id) FILTER (
            WHERE i.channel = 'email' AND i.status = 'suppressed'
        ) AS suppressed_email_intent_count,
        COUNT(DISTINCT i.id) FILTER (
            WHERE i.channel = 'email'
              AND i.status IN ('draft', 'queued', 'scheduled', 'approved', 'pending')
        ) AS pending_email_intent_count,
        COUNT(DISTINCT i.id) FILTER (
            WHERE i.channel IS NOT NULL AND i.channel <> 'email'
        ) AS non_email_intent_count,
        COUNT(DISTINCT c.id) FILTER (
            WHERE c.channel = 'email'
              AND lower(c.state) IN ('open', 'active', 'engaged', 'replied')
              AND nullif(btrim(c.external_conversation_id), '') IS NOT NULL
              AND (
                   (i.prospect_id IS NOT NULL AND i.prospect_id = c.prospect_id)
                OR (i.entity_id IS NOT NULL AND i.entity_id = c.entity_id)
                OR (i.buyer_id IS NOT NULL AND i.buyer_id = c.buyer_id)
                OR (i.opportunity_id IS NOT NULL AND i.opportunity_id = c.opportunity_id)
              )
              AND (i.prospect_id IS NULL OR i.prospect_id = c.prospect_id)
              AND (i.entity_id IS NULL OR i.entity_id = c.entity_id)
              AND (i.buyer_id IS NULL OR i.buyer_id = c.buyer_id)
              AND (i.opportunity_id IS NULL OR i.opportunity_id = c.opportunity_id)
        ) AS active_context_count
    FROM recent AS r
    LEFT JOIN public.outbound_intents AS i
        ON i.id = r.intent_id
    LEFT JOIN public.empire_conversations AS c
        ON c.outbound_intent_id = r.intent_id
    GROUP BY r.id, r.provider_message_id, r.normalized_from_contact
)
SELECT
    count(*) AS reply_count,
    count(*) FILTER (WHERE intent_count = 0) AS intent_missing,
    count(*) FILTER (WHERE intent_count = 1) AS intent_unique,
    count(*) FILTER (WHERE intent_count > 1) AS intent_ambiguous,
    count(*) FILTER (WHERE conversation_count = 0) AS conversation_missing,
    count(*) FILTER (WHERE conversation_count = 1) AS conversation_unique,
    count(*) FILTER (WHERE conversation_count > 1) AS conversation_ambiguous,
    count(*) FILTER (WHERE email_sent_intent_count = 1)
        AS sent_email_intent_present,
    count(*) FILTER (WHERE active_context_count = 1 AND conversation_count = 1)
        AS active_email_context_present,
    count(*) FILTER (
        WHERE nullif(btrim(provider_message_id), '') IS NOT NULL
    ) AS provider_message_field_present,
    count(*) FILTER (
        WHERE nullif(btrim(normalized_from_contact), '') IS NOT NULL
    ) AS sender_field_present,
    count(*) FILTER (
        WHERE intent_count = 1 AND conversation_count = 1
          AND email_sent_intent_count = 1 AND active_context_count = 1
          AND nullif(btrim(provider_message_id), '') IS NOT NULL
          AND nullif(btrim(normalized_from_contact), '') IS NOT NULL
    ) AS structurally_reviewable_not_authenticated,
    count(*) FILTER (WHERE email_intent_count = 1) AS email_intent_present,
    count(*) FILTER (WHERE suppressed_email_intent_count = 1)
        AS suppressed_email_intent_present,
    count(*) FILTER (WHERE pending_email_intent_count = 1)
        AS pending_email_intent_present,
    count(*) FILTER (WHERE non_email_intent_count = 1)
        AS non_email_intent_present
FROM joined
"""

COLUMNS = (
    "reply_count", "intent_missing", "intent_unique", "intent_ambiguous",
    "conversation_missing", "conversation_unique", "conversation_ambiguous",
    "sent_email_intent_present", "active_email_context_present",
    "provider_message_field_present", "sender_field_present",
    "structurally_reviewable_not_authenticated",
    "email_intent_present", "suppressed_email_intent_present",
    "pending_email_intent_present", "non_email_intent_present",
)


def summarize(row: object) -> dict:
    """Validate exact aggregate shape and mathematical invariants."""
    if (not isinstance(row, (tuple, list)) or len(row) != len(COLUMNS)
            or any(type(x) is not int or x < 0 or x > 100 for x in row)):
        raise ValueError("CANONICAL_JOIN_AGGREGATE_INVALID")
    n = dict(zip(COLUMNS, row))
    total = n["reply_count"]
    if (sum(n[k] for k in ("intent_missing", "intent_unique", "intent_ambiguous")) != total
            or sum(n[k] for k in ("conversation_missing", "conversation_unique",
                                  "conversation_ambiguous")) != total
            or n["sent_email_intent_present"] > n["email_intent_present"]
            or n["email_intent_present"] > n["intent_unique"]
            or (n["sent_email_intent_present"]
                + n["suppressed_email_intent_present"]
                + n["pending_email_intent_present"]) > n["email_intent_present"]
            or n["non_email_intent_present"] > n["intent_unique"]
            or (n["non_email_intent_present"] + n["email_intent_present"]) > n["intent_unique"]
            or n["active_email_context_present"] > n["conversation_unique"]
            or n["structurally_reviewable_not_authenticated"] > min(
                n["intent_unique"], n["conversation_unique"],
                n["sent_email_intent_present"], n["active_email_context_present"],
                n["provider_message_field_present"], n["sender_field_present"],
            )):
        raise ValueError("CANONICAL_JOIN_AGGREGATE_CONTRADICTORY")
    return {
        "schema_version": "empire.reply_identity_lineage_structural_probe.v2",
        "status": (
            "NO_CANONICAL_REPLY_ROWS_IN_SAMPLE" if total == 0
            else "EXACT_CANONICAL_JOIN_STRUCTURAL_REVIEW_ONLY"
        ),
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_query_completed": True,
        "read_only": True,
        "database_writes": False,
        "canonical_edges": [
            "public.outbound_replies.intent_id=public.outbound_intents.id",
            "public.empire_conversations.outbound_intent_id=public.outbound_replies.intent_id",
        ],
        "reply_count": total,
        "sample_limit": 100,
        "sample_exhaustive": total < 100,
        "structural_counts": {
            k: n[k] for k in (
                "intent_missing", "intent_unique", "intent_ambiguous",
                "conversation_missing", "conversation_unique",
                "conversation_ambiguous",
            )
        },
        "read_only_metadata_counts": {
            k: n[k] for k in (
                "sent_email_intent_present", "active_email_context_present",
                "provider_message_field_present", "sender_field_present",
                "structurally_reviewable_not_authenticated",
                "email_intent_present", "suppressed_email_intent_present",
                "pending_email_intent_present", "non_email_intent_present",
            )
        },
        "email_other_or_unclassified_intent_status_count": (
            n["email_intent_present"] - n["sent_email_intent_present"]
            - n["suppressed_email_intent_present"]
            - n["pending_email_intent_present"]
        ),
        "exact_join_cardinality_checked": True,
        "provider_thread_authenticated": False,
        "contact_authenticated": False,
        "tenant_authenticated": False,
        "buyer_intent_verified": False,
        "outbound_authorized": False,
        "admission_authorized": False,
        "crm_mutations": False,
        "raw_ids_or_pii_emitted": False,
        "execution_authority": "none",
    }


def probe_readonly(dsn: str | None = None, *, connect=None) -> dict:
    """Read in the existing authorised DB-reader context or fail closed."""
    if dsn is None:
        dsn = os.getenv("EMPIREDB_DSN")
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("DEDICATED_REPLY_READER_CREDENTIAL_MISSING")
    reader = connect if connect is not None else psycopg.connect
    with reader(dsn, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '4000ms'")
            cur.execute(SQL)
            result = cur.fetchall()
            conn.rollback()
    if len(result) != 1:
        raise ValueError("CANONICAL_JOIN_AGGREGATE_MISSING")
    return summarize(result[0])


def unavailable() -> dict:
    """Safe, non-zero fallback; never expose a DSN or raw database error."""
    return {
        "status": "CANONICAL_JOIN_PROBE_UNAVAILABLE",
        "mode": "OBSERVE", "source_query_completed": False,
        "reply_count": None, "admission_authorized": False,
        "outbound_authorized": False, "execution_authority": "none",
    }


def main() -> int:
    if not os.getenv("EMPIREDB_DSN"):
        raise SystemExit("EMPIREDB_DSN unavailable")
    try:
        packet = probe_readonly()
    except Exception:
        print(json.dumps(unavailable()))
        return 2
    print(json.dumps(packet, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
