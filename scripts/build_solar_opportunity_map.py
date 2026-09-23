#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.solar_opportunity_map import (
    build_solar_opportunity_map,
    write_solar_opportunity_map,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prospect-id",
        action="append",
        required=True,
        help="Canonical solar prospect id; may be repeated.",
    )
    args = parser.parse_args()

    rows = []
    failed = []
    for prospect_id in dict.fromkeys(args.prospect_id):
        try:
            payload = build_solar_opportunity_map(prospect_id)
            paths = write_solar_opportunity_map(payload)
            rows.append({
                "prospect_id": prospect_id,
                "business_name": payload["prospect"]["business_name"],
                "buyer_review_id": payload["buyer_review"]["id"],
                "buyer_review_status": payload["buyer_review"]["status"],
                "priority_actions": len(payload["priority_backlog"]),
                "observed_sections": payload["search_opportunity_report"]["observed_sections"],
                "unavailable_sections": payload["search_opportunity_report"]["unavailable_sections"],
                "artifacts": paths,
                "actual_revenue": False,
            })
        except Exception as exc:
            failed.append({
                "prospect_id": prospect_id,
                "error": f"{type(exc).__name__}:{str(exc)[:300]}",
            })

    print(json.dumps({
        "schema_version": "empire.solar-opportunity-map-cycle.v1",
        "mode": "INTERNAL_MATERIALIZE",
        "requested": len(set(args.prospect_id)),
        "materialized": len(rows),
        "failed": len(failed),
        "results": rows,
        "errors": failed,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
        "execution_authority": "internal_artifact_only",
    }, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
