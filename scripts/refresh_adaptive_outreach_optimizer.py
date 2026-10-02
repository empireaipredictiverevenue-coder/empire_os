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


def _records(dsn: str, *, lookback_days: int) -> list[dict[str, Any]]:
    try:
        import psycopg
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("psycopg required") from exc

    days = max(1, min(int(lookback_days), 365))
    query = """
    SELECT
      i.id::text AS intent_id,
      i.offer_key,
      i.status,
      i.metadata,
      (
        i.status IN ('delivered','replied')
        OR EXISTS (
          SELECT 1
          FROM public.outbound_replies proof_of_delivery
          WHERE proof_of_delivery.intent_id=i.id
        )
      ) AS delivered,
      (
        SELECT rr.classification
        FROM public.outbound_replies rr
        WHERE rr.intent_id=i.id
        ORDER BY rr.received_at DESC
        LIMIT 1
      ) AS classification
    FROM public.outbound_intents i
    WHERE i.created_at >= clock_timestamp() - (%s * interval '1 day')
    ORDER BY i.created_at ASC, i.id ASC
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(query, (days,))
            columns = [item.name for item in cur.description]
            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]


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
    rows = _records(dsn, lookback_days=lookback_days)
    payload = build_performance_snapshot(
        rows,
        generated_at=current.astimezone(timezone.utc).isoformat(),
    )
    reply_classes = Counter(
        str(row.get("classification") or "").strip().lower()
        for row in rows
        if str(row.get("classification") or "").strip()
    )
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
