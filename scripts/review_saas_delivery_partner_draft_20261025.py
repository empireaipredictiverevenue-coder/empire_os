"""Existing EmpireDB sender's read-only Teconomy delivery-partner review.

Owner-only review. Never sends, creates an intent, changes suppression or
purports to grant authority. Reuses EmpireOS's existing RLS/row-visibility
checks and sender credential; unavailable privileges fail closed.
"""
from __future__ import annotations

import json
from typing import Any

from scripts.audit_founder_email_db_visibility_20261023 import (
    load_sender_dsn, policy_all_rows_visible,
)
from scripts.inspect_three_approved_b2b_outreach_20261024 import SQL_HISTORY
from scripts.inspect_two_approved_followups_suppression_20261024 import (
    ROLE, SENDER_ENV, SQL_IDENTITY, SQL_POLICIES, SQL_SUPPRESSIONS, SQL_TABLE,
)

RECIPIENT = "dennis.lupo@teconomy.ch"
DOMAIN = "teconomy.ch"
REVIEW_SCHEMA = "empire.saas.delivery_partner_exact_email_review.v1"
DRAFT_ID = "r4036658615946086992"


def decide(counts: tuple[int, int, int]) -> dict[str, Any]:
    if not isinstance(counts, tuple) or len(counts) != 3 or any(
        type(n) is not int or n < 0 for n in counts
    ):
        raise ValueError("CANONICAL_SUPPRESSION_OR_HISTORY_COUNTS_INVALID")
    suppression, prior_exact, prior_domain = counts
    if prior_exact > prior_domain:
        raise ValueError("CANONICAL_INTENTS_COUNT_INCONSISTENT")
    has_canonical_block = bool(suppression or prior_domain)
    return {
        "status": (
            "HOLD_CANONICAL_SUPPRESSION_OR_PREVIOUS_DOMAIN_OUTREACH"
            if has_canonical_block
            else "NO_CANONICAL_BLOCK_OBSERVED_REVIEW_ONLY"
        ),
        "exact_and_domain_suppression_count": suppression,
        "prior_exact_recipient_intent_count": prior_exact,
        "prior_domain_intent_count": prior_domain,
        "counts_full_visibility_verified": True,
        "no_canonical_contact_block_observed": not has_canonical_block,
        "outbound_authorized": False,
        "message_sent": False,
        "recipient_clearance_granted": False,
        "new_intent_created": False,
        "database_writes": False,
    }


def inspect(dsn: str, *, connect_factory=None) -> dict[str, Any]:
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("EXISTING_ROOT_PROTECTED_SENDER_DSN_REQUIRED")
    if connect_factory is None:
        import psycopg
        connect_factory = psycopg.connect

    with connect_factory(dsn, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL ROLE empire_outbound_sender")
            cursor.execute("SET LOCAL statement_timeout = '3000ms'")
            cursor.execute(SQL_IDENTITY)
            ident = cursor.fetchone()
            if (
                not isinstance(ident, (list, tuple))
                or len(ident) != 5
                or ident[0] != ROLE
                or ident[1] != "on"
                or type(ident[2]) is not int
                or ident[3] is not False
                or ident[4] is not False
            ):
                raise ValueError("EXISTING_DEDICATED_READ_ONLY_ROLE_NOT_VERIFIED")
            for table in ("public.outbound_suppressions", "public.outbound_intents"):
                cursor.execute(
                    "SELECT pg_catalog.has_table_privilege(current_user,%s,'SELECT')",
                    (table,),
                )
                if cursor.fetchone() != (True,):
                    raise ValueError("CANONICAL_TABLE_READ_PRIVILEGE_UNVERIFIED")
                cursor.execute(SQL_TABLE, (table,))
                visibility = cursor.fetchone()
                if not isinstance(visibility, (tuple, list)) or len(visibility) != 3:
                    raise ValueError("CANONICAL_TABLE_RLS_STATE_UNVERIFIED")
                cursor.execute(SQL_POLICIES, (table,))
                policies = cursor.fetchall()
                if not policy_all_rows_visible(
                    visibility[0], visibility[2], policies, ident[2]
                ):
                    raise ValueError("CANONICAL_RLS_FULL_ROW_VISIBILITY_UNVERIFIED")

            cursor.execute(SQL_SUPPRESSIONS, (RECIPIENT, DOMAIN, "@" + DOMAIN))
            suppressed = cursor.fetchone()
            cursor.execute(SQL_HISTORY, (RECIPIENT, DOMAIN))
            historical = cursor.fetchone()
            if (
                not isinstance(suppressed, (tuple, list))
                or len(suppressed) != 1
                or not isinstance(historical, (tuple, list))
                or len(historical) != 2
            ):
                raise ValueError("CANONICAL_COUNTS_MISSING_OR_UNTRUSTED")
            result = decide((suppressed[0], historical[0], historical[1]))
            connection.rollback()
    return {
        "schema_version": REVIEW_SCHEMA,
        "mode": "EXACT_COMPANY_READ_ONLY",
        "recipient": RECIPIENT,
        "company_domain": DOMAIN,
        "mailbox_draft_id": DRAFT_ID,
        "original_sender_credential_used": True,
        "canonical_source": "EmpireDB",
        "canonical_source_role": ROLE,
        "gmail_send_history_independently_rechecked_here": False,
        "company_delivery_capability_verified": False,
        "partner_agreement_verified": False,
        "founder_approval_for_this_send_verified": False,
        "recipient_permission_from_partner_post_not_equal_send_authority": True,
        "money_moved": False,
        **result,
    }


def main() -> int:
    try:
        result = inspect(load_sender_dsn(SENDER_ENV))
    except Exception:
        # Fail closed on all provider/driver failures, never display a DSN.
        result = {
            "schema_version": REVIEW_SCHEMA,
            "status": "HOLD_EXISTING_PROTECTED_SENDER_READER_UNAVAILABLE",
            "recipient": RECIPIENT,
            "company_domain": DOMAIN,
            "mailbox_draft_id": DRAFT_ID,
            "counts_full_visibility_verified": False,
            "outbound_authorized": False,
            "message_sent": False,
            "recipient_clearance_granted": False,
            "new_intent_created": False,
            "database_writes": False,
        }
    print(json.dumps(result, sort_keys=True))
    return (0 if result["status"] == "NO_CANONICAL_BLOCK_OBSERVED_REVIEW_ONLY"
            else 2)


if __name__ == "__main__":
    raise SystemExit(main())
