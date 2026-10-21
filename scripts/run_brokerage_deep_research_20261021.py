"""Read-only original-source brokerage bot for US and UK.

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.run_brokerage_deep_research_20261021 \
 --read-only --country both --format markdown

Add --probe-public-search for two bounded Search Fabric attempts per market.
No customer send, data-resale, payment or independent editorial approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.research.brokerage_editorial_review import review_brokerage_editorial
from empire_os.research.brokerage_decision_brief import (
    build_brokerage_decision_brief, discover_held_candidates
)
from empire_os.research.brokerage_model_challenge import (
    challenge_research_brief, default_local_compute_challenge
)
from empire_os.research.brokerage_niche_profiles import NICHES, research_intake_plan

US_SAMPLE = Path(
    "/home/ubuntu/empire_worktrees/agency_acquisition_conversion_20261020/"
    "docs/integrations/agency_acquisition/original_market_samples/"
    "LINCOLN_PARK_IMPLANTS_PUBLIC_EVIDENCE_SAMPLE_20261020.md"
)


def run(*, country: str, niche: str = "dental",
        probe_public_search: bool = False,
        local_model_challenge: bool = False,
        inspect_fn=None, search_fn=None, model_fn=None) -> dict:
    if country not in ("US", "GB", "both"):
        raise ValueError("EXPLICIT_MARKET_COUNTRY_REQUIRED")
    if niche not in NICHES:
        raise ValueError("EXPLICIT_SUPPORTED_RESEARCH_NICHE_REQUIRED")
    markets = ("US", "GB") if country == "both" else (country,)
    if probe_public_search and search_fn is None:
        from empire_os.search_fabric.search import search as search_fn
    if niche != "dental":
        # No silent conversion of the dental original-source catalogue into
        # other industries. Show a useful market-specific intake and discovery
        # state, without claiming any accepted original-source evidence.
        intakes = []
        for market in markets:
            plan = research_intake_plan(niche, market)
            plan["public_search_diagnostic"] = discover_held_candidates(
                market, search_fn if probe_public_search else None, niche=niche
            )
            intakes.append(plan)
        return {
            "schema_version": "empire.brokerage.deep_research_operator.v1",
            "mode": "OBSERVE",
            "niche": niche,
            "scope": list(markets),
            "status": "HELD_NICHE_ORIGINAL_SOURCE_INTAKE_REQUIRED",
            "market_reports": [],
            "niche_intake_plans": intakes,
            "research_owner": "existing_search_and_market_intelligence",
            "editorial_signoff_verified": False,
            "genuine_buyer_or_revenue_proven": False,
            "outbound_sent": False,
            "financial_actions": False,
            "database_writes": False,
            "next_action": "REVIEW_NICHE_COUNTRY_ORIGINAL_SOURCE_AND_RIGHTS_INTAKE",
        }
    results = []
    for market in markets:
        kwargs = {"original_sample": US_SAMPLE if market == "US" else None}
        if inspect_fn is not None:
            kwargs["inspect_fn"] = inspect_fn
        evidence = review_brokerage_editorial(market, **kwargs)
        discovered = discover_held_candidates(
            market, search_fn if probe_public_search else None
        )
        brief = build_brokerage_decision_brief(
            evidence, search_diagnostic=discovered
        )
        brief["advisory_model_review"] = challenge_research_brief(
            brief,
            model_fn=(model_fn or default_local_compute_challenge)
                     if local_model_challenge else None,
        )
        results.append(brief)
    return {
        "schema_version": "empire.brokerage.deep_research_operator.v1",
        "mode": "OBSERVE",
        "niche": niche,
        "scope": list(markets),
        "status": ("ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING"
                   if all(x["status"] == "SOURCE_EVIDENCE_READY_FOR_EDITORIAL_REVIEW"
                          for x in results)
                   else "HELD_INCOMPLETE_MARKET_SOURCE_OBSERVATION"),
        "market_reports": results,
        "research_owner": "existing_search_and_market_intelligence",
        "no_unsupervised_new_source_ingestion": True,
        "source_reuse_rights_granted": False,
        "editorial_signoff_verified": False,
        "genuine_buyer_or_revenue_proven": False,
        "outbound_sent": False,
        "financial_actions": False,
        "database_writes": False,
        "next_action": "AUTHENTICATED_ORIGINAL_RESEARCH_OWNER_CLAIM_AND_RIGHTS_REVIEW",
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Empire AI — Brokerage deep research",
        "",
        "**Read-only original-source analysis · customer-use approval pending**",
        "",
        "Status: " + report["status"],
        "",
        "Niche: " + report.get("niche", "dental"),
        "",
    ]
    if report.get("niche_intake_plans"):
        for plan in report["niche_intake_plans"]:
            lines.extend([
                "## " + plan["country"] + " — source intake required", "",
                "Buyer decision: " + plan["buyer_problem_to_qualify"], "",
                "Research question: " + plan["research_question"], "",
                "Original sources admitted: **none**", "",
                "Discovery: " + plan["public_search_diagnostic"]["status"], "",
                "Risks to avoid: " + ", ".join(plan["unverified_inferences_to_avoid"]),
                "", "Next: " + plan["next_action"], "",
            ])
        lines.append("No original sources, buyer claims or external send clearance.")
        return "\n".join(lines)
    for item in report["market_reports"]:
        lines.extend([
            "## " + item["country"] + " — original source evidence",
            "",
            ("Inspected: " + str(item["original_pages_inspected"]) + "/"
             + str(item["curated_original_source_count"]) + " primary sources."),
            "",
        ])
        for row in item["evidence_ledger"]:
            title = " / ".join(row["page_headings_as_observed"][:2])
            lines.append(
                "- " + row["publisher_host"] + " — "
                + ("inspected" if row["inspected"] else "held/unavailable")
                + "; source: " + row["original_url"]
                + "; observed headings: " + (title or "unavailable")
            )
        lines += [
            "", "**Private original-page context for editorial review:**", ""
        ]
        for entry in item["evidence_ledger"]:
            anchors = entry["original_passage_anchors_for_editorial_only"]
            lines.append("- " + entry["publisher_host"] + ": "
                         + (anchors[0]["original_page_excerpt"]
                            if anchors else "no bounded source passage extracted"))
        lines += ["", "**Literal terminology observed on source pages (not clinical proof):**", ""]
        for matrix in item["source_term_comparison"]:
            lines.append("- " + matrix["publisher_host"] + ": "
                         + (", ".join(matrix["literal_source_terms"]) or
                            "no tracked literal terms found"))
        lines += ["", "**Decision questions for the Research owner:**", ""]
        lines += ["- " + q for q in item["editorial_questions"]]
        lines += [
            "", "Fresh search status: " + item["current_search_discovery"]["status"],
            "", "Evidence fingerprint: " + item["evidence_fingerprint_sha256"],
            "", "Model advisory status: " + item["advisory_model_review"]["status"],
            "", "Editorial approved: NO · Client reuse licence: NOT VERIFIED", "",
        ]
    lines += [
        "## Commercial and editorial boundaries", "",
        "Do not distribute this packet as a client deliverable.",
        "No sales pitch or payment request before genuine buyer need and scope.",
        "No buyer conversation or revenue inferred. Search results, if any,",
        "remain unadmitted candidate URLs.",
        "Existing Search/Market Intelligence owner must independently verify",
        "exact claims, attribution, rights and editorial sign-off.",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--read-only", required=True, action="store_true")
    ap.add_argument("--country", choices=("US", "GB", "both"), required=True)
    ap.add_argument("--niche", choices=tuple(NICHES), default="dental")
    ap.add_argument("--format", choices=("json", "markdown"), default="markdown")
    ap.add_argument("--probe-public-search", action="store_true")
    ap.add_argument("--local-model-challenge", action="store_true")
    args = ap.parse_args(argv)
    result = run(country=args.country, niche=args.niche,
                 probe_public_search=args.probe_public_search,
                 local_model_challenge=args.local_model_challenge)
    print(json.dumps(result, sort_keys=True, indent=2)
          if args.format == "json" else render_markdown(result))
    return 0 if result["status"] == "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
