#!/usr/bin/env python3
"""Read-only consolidated Empire SEO/AEO/GEO/A2A + growth department status.

Reuses the existing first-party GSC observer, historical AEO 404 triage,
live organic release integrity check, owned public A2A discovery,
and marketing_growth research queue. It is NOT a new agent or scheduled
worker and does not publish, send, spend, scrape SERPs or touch customer DB.
"""
from __future__ import annotations

import argparse
from datetime import date
import json

from empire_os.search_intelligence.department_integration_review import (
    SCHEMA, IntegrationEvidenceHeld, run,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-only", action="store_true", required=True)
    parser.add_argument("--start-date", type=date.fromisoformat,
                        help="First date of bounded final GSC page window")
    parser.add_argument("--end-date", type=date.fromisoformat,
                        help="Last date of bounded final GSC page window")
    args = parser.parse_args(argv)
    if bool(args.start_date) != bool(args.end_date):
        parser.error("both start-date and end-date must be specified together")
    try:
        result = run(start=args.start_date, end=args.end_date)
    except IntegrationEvidenceHeld as error:
        result = {
            "schema_version": SCHEMA,
            "status": "HELD_UNVERIFIED_DEPENDENCY",
            "reason_code": str(error),
            "mode": "OBSERVE",
            "production_mutated": False,
            "buyer_conversions_verified": False,
            "execution_authority": "NONE",
        }
    except Exception:
        # Never emit a driver error, request URL, secret, stack trace or
        # private source packet through a status command.
        result = {
            "schema_version": SCHEMA,
            "status": "HELD_UNVERIFIED_DEPENDENCY",
            "reason_code": "SEO_DEPARTMENT_READONLY_SOURCE_UNAVAILABLE",
            "mode": "OBSERVE",
            "production_mutated": False,
            "buyer_conversions_verified": False,
            "execution_authority": "NONE",
        }
    print(json.dumps(result,sort_keys=True))
    return 2 if result["status"].startswith("HELD") else 0


if __name__ == "__main__":
    raise SystemExit(main())
