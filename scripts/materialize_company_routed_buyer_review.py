#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg

from empire_os.company_routed_buyer_review import (
    build_company_routed_review_queue,
)


ROOT = Path("/srv/empire_os")
SOURCE = ROOT / "runtime/hunter/buyer_deferred_enrichment.json"
OUTPUT = ROOT / "runtime/buyer_acquisition/company_routed_review_latest.json"


def _canonical_contact_history() -> tuple[set[str], set[str], set[str]]:
    dsn = os.getenv("EMPIREDB_DSN", "").strip()
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN required for company-routed history guard")

    prior_prospects: set[str] = set()
    prior_domains: set[str] = set()
    suppressed_emails: set[str] = set()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT DISTINCT
                    COALESCE(prospect_id::text, ''),
                    lower(split_part(normalized_recipient, '@', 2))
                FROM public.outbound_intents i
                WHERE i.status IN (
                    'sending','sent','delivered','replied',
                    'suppressed','bounced','failed'
                )
                   OR EXISTS (
                       SELECT 1
                       FROM public.outbound_events e
                       WHERE e.intent_id=i.id
                         AND e.event_type IN (
                           'send_attempt','sent','delivered','reply_received'
                         )
                   )
                """
            )
            for prospect_id, domain in cur.fetchall():
                if prospect_id:
                    prior_prospects.add(str(prospect_id))
                if domain:
                    prior_domains.add(str(domain).lower())

            cur.execute(
                """
                SELECT lower(normalized_contact)
                FROM public.outbound_suppressions
                WHERE normalized_contact LIKE '%@%'
                """
            )
            suppressed_emails.update(
                str(row[0]).lower()
                for row in cur.fetchall()
                if row and row[0]
            )
    return prior_prospects, prior_domains, suppressed_emails


def _canonical_exact_outbound_intents(candidate_emails: set[str]) -> set[str]:
    """Read-only exact-address duplicate detector for already-public research.

    Queries only supplied bounded addresses. Does not read mail bodies,
    create outreach intents, clear suppression or return raw data to logs.
    """
    from empire_os.storm_contractor_independent_evidence import BUSINESS_EMAIL_PATTERN

    if (not isinstance(candidate_emails, set)
            or len(candidate_emails) > 30
            or any(not isinstance(x, str)
                   or len(x) > 254
                   or not BUSINESS_EMAIL_PATTERN.fullmatch(x)
                   for x in candidate_emails)):
        raise ValueError("INVALID_BOUNDED_CONTRACTOR_EXACT_RECIPIENT_COHORT")
    if not candidate_emails:
        return set()
    dsn = os.getenv("EMPIREDB_DSN", "").strip()
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN required for exact contact intent history")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute(
                """
                SELECT DISTINCT lower(trim(normalized_recipient))
                FROM public.outbound_intents
                WHERE channel = 'email'
                  AND lower(trim(normalized_recipient)) = ANY(%s)
                """,
                (sorted(candidate_emails),),
            )
            matches = {str(row[0]) for row in cur.fetchall() if row and row[0]}
    if not matches <= candidate_emails:
        raise ValueError("UNTRUSTED_EXACT_RECIPIENT_DB_RESULT")
    return matches


def _review_exact_public_recipient_candidates(review: dict) -> set[str]:
    """Only already-vetted first-party/historical business contact evidence."""
    from empire_os.storm_contractor_independent_evidence import BUSINESS_EMAIL_PATTERN

    rows = review.get("packets")
    if not isinstance(rows, list) or len(rows) > 25:
        raise ValueError("UNBOUNDED_PUBLIC_RECIPIENT_RESEARCH")
    candidates: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("INVALID_PUBLIC_CONTACT_RESEARCH")
        source = row.get("business_contact_research") or {}
        if source.get("state") != "PUBLIC_GENERAL_COMPANY_ROUTE_HISTORICAL_PERSON_HOLD":
            continue
        if (source.get("outbound_authorized") is not False
                or source.get("person_candidate_current_route_verified") is not False
                or source.get("named_person_to_email_attribution_verified") is not False):
            raise ValueError("UNTRUSTED_PUBLIC_CONTACT_AUTHORITY")
        for field in ("first_party_business_contact_email", "historical_person_candidate_email"):
            value = source.get(field)
            if not isinstance(value, str) or not BUSINESS_EMAIL_PATTERN.fullmatch(value):
                raise ValueError("INVALID_PUBLIC_CONTACT_EMAIL_CANDIDATE")
            candidates.add(value)
    if len(candidates) > 30:
        raise ValueError("UNBOUNDED_PUBLIC_EMAIL_CANDIDATES")
    return candidates


def _contractor_source_review_date(utc_now):
    """Public research evidence dates use founder local time (Europe/London).

    Avoid rejecting a 10 Oct UK-captured observation from an existing
    authorised service that starts at 23:xx UTC on 9 Oct.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if not isinstance(utc_now, datetime) or utc_now.tzinfo is None:
        raise ValueError("AWARE_CONTRACTOR_OBSERVATION_TIME_REQUIRED")
    return utc_now.astimezone(ZoneInfo("Europe/London")).date()


