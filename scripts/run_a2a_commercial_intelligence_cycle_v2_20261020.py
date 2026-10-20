#!/usr/bin/env python3
"""One complete local A2A research cycle over existing real EmpireOS snapshots.

Creates only files inside this research worktree. Never touches source files,
network, Meta, CRM, payments, buyer emails or campaigns. No daemon.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from empire_os.a2a_commercial_signal_miner import mine_signals, agent_card
from empire_os.a2a_data_campaign_experiments import build_data_campaign_experiments
from empire_os.a2a_data_campaign_release_review import assess_campaign_readiness
from empire_os.a2a_data_opportunity_workflow import plan_handoffs
from empire_os.a2a_nyc_commercial_evidence_gate import inspect_nyc_pilot
from empire_os.a2a_signal_decision_intelligence_v2 import make_decision_intelligence
from empire_os.a2a_opportunity_graph_v2 import make_opportunity_graph
from empire_os.a2a_evidence_history_v2 import merge_evidence_history
from empire_os.a2a_founder_targeting_cycle_v1 import build_prompted_research
from empire_os.a2a_target_owner_handoff_v1 import make_owner_research_handoffs, make_handoff_source_hold
from empire_os.a2a_owner_research_protocol_v1 import make_owner_pickup_packets
from empire_os.a2a_owner_receipt_intake_v1 import inspect_owner_receipt_files
from empire_os.a2a_owner_pickup_change_tracking_v1 import review_pickup_changes
from empire_os.a2a_b2b_evidence_mining_v1 import mine_targeted_business_evidence, make_mining_source_hold
from empire_os.a2a_b2b_mining_history_v1 import update_mining_history

BASE = Path("/srv/empire_os/runtime")
LOCAL = Path(__file__).resolve().parents[1] / "runtime" / "a2a_commercial_signal_mining"

SOURCES = {
    "community": BASE / "community_intent/latest.json",
    "gps": BASE / "market_sweeps/revenue_gps_latest.json",
    "catalogue": BASE / "data_brokerage/internal_product_catalog_latest.json",
    "nyc": BASE / "data_brokerage/nyc_dobnow_property_three_agency_latest.json",
    "provenance": BASE / "data_brokerage/nyc_dobnow_property_three_agency_latest.provenance.json",
}

def _read(p: Path, *, max_size: int = 1_000_000) -> tuple[dict, bytes]:
    if p.is_symlink() or not p.is_file() or p.stat().st_size > max_size:
        raise ValueError("MISSING_OR_UNSAFE_READONLY_SOURCE:" + p.name)
    raw = p.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("SOURCE_ROOT_NOT_OBJECT")
    return data, raw

def _write(name: str, content: dict) -> None:
    if LOCAL.is_symlink():
        raise ValueError("UNSAFE_OUTPUT_DIRECTORY")
    LOCAL.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = LOCAL / name
    if dest.is_symlink() or (dest.exists() and not dest.is_file()):
        raise ValueError("UNSAFE_OUTPUT_FILE")
    fd, path = tempfile.mkstemp(prefix=".a2a_decision_", dir=LOCAL)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as f:
            json.dump(content, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        os.replace(path, dest)
    finally:
        if os.path.exists(path):
            os.unlink(path)

def run(*, previous: dict | None = None, history: dict | None = None,
        previous_owner_pickup: dict | None = None,
        previous_mining_history: dict | None = None) -> dict:
    payload = {name: _read(path) for name, path in SOURCES.items()}
    current = mine_signals(
        community=payload["community"][0], revenue_gps=payload["gps"][0],
    )
    prompt_config = _read(Path(__file__).resolve().parents[1] /
                          "config/a2a_candidates/founder_targeting_prompts_v1.json")[0]
    targeting = build_prompted_research(prompt_config, payload["community"][0])
    buyer_scout_snapshot = None
    try:
        buyer_scout_snapshot = _read(BASE / "buyer_acquisition/scout_latest.json")[0]
    except (OSError, ValueError, json.JSONDecodeError):
        owner_handoffs = make_handoff_source_hold(
            reason="BUYER_SCOUT_SOURCE_UNAVAILABLE",
            profile_count=targeting["profile_count"],
        )
    else:
        try:
            owner_handoffs = make_owner_research_handoffs(targeting, buyer_scout_snapshot)
        except ValueError:
            owner_handoffs = make_handoff_source_hold(
                reason="BUYER_SCOUT_SOURCE_UNTRUSTED",
                profile_count=targeting["profile_count"],
            )
    owner_pickup = make_owner_pickup_packets(owner_handoffs)
    # Mine existing real, owner-issued public research evidence without another
    # crawler, new paid API calls or changing Buyer Scout's own candidate state.
    if owner_handoffs.get("source_state") is not None or buyer_scout_snapshot is None:
        mining = make_mining_source_hold(
            targeting, reason="CANONICAL_MINING_INPUT_UNAVAILABLE")
    else:
        try:
            public_research_seeds = _read(BASE / "buyer_acquisition/public_research_seeds.json")[0]
            mining = mine_targeted_business_evidence(
                targeting, owner_pickup, public_research_seeds,
                buyer_scout_snapshot, payload["nyc"][0],
            )
        except (OSError, ValueError, json.JSONDecodeError):
            mining = make_mining_source_hold(
                targeting, reason="CANONICAL_MINING_INPUT_UNTRUSTED")
    mining_history = update_mining_history(mining, previous_mining_history)
    receipt_review = inspect_owner_receipt_files(
        owner_pickup, LOCAL / "owner_signed_receipts",
    )
    pickup_delta = review_pickup_changes(owner_pickup, previous_owner_pickup)
    campaigns = build_data_campaign_experiments(current)
    nyc = inspect_nyc_pilot(
        report=payload["nyc"][0],
        report_sha256=hashlib.sha256(payload["nyc"][1]).hexdigest(),
        provenance=payload["provenance"][0],
        catalogue=payload["catalogue"][0],
        revenue_gps=payload["gps"][0],
    )
    releases = assess_campaign_readiness(campaigns, nyc)
    intelligence = make_decision_intelligence(
        current, releases, payload["catalogue"][0], previous=previous,
    )
    evidence_history = merge_evidence_history(
        history, source_hashes={k: hashlib.sha256(v[1]).hexdigest()
                                for k, v in payload.items()}, decision=intelligence,
    )
    return {
        "intel": intelligence, "graph": make_opportunity_graph(intelligence, releases),
        "history": evidence_history,
        "targeting": targeting,
        "buyer_owner_handoffs": owner_handoffs,
        "owner_pickup": owner_pickup,
        "owner_receipt_review": receipt_review,
        "pickup_change_tracking": pickup_delta,
        "data_mining": mining,
        "mining_history": mining_history,
        "signal": current, "campaign": campaigns,
        "nyc": nyc, "release": releases, "handoff": plan_handoffs(campaigns),
        "card": agent_card(),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Empire A2A commercial intelligence v2 (read-only)")
    parser.add_argument("--write-local", action="store_true",
                        help="Save worktree-local research JSON; never touches production files")
    args = parser.parse_args()
    previous_path = LOCAL / "latest.json"
    previous = None
    if previous_path.is_file() and not previous_path.is_symlink():
        previous = _read(previous_path)[0]
    history_path = LOCAL / "evidence_history_v2.json"
    history = _read(history_path)[0] if history_path.is_file() and not history_path.is_symlink() else None
    prior_pickup_path = LOCAL / "owner_research_pickup_v1.json"
    prior_pickup = (_read(prior_pickup_path)[0] if prior_pickup_path.is_file()
                    and not prior_pickup_path.is_symlink() else None)
    mining_history_path = LOCAL / "targeted_business_mining_history_v1.json"
    prior_mining_history = (_read(mining_history_path)[0]
                            if mining_history_path.is_file()
                            and not mining_history_path.is_symlink() else None)
    outcome = run(previous=previous, history=history,
                  previous_owner_pickup=prior_pickup,
                  previous_mining_history=prior_mining_history)
    if args.write_local:
        for filename, key in (
            ("latest.json", "signal"),
            ("decision_intelligence_v2.json", "intel"),
            ("opportunity_evidence_graph_v2.json", "graph"),
            ("evidence_history_v2.json", "history"),
            ("founder_prompted_targeting_v1.json", "targeting"),
            ("buyer_owner_research_handoffs_v1.json", "buyer_owner_handoffs"),
            ("owner_research_pickup_v1.json", "owner_pickup"),
            ("owner_signed_receipts_review_v1.json", "owner_receipt_review"),
            ("owner_pickup_change_tracking_v1.json", "pickup_change_tracking"),
            ("targeted_business_evidence_mining_v1.json", "data_mining"),
            ("targeted_business_mining_history_v1.json", "mining_history"),
            ("data_campaign_experiments.json", "campaign"),
            ("nyc_commercial_preflight.json", "nyc"),
            ("data_campaign_release_review.json", "release"),
            ("a2a_handoff_plans.json", "handoff"),
            ("agent_card.json", "card"),
        ):
            _write(filename, outcome[key])
    x = outcome["intel"]
    print(json.dumps({
        "schema_version": x["schema_version"],
        "agent_id": x["agent_id"],
        "research_candidates": x["research_candidate_count"],
        "new_candidates": x["new_candidate_count"],
        "repeated_candidates": x["repeated_candidate_count"],
        "research_tasks": x["verification_task_count"],
        "new_owner_task_proposals": x["new_owner_task_proposals"],
        "duplicate_owner_tasks_suppressed": x["duplicate_owner_task_reissues_suppressed"],
        "knowledge_graph_nodes": outcome["graph"]["node_count"],
        "knowledge_graph_edges": outcome["graph"]["edge_count"],
        "history_source_snapshots": outcome["history"]["source_snapshots_recorded"],
        "founder_target_profiles": outcome["targeting"]["profile_count"],
        "target_profiles_with_public_research_venues": outcome["targeting"]["targets_with_public_sources"],
        "prepared_buyer_owner_research_tickets": outcome["buyer_owner_handoffs"]["prepared_handoff_ticket_count"],
        "actual_owner_tasks_dispatched": outcome["buyer_owner_handoffs"]["tasks_dispatched"],
        "owner_pickup_requests": outcome["owner_pickup"]["pickup_count"],
        "mined_research_records": (outcome["data_mining"]["total_target_research_records_before_cross_target_dedupe"]
                                   if outcome["data_mining"] is not None else None),
        "fresh_web_searches_by_miner": 0,
        "mining_source_history_snapshots": outcome["mining_history"]["snapshot_count"],
        "new_mining_source_snapshot": outcome["mining_history"]["new_snapshot_appended"],
        "authenticated_owner_reply_count": outcome["owner_receipt_review"]["authenticated_owner_replies"],
        "owner_trust_state": outcome["owner_receipt_review"]["trust_store_state"],
        "new_owner_pickup_requests": outcome["pickup_change_tracking"]["new_request_count"],
        "unchanged_owner_pickups_not_reissued": outcome["pickup_change_tracking"]["unchanged_request_count"],
        "new_source_snapshots_this_run": outcome["history"]["new_source_snapshot_recorded_this_run"],
        "source_health": x["source_health"],
        "catalogue_stale": x["catalogue_stale"],
        "verified_buyers": x["verified_new_buyers"],
        "campaigns_reviewed": outcome["release"]["reviewed_campaign_count"],
        "campaigns_authorized": outcome["release"]["launch_ready_campaign_count"],
        "leading_markets": [
            {
                "niche": r["niche"], "metro": r["metro"],
                "priority_not_probability": r["prioritisation_score_not_probability"],
                "temporal_status": r["temporal_status"],
                "next_verification": r["next_best_verification_steps"][0]["action"]
            }
            for r in x["research_priorities"][:5]
        ],
        "execution_authority": "NONE",
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
