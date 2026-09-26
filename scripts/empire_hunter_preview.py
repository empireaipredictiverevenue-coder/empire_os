#!/usr/bin/env python3
"""Empire Hunter domain-intelligence preview/materialization CLI."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.evidence_graph import build_evidence_plan
from empire_os.hunter.materializer import SupabaseHunterMaterializer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("website")
    parser.add_argument("--entity-id", default="")
    parser.add_argument(
        "--materialize",
        action="store_true",
        help=(
            "write the evidence plan to canonical Intelligence Fabric; "
            "requires --entity-id"
        ),
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
    )
    args = parser.parse_args(argv)

    report = analyze_domain(
        args.website,
        max_pages=max(1, min(args.max_pages, 10)),
        request_timeout=max(1.0, min(args.timeout, 15.0)),
        time_budget_seconds=30.0,
    )
    result = {
        "schema_version": "empire_hunter.preview.v1",
        "mode": (
            "INTERNAL_MATERIALIZE"
            if args.materialize
            else "OBSERVE"
        ),
        "hunter": report.as_dict(),
        "outbound_actions": False,
        "payment_actions": False,
        "revenue_actions": False,
    }

    if args.entity_id:
        plan = build_evidence_plan(
            report,
            entity_id=args.entity_id,
            observed_at=datetime.now(timezone.utc),
        )
        result["materialization_plan"] = plan.as_dict()
        result["materialization"] = SupabaseHunterMaterializer().materialize(
            plan,
            write_authorized=bool(args.materialize),
        )
    elif args.materialize:
        parser.error("--materialize requires --entity-id")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
