#!/usr/bin/env python3
"""One-shot exact-history lookup for Champions' published partnerships inbox.

Requires an authorised EmpireDB read-only environment. No email send, approval,
recipient guessing, status mutation, or credentials printed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from empire_os.enterprise_published_route_history import review_published_route

REVIEW = Path("/srv/empire_os/runtime/predictive_revenue/enterprise_commercial_review_latest.json")


def select_route(review: dict) -> dict:
    if (not isinstance(review, dict)
            or review.get("mode") != "OBSERVE"
            or review.get("outreach_authorized") is not False):
        raise ValueError("UNSAFE_ENTERPRISE_REVIEW")
    candidates = [p for p in (review.get("packets") or [])
                  if isinstance(p, dict) and p.get("domain") == "championsgroupholdings.com"]
    if len(candidates) != 1 or candidates[0].get("outreach_authorized") is not False:
        raise ValueError("CHAMPIONS_REVIEW_RECORD_UNAVAILABLE")
    routes = (candidates[0].get("market_role_review") or {}).get("public_contact_routes_for_review_only") or []
    matching = [r for r in routes if isinstance(r, dict)
                and str(r.get("published_email") or "").lower() == "partnerships@championsgh.com"
                and r.get("person_bound") is False
                and r.get("software_vendor_fit_verified") is False
                and r.get("outreach_authorized") is False]
    if len(matching) != 1:
        raise ValueError("CURATED_PUBLISHED_ROUTE_UNAVAILABLE")
    return matching[0]


def main() -> int:
    try:
        if REVIEW.is_symlink():
            raise ValueError("UNSAFE_ENTERPRISE_REVIEW_FILE")
        data = json.loads(REVIEW.read_text(encoding="utf-8"))
        route = select_route(data)
        result = review_published_route(
            os.getenv("EMPIREDB_DSN", ""),
            email=route["published_email"],
            source_url=route["source_url"],
            company_domain="championsgroupholdings.com",
        )
    except Exception:
        print(json.dumps({
            "status": "HELD_CANONICAL_PUBLISHED_ROUTE_READ_UNAVAILABLE",
            "mode": "OBSERVE", "recipient_identity_verified": False,
            "recipient_send_time_suppression_cleared": False,
            "founder_send_authorized": False,
            "outreach_authorized": False,
            "outbound_sent": False, "database_writes": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
