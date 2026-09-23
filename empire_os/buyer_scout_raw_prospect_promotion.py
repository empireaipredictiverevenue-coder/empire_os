"""Governed Buyer Scout raw-prospect promotion runtime.

This module never grants standing authority. It prepares or explicitly executes
promotion for candidates that have already passed the REVIEW_READY gate. The
database RPC revalidates state and identity atomically.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


OUTPUT = Path(
    "runtime/buyer_acquisition/raw_prospect_promotion_latest.json"
)
RpcCall = Callable[[str, str, dict[str, Any]], Any]


def _eligible(
    candidates: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in candidates:
        row = dict(raw)
        if (
            row.get("review_state") == "review_ready"
            and row.get("reconciliation_state") == "REVIEW_READY"
            and str(row.get("id") or "").strip()
        ):
            rows.append(row)
    rows.sort(key=lambda row: str(row.get("id") or ""))
    return rows


def run_raw_prospect_promotion(
    candidates: Iterable[Mapping[str, Any]],
    *,
    rpc_call: RpcCall,
    execute: bool = False,
    actor: str | None = None,
) -> dict[str, Any]:
    source_rows = [dict(row) for row in candidates]
    rows = _eligible(source_rows)
    actor_name = str(actor or "").strip()

    if execute and rows and not actor_name:
        raise ValueError("actor is required for governed execution")

    results: list[dict[str, Any]] = []
    decisions: Counter[str] = Counter()

    for row in rows:
        candidate_id = str(row["id"]).strip()
        if not execute:
            result = {
                "candidate_id": candidate_id,
                "decision": "ready_for_governed_promotion",
                "database_write_performed": False,
                "canonical_promotion_performed": False,
            }
        else:
            response = rpc_call(
                "POST",
                (
                    "/rest/v1/rpc/"
                    "promote_buyer_scout_candidate_to_prospect"
                ),
                {
                    "p_candidate_id": candidate_id,
                    "p_actor": actor_name,
                },
            )
            result = (
                dict(response)
                if isinstance(response, Mapping)
                else {
                    "candidate_id": candidate_id,
                    "decision": "unexpected_rpc_response",
                    "database_write_performed": False,
                    "canonical_promotion_performed": False,
                }
            )
            result.setdefault("candidate_id", candidate_id)

        decisions[str(result.get("decision") or "unknown")] += 1
        results.append(result)

    promoted = sum(
        row.get("canonical_promotion_performed") is True
        for row in results
    )
    wrote = any(
        row.get("database_write_performed") is True
        for row in results
    )

    return {
        "schema_version": (
            "empire.buyer_scout_raw_prospect_promotion.v1"
        ),
        "mode": "GOVERNED" if execute else "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execute_requested": bool(execute),
        "candidate_count": len(source_rows),
        "eligible_review_ready_count": len(rows),
        "result_count": len(results),
        "promoted_count": promoted,
        "decision_counts": dict(sorted(decisions.items())),
        "results": results,
        "database_write_performed": wrote,
        "canonical_promotion_performed": promoted > 0,
        "buy_signal_score_policy": "UNKNOWN_NULL",
        "qualification_created": False,
        "buyer_created": False,
        "outbound_sent": False,
        "terms_accepted": False,
        "payment_action": False,
        "actual_revenue": False,
        "autonomous_execution": False,
        "standing_authority": False,
        "execution_authority": (
            "founder_governed_raw_prospect_promotion"
            if execute
            else "none"
        ),
    }


def write_raw_prospect_promotion(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
