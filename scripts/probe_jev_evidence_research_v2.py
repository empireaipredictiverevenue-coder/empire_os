"""JEV / shared Empire research operator CLI.

Default is plan-only. Fixture smoke exercises the *real Python pipeline*
without DNS, network, model, database, money or external side effects.
Local JSON evidence is NOT authenticated; do not use this as production
approval or claim a real buyer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from empire_os.jev_gtm_research_bridge import (
    attach_jev_research_review,
    plan_jev_evidence_gap,
    run_jev_evidence_gap,
    run_jev_official_source_review,
)
from empire_os.jev_gtm_v2 import build_jev_gtm_decision


def _synthetic_decision() -> dict[str, Any]:
    return build_jev_gtm_decision(
        account={
            "entity_id": "synthetic:roof:1",
            "tenant_id": "synthetic:tenant:1",
            "opportunity_key": "synthetic:op:1",
            "entity_verified": False,
            "tenant_binding_verified": False,
            "business_name": "Fictional Only Ltd",
            "description": "fictional local roofing contractor",
            "target_buyer_pools": ["local_and_smb_buyers"],
            "target_product_codes": ["managed_service"],
            "first_party_people": [{"title": "owner"}],
        },
        signals=[],
        outreach={},
        as_of=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )


def execute_fixture_smoke() -> dict[str, Any]:
    decision = _synthetic_decision()
    url = "https://www.gov.uk/government/collections/public-procurement"
    calls = []

    def search(query: str, num: int) -> dict[str, Any]:
        calls.append(("search", num))
        return {"organic": [{"link": url, "title": "Synthetic official sample"}]}

    def inspect(value: str) -> dict[str, Any]:
        calls.append(("inspect", value))
        return {
            "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
            "source_url": url,
            "content_sha256": "a" * 64,
            "visible_excerpt": "Synthetic example only",
        }

    packet = run_jev_evidence_gap(
        decision,
        public_niche="roofing",
        public_market="Manchester",
        search_fn=search, inspect_fn=inspect,
        depth="speed",
    )
    attached = attach_jev_research_review(decision, packet)
    return {
        "schema_version": "empire.jev.research_operator_probe.v1",
        "status": "OFFLINE_SYNTHETIC_PIPELINE_PASSED",
        "input_authentication": "SYNTHETIC_NOT_CANONICAL",
        "network_access": False,
        "network_calls": 0,
        "db_reads": 0,
        "original_buyer_reply_verified": False,
        "actual_revenue": False,
        "calls_bounded": len(calls) <= 4,
        "research_receipt": packet,
        "decision_attachment": attached,
        "execution_authority": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JEV read-only evidence-gap research probe")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--fixture-smoke", action="store_true")
    sources.add_argument("--decision-json", type=Path)
    sources.add_argument("--official-source-smoke", action="store_true")
    parser.add_argument("--official-source-url")
    parser.add_argument("--public-niche")
    parser.add_argument("--public-market")
    parser.add_argument("--depth", choices=("speed", "balanced", "quality"), default="speed")
    parser.add_argument("--country", choices=("GB", "US", "CA", "AU", "GLOBAL"), default="GB")
    args = parser.parse_args(argv)
    if args.fixture_smoke:
        output = execute_fixture_smoke()
    elif args.official_source_smoke:
        if not args.official_source_url or not args.public_niche or not args.public_market:
            parser.error("official source URL, public niche and market required for bounded public probe")
        receipt = run_jev_official_source_review(
            _synthetic_decision(),
            public_niche=args.public_niche,
            public_market=args.public_market,
            official_source_urls=(args.official_source_url,),
            country=args.country,
        )
        output = {
            "schema_version": "empire.jev.research_operator_probe.v1",
            "status": "PUBLIC_OFFICIAL_SOURCE_SMOKE",
            "input_authentication": "SYNTHETIC_NOT_CANONICAL",
            "network_access": True,
            "search_provider_calls": 0,
            "public_primary_page_attempts": receipt["pages_considered"],
            "inspection_status": receipt["sources"][0]["inspection_status"],
            "inspected_count": receipt["inspected_source_count"],
            "content_fingerprint_present": bool(
                receipt["sources"][0].get("content_sha256")
            ),
            "buyer_intent_verified": False,
            "contact_permission_granted": False,
            "outbound_sent": False, "database_write": False,
            "actual_revenue": False, "execution_authority": "none",
        }
    else:
        if not args.public_niche or not args.public_market:
            parser.error("public-niche and public-market required for offline decision review")
        try:
            data = json.loads(args.decision_json.read_text(encoding="utf8"))
        except (OSError, ValueError) as exc:
            parser.error("offline decision file unreadable or invalid")
        plan = plan_jev_evidence_gap(
            data, public_niche=args.public_niche, public_market=args.public_market,
            depth=args.depth, country=args.country,
        )
        # Local JSON is not a trusted canonical source. This tool cannot
        # manufacture a source identity by accepting a file path as proof.
        output = {
            "schema_version": "empire.jev.research_operator_probe.v1",
            "status": "OFFLINE_UNAUTHENTICATED_PLAN_ONLY",
            "input_authentication": "LOCAL_JSON_NOT_CANONICAL",
            "plan": plan,
            "network_access": False, "database_write": False,
            "outbound_sent": False, "revenue_recognition": False,
            "execution_authority": "none",
        }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
