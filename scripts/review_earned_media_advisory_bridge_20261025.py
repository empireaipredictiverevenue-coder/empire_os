#!/usr/bin/env python3
"""Founder review of existing PR, editorial, consultancy and proposal evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.earned_media_advisory_bridge import review



def _compact_founder_summary(packet: dict) -> dict:
    """Keep an inspectable operator brief distinct from the full evidence packet."""
    lead = packet.get("lead_generation")
    lanes = packet.get("lane_counts", {})
    counts = lead.get("counts", {}) if isinstance(lead, dict) else {}
    opportunities = lead.get("opportunities", []) if isinstance(lead, dict) else []
    top = [
        {
            "opportunity_id": x["opportunity_id"],
            "label": x["label"],
            "stage": x["lead_stage"],
            "review_priority_not_buy_probability": x["priority_score"],
            "next_action": x["next_action"],
            "provenance": x.get("source_document"),
            "first_party_offer_hypothesis": x.get("recommended_offer_code"),
            "outreach_authorized": False,
            "sample_preview_available": True,
        }
        for x in opportunities[:5] if isinstance(x, dict)
    ]
    return {
        "schema_version": "empire.earned_media.founder_summary.v1",
        "mode": "OBSERVE",
        "bridge_state": packet.get("status"),
        "leadgen_state": lead.get("status") if isinstance(lead, dict) else "NOT_REQUESTED",
        "source_health_held": sorted(
            k for k, v in packet.get("sources", {}).items()
            if isinstance(v, dict) and str(v.get("state", "")).startswith("HELD")
        ),
        "lanes": lanes,
        "lead_counts": counts,
        "top_review_actions": top,
        "pr_sent_not_reply_verified": sum(
            x.get("lane") == "pr" and
            x.get("state") == "SENT_PROVIDER_RECEIPT_REPLY_UNVERIFIED"
            for x in packet.get("items", [])
        ),
        "qualified_buyers_verified": counts.get("qualified_buyer", 0),
        "forecast_verified": False,
        "revenue_verified": False,
        "outbound_authorized": False,
        "empiredb_writes": False,
        "founder_decision": (
            "VERIFY_ONE_FRESH_BUYER_PROBLEM_AND_SOURCE_BEFORE_OUTREACH"
            if counts.get("total", 0) else "REVIEW_HELD_SOURCE_EVIDENCE"
        ),
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-only", action="store_true", required=True)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pr-root", type=Path,
                        help="Explicit path to existing PR/consultancy branch/worktree")
    parser.add_argument("--distribution-root", type=Path,
                        help="Explicit path to canonical existing Revenue Distribution snapshot")
    parser.add_argument("--with-leadgen", action="store_true",
                        help="Add bounded original B2B demand and research account priority review")
    parser.add_argument("--summary", action="store_true",
                        help="Print compact executive review instead of the full source packet")
    parser.add_argument("--sample-opportunity-id", type=str,
                        help="Print original read-only sample for an exact opportunity ID")
    args = parser.parse_args(argv)
    if args.summary and args.sample_opportunity_id:
        parser.error("--summary cannot be combined with --sample-opportunity-id")
    if args.sample_opportunity_id and not args.with_leadgen:
        parser.error("--sample-opportunity-id requires --with-leadgen")
    packet = review(args.repo_root, pr_root=args.pr_root,
                    distribution_root=args.distribution_root)
    if args.with_leadgen:
        from empire_os.earned_media_leadgen_review import review_lead_generation
        packet["lead_generation"] = review_lead_generation(
            packet, repo_root=args.repo_root,
            distribution_root=args.distribution_root or args.repo_root,
        )
    held = (packet["status"].endswith("SOURCE_GAPS")
            or (args.with_leadgen
                and packet["lead_generation"]["status"] == "HELD_SOURCE_OR_PACKET_INTEGRITY"))
    if args.sample_opportunity_id:
        from empire_os.earned_media_value_first import preview_value_first_sample
        if held:
            print(json.dumps({"status": "HELD_UNVERIFIED_SOURCE", "execution_authority": "none"}))
            return 2
        try:
            result = preview_value_first_sample(
                packet["lead_generation"], opportunity_id=args.sample_opportunity_id
            )
        except (ValueError, LookupError):
            print(json.dumps({"status": "HELD_SAMPLE_NOT_VALID", "execution_authority": "none"}))
            return 2
    else:
        result = _compact_founder_summary(packet) if args.summary else packet
    print(json.dumps(result, sort_keys=True))
    return 2 if held else 0


if __name__ == "__main__":
    raise SystemExit(main())