def refresh_existing_contractor_history(
    *, prior_contact_domains: set[str], suppressed_emails: set[str],
) -> dict:
    """Use this authorised one-shot DB reader for the existing Revenue Strike.

    The caller already obtained these sets under SET TRANSACTION READ ONLY.
    No new DB login, secret reading, service, timer, outbound or CRM write.
    A negative domain search never clears a named recipient.
    """
    from datetime import date, datetime, timezone
    from empire_os.storm_contractor_review import attach_existing_canonical_contact_history
    from scripts.refresh_contractor_revenue_review import run, write_review_snapshot

    today = datetime.now(timezone.utc)
    review = run(as_of=_contractor_source_review_date(today), now=today)
    candidates = _review_exact_public_recipient_candidates(review)
    # Authenticated read-only lookup is independent of domain-only history.
    # An unavailable exact lookup fails closed without writing a snapshot.
    prior_exact = _canonical_exact_outbound_intents(candidates)
    checked = attach_existing_canonical_contact_history(
        review,
        prior_contact_domains=prior_contact_domains,
        suppressed_emails=suppressed_emails,
        prior_recipient_intents=prior_exact,
    )
    if (checked.get("mode") != "OBSERVE"
            or checked.get("outbound_authorized") is not False
            or checked.get("contract_sent") is not False
            or checked.get("execution_authority") != "none"
            or checked["summary"].get("approved_outbound_count") != 0
            or checked["summary"].get("verified_payments") != 0
            or checked.get("canonical_domain_history_observed") is not True
            or checked.get("individual_recipient_suppression_cleared") is not False):
        raise ValueError("UNSAFE_CONTRACTOR_CANONICAL_HISTORY_RESULT")
    checked["canonical_domain_history_read_at"] = today.isoformat()
    write_review_snapshot(checked)
    return {
        "contractor_history_state": "CANONICAL_DOMAIN_HISTORY_OBSERVED",
        "contractor_company_count": checked["summary"]["historical_contractor_companies"],
        "contractor_prior_contact_domain_holds": checked["summary"]["prior_outbound_domain_review_holds"],
        "contractor_suppressed_contact_domain_holds": checked["summary"]["suppressed_domain_contact_holds"],
        "contractor_exact_recipient_checks": checked["summary"]["exact_recipient_outbound_intent_checks"],
        "contractor_exact_intent_holds": checked["summary"]["exact_recipient_prior_intent_holds"],
        "contractor_exact_suppression_holds": checked["summary"]["exact_recipient_suppression_holds"],
        "contractor_named_recipients_cleared": 0,
        "contractor_outbound_authorized": False,
    }


def main() -> int:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = [
        row
        for row in data.values()
        if isinstance(row, dict)
    ] if isinstance(data, dict) else []
    try:
        prior_prospects, prior_domains, suppressed_emails = (
            _canonical_contact_history()
        )
    except Exception as exc:
        payload = {
            "schema_version": "empire.company-routed-buyer-review.v1",
            "candidate_count": 0,
            "review_ready_count": 0,
            "ambiguous_person_count": 0,
            "no_same_domain_person_count": 0,
            "prior_contact_history_count": 0,
            "suppressed_route_count": 0,
            "items": [],
            "execution_authority": "none",
            "outbound_authorized": False,
            "database_write_performed": False,
            "payment_action": False,
            "actual_revenue": False,
            "history_guard_ok": False,
            "history_guard_error": type(exc).__name__,
        }
    else:
        payload = build_company_routed_review_queue(
            rows,
            prior_contact_prospect_ids=prior_prospects,
            prior_contact_domains=prior_domains,
            suppressed_emails=suppressed_emails,
        )
        payload["history_guard_ok"] = True
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUTPUT)
    contractor_result = {
        "contractor_history_state": "BLOCKED_CANONICAL_HISTORY_UNAVAILABLE",
        "contractor_outbound_authorized": False,
        "contractor_named_recipients_cleared": 0,
    }
    if payload.get("history_guard_ok") is True:
        try:
            contractor_result = refresh_existing_contractor_history(
                prior_contact_domains=prior_domains,
                suppressed_emails=suppressed_emails,
            )
        except Exception as exc:
            # Do not leak DB/recipient details; preserve the successful buyer
            # review. Never claim a new contractor history check succeeded.
            contractor_result["contractor_history_state"] = (
                "BLOCKED_" + type(exc).__name__
            )
    print(json.dumps({
        "ok": True,
        "candidate_count": payload["candidate_count"],
        "review_ready_count": payload["review_ready_count"],
        "ambiguous_person_count": payload["ambiguous_person_count"],
        "outbound_authorized": False,
        "founder_gate_required": True,
        "history_guard_ok": payload.get("history_guard_ok") is True,
        "prior_contact_history_count": payload.get(
            "prior_contact_history_count", 0
        ),
        "suppressed_route_count": payload.get("suppressed_route_count", 0),
        "output": str(OUTPUT),
        **contractor_result,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
