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
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
