#!/usr/bin/env python3
"""Feature-owner-only prospective market evidence freeze from existing sources.

Default: read-only. Explicit flag: single private write to this feature
worktree. No customer records, network, EmpireDB, model weights, marketing
claims or commercial operations.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.flagship_market_knowledge_graph import build_market_knowledge_graph
from empire_os.flagship_predictive_market_features import (
    build_point_in_time_market_features, review_market_feature_prediction_gap,
)
from empire_os.flagship_predictive_feature_custody import (
    preserve_prospective_market_features, read_local_prospective_features,
)

WORKTREE=Path(__file__).resolve().parents[1]
CANONICAL=Path("/srv/empire_os")
PRIVATE=WORKTREE/"runtime/scientific_evaluation/market_features"


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--capture-original-feature-snapshot",action="store_true",
                        help="Private one-time feature-worktree file, not production")
    args=parser.parse_args()
    if WORKTREE.name!="predictive_decision_control_20261018":
        parser.error("isolated predictive feature owner worktree required")
    now=datetime.now(timezone.utc)
    graph=build_market_knowledge_graph(CANONICAL,as_of=now)
    packet=build_point_in_time_market_features(graph,issued_at=now)
    preview=review_market_feature_prediction_gap(packet)
    receipt=preserve_prospective_market_features(
        PRIVATE,packet,apply=args.capture_original_feature_snapshot,
    )
    original_verified=False
    if receipt["status"] in (
        "PRIVATE_ORIGINAL_FEATURE_SNAPSHOT_RECORDED",
        "EXACT_PRIOR_FEATURE_REPLAY",
    ):
        original_verified = (
            read_local_prospective_features(
                PRIVATE,packet["feature_packet_sha256"]
            ) == packet
        )
    print(json.dumps({
        "schema_version":"empire.flagship_predictive_feature_operator.v1",
        "status":preview["status"],
        "mode":"OBSERVE",
        "market_count":preview["market_count"],
        "markets_with_public_research":preview["market_features_with_observed_public_topics"],
        "feature_sha256":preview["time_safe_packet_sha256"],
        "feature_local_receipt_status":receipt["status"],
        "private_file_readback_verified":original_verified,
        "production_registry_authenticated":False,
        "prospective_outcome_accuracy_verified":False,
        "forecast_issued":False,
        "model_weights_changed":False,
        "database_writes":False,
        "outbound_or_payments_executed":False,
    },sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
