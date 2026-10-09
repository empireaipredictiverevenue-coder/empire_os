#!/usr/bin/env python3
"""Compile adaptive outreach performance from canonical EmpireDB outcomes."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from empire_os.adaptive_outreach_optimizer import (
    SNAPSHOT_PATH,
    build_performance_snapshot,
)


def _records(dsn: str, *, lookback_days: int, repo_root: str | Path = "/srv/empire_os",
             as_of: datetime | None = None) -> list[dict[str, Any]]:
    from empire_os.canonical_data_gateway import CanonicalDataGateway
    from empire_os.data_backends.empiredb import EmpireDbProvider
    from empire_os.data_backends.postgres import PostgresConnectionConfig, PostgresConnector
    from empire_os.execution_bus_data_repository import ExecutionBusDataRepository

    current = as_of or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone-aware outreach snapshot required")
    provider = EmpireDbProvider(PostgresConnector(PostgresConnectionConfig(
        dsn=dsn, application_name="empire-outreach-outcome-observer")))
    with provider.read_only_snapshot() as snapshot:
        repository = ExecutionBusDataRepository(CanonicalDataGateway(snapshot))
        return repository.outreach_performance_records(lookback_days=lookback_days,
            repo_root=repo_root, as_of=current)


def refresh(
    repo_root: str | Path,
    *,
    dsn: str,
    lookback_days: int = 90,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")
    rows = _records(dsn, lookback_days=lookback_days, repo_root=root, as_of=current)
    payload = build_performance_snapshot(
        rows,
        generated_at=current.astimezone(timezone.utc).isoformat(),
    )
    reply_classes = Counter(
        str(row.get("classification") or "").strip().lower()
        for row in rows
        if str(row.get("classification") or "").strip()
    )
    payload["outcome_bridge"] = {
        "schema_version": "empire.outreach-verified-outcome-runtime-bridge.v1",
        "states": dict(Counter(row.get("outcome_bridge_state", "UNKNOWN") for row in rows)),
        "canonical_lineage": "outbound_intents -> closer_cases -> fulfilment_orders -> verified_outcome_feedback",
        "read_only": True,
        "execution_authority": "none",
    }
    payload["middle_funnel_states"] = {
        stage: dict(Counter(row.get(stage + "_state", "UNKNOWN") for row in rows))
        for stage in ("qualified_conversation", "commercial_terms")
    }
    payload["lookback_days"] = max(1, min(int(lookback_days), 365))
    payload["historical_intent_count"] = len(rows)
    payload["historical_reply_classes"] = dict(
        sorted(reply_classes.items())
    )
    payload["learning_state"] = (
        "ADAPTIVE"
        if payload.get("winner_claim_allowed")
        else "LEARNING"
    )
    payload["outbound_mutation"] = False

    target = root / SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(target)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--lookback-days", type=int, default=90)
    args = parser.parse_args()
    dsn = str(os.getenv("EMPIREDB_DSN") or "").strip()
    if not dsn:
        raise SystemExit("EMPIREDB_DSN required")
    payload = refresh(
        args.repo_root,
        dsn=dsn,
        lookback_days=args.lookback_days,
    )
    print(json.dumps({
        "generated_at": payload["generated_at"],
        "learning_state": payload["learning_state"],
        "historical_intent_count": payload["historical_intent_count"],
        "labelled_intent_count": payload["labelled_intent_count"],
        "unlabelled_history_count": payload["unlabelled_history_count"],
        "winner_claim_allowed": payload["winner_claim_allowed"],
        "historical_reply_classes": payload["historical_reply_classes"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
