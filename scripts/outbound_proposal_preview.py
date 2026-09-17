#!/usr/bin/env python3
"""Phase 3E review-only candidate/outbound proposal renderer."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from empire_os.buyer_discovery import (
    build_candidate,
    build_candidate_review_plan,
    build_reviewed_outbound_intent_plan,
)


def _load(path: str) -> dict:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("input JSON object required")
    return value


def _expiry(hours: int) -> str:
    if hours < 1 or hours > 168:
        raise ValueError("expiry must be 1-168 hours")
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate_json")
    ap.add_argument("contact_plan_json")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--postal-address", required=True)
    ap.add_argument("--proposed-by", default="buyer-discovery-preview")
    ap.add_argument("--idempotency-key", required=True,
                    help="Candidate-review idempotency key")
    ap.add_argument("--approved-review-id")
    ap.add_argument("--outbound-idempotency-key")
    ap.add_argument("--expiry-hours", type=int, default=24)
    args = ap.parse_args()

    candidate_raw = _load(args.candidate_json)
    contact_plan = _load(args.contact_plan_json)
    body = Path(args.body_file).read_text().strip()
    candidate = build_candidate(
        candidate_raw,
        entity_id=candidate_raw.get("entity_id"),
        entity_linked=bool(candidate_raw.get("entity_id")),
    )
    candidate_review = build_candidate_review_plan(
        candidate, contact_plan, idempotency_key=args.idempotency_key
    )

    reviewed_outbound = None
    if args.approved_review_id:
        outbound_idem = args.outbound_idempotency_key or f"{args.idempotency_key}:outbound"
        reviewed_outbound = build_reviewed_outbound_intent_plan(
            args.approved_review_id,
            subject=args.subject,
            body_text=body,
            proposed_by=args.proposed_by,
            expires_at=_expiry(args.expiry_hours),
            idempotency_key=outbound_idem,
            postal_address=args.postal_address,
        )

    output = {
        "decision": "review_only",
        "mode": "OBSERVE",
        "write_authorized": False,
        "candidate": {
            "prospect_id": candidate.prospect_id,
            "business_name": candidate.business_name,
            "offer_key": candidate.offer_key,
            "company_score": candidate.company_score,
            "decision_role": candidate.decision_role,
            "decision_score": candidate.decision_score,
        },
        "candidate_review_proposal": candidate_review,
        "message_preview": {
            "subject": args.subject,
            "body_text": body,
            "postal_address": args.postal_address,
        },
        "reviewed_outbound_proposal": reviewed_outbound,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
