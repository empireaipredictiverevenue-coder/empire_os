#!/usr/bin/env python3
"""Real existing-source market graph. Optional *curated* private examples.

No network, API fees, source download, CRM reads/writes, contact metadata,
raw chat transcripts, model weight tuning or customer output publication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.flagship_market_knowledge_graph import (
    MAX_EXAMPLES, build_market_knowledge_graph, prepare_market_conversation_brief,
)

ROOT = Path("/srv/empire_os")
WORKTREE = Path(__file__).resolve().parents[1]
CURATED = WORKTREE / "runtime/knowledge_graph/approved_examples.json"


def _read_curated() -> list[dict]:
    if CURATED.is_symlink() or CURATED.parent.is_symlink() or not CURATED.is_file():
        raise ValueError("approved example ledger unavailable")
    stat = CURATED.stat()
    if not (0 < stat.st_size <= 24576 and stat.st_mode & 0o077 == 0
            and stat.st_nlink == 1):
        raise ValueError("private examples require strict custody")
    doc = json.loads(CURATED.read_text(encoding="utf-8"))
    if (not isinstance(doc, dict)
            or set(doc) != {"schema_version", "human_reviewed", "examples"}
            or doc["schema_version"] != "empire.knowledge_graph.curated_scenarios.v1"
            or doc["human_reviewed"] is not True
            or not isinstance(doc["examples"], list)
            or len(doc["examples"]) > MAX_EXAMPLES):
        raise ValueError("invalid approved scenario manifest")
    return doc["examples"]


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--market", choices=["roofing","solar","hvac","agency","b2b","law"],
                    default="roofing")
    ap.add_argument("--include-approved-private-scenarios", action="store_true",
                    help="Only already human-approved and deidentified lessons; no chat transcripts")
    options=ap.parse_args()
    if WORKTREE.name!="predictive_decision_control_20261018":
        ap.error("script must run from isolated feature owner worktree")
    now=datetime.now(timezone.utc)
    try:
        rows=_read_curated() if options.include_approved_private_scenarios else []
        graph=build_market_knowledge_graph(ROOT,as_of=now,approved_examples=rows)
        brief=prepare_market_conversation_brief(graph,niche=options.market)
    except (ValueError, OSError, TypeError):
        print(json.dumps({
            "status":"MARKET_GRAPH_SOURCE_OR_EXAMPLE_CUSTODY_HELD",
            "raw_chat_content_exported":False,
            "commercial_buyer_verified":False,
            "external_execution_authorized":False,
        }))
        return 1
    # The full graph is a private internal transient model; the CLI exposes
    # only safe operational aggregates and fixed category-level lessons.
    print(json.dumps({
        "schema_version":graph["schema_version"],
        "status":graph["status"],
        "node_count":graph["node_count"],
        "edge_count":graph["edge_count"],
        "research_sources":graph["research_sources"],
        "intelligence_data_products":graph["intelligence_data_products"],
        "public_observations_indexed":graph["public_observations_indexed"],
        "unattributed_or_invalid_observations":graph["unattributed_or_invalid_observations"],
        "community_source_diagnostic_rows":graph["community_source_diagnostic_rows"],
        "unmapped_source_diagnostic_rows":graph["unmapped_source_diagnostic_rows"],
        "approved_scenario_lessons":graph["approved_scenario_lessons"],
        "market_brief":brief,
        "unrestricted_saved_chat_import_enabled":False,
        "external_execution_authorized":False,
        "customer_result_claimed":False,
        "model_weights_updated":False,
    },indent=2,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
