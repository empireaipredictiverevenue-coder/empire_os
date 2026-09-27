"""
Empire OS Predictive Cloud.

Top-level predictive intelligence layer for Empire OS.

Responsibilities:
- build a live business-state snapshot from the current operational DB
- generate revenue, market-gap, leak, and waste intelligence
- emit durable predictive-cloud telemetry
- remain independent of the old Incus/container layout

Predictive Cloud is an intelligence capability for the Empire Brain, not a
generic worker daemon.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.predictive import (
    detect_leaks,
    detect_market_gaps,
    detect_waste,
    predict_revenue,
)


DB_PATH = os.environ.get(
    "EMPIRE_DB_PATH",
    "/srv/empire_os/empire_os.db",
)
RUNTIME_ROOT = Path(
    os.environ.get(
        "EMPIRE_RUNTIME_ROOT",
        "/srv/empire_os/runtime",
    )
)
LOG_PATH = Path(
    os.environ.get(
        "PREDICTIVE_CLOUD_LOG",
        str(RUNTIME_ROOT / "predictive" / "predictive_cloud.jsonl"),
    )
)
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
INTERVAL_SEC = int(
    os.environ.get(
        "PREDICTIVE_CLOUD_INTERVAL_SEC",
        str(6 * 3600),
    )
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_log_parent() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def log_event(level: str, event: str, **fields: Any) -> None:
    _ensure_log_parent()

    payload = {
        "ts": now_iso(),
        "level": level,
        "event": event,
        **fields,
    }

    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ts": now_iso(),
                    "level": "ERROR",
                    "event": "predictive_cloud_log_failure",
                    "error": str(exc)[:300],
                }
            ),
            flush=True,
        )

    if level in {"ERROR", "EVENT"}:
        print(json.dumps(payload, default=str), flush=True)


def _connect() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"predictive_db_missing:{DB_PATH}")

    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _count(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple = (),
) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0)


def _sum_cents(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple = (),
) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0)


def gather_state() -> dict[str, Any]:
    """
    Build the Predictive Cloud state contract from the current DB.

    This deliberately uses explicit projections rather than SELECT *.
    """
    with _connect() as conn:
        lanes = _rows(
            conn,
            """
            SELECT
                id,
                lane_number,
                category,
                category_label,
                sub_niche,
                sub_label,
                metro,
                metro_label,
                occupied_by,
                firm_slug,
                firm_tier,
                seat_price,
                seat_expires_at,
                created_at,
                updated_at
            FROM lanes
            """,
        )

        leads = _rows(
            conn,
            """
            SELECT
                id,
                lane_id,
                prospect_id,
                status,
                omega_score,
                omega_tier,
                notes,
                created_at
            FROM lane_leads
            """,
        )

        crm_leads = _rows(
            conn,
            """
            SELECT
                id,
                lead_uid,
                source,
                business_name,
                metro,
                niche,
                sub_niche,
                state,
                omega_score,
                omega_tier,
                enrichment_score,
                status,
                created_at,
                updated_at,
                icp_fit_score,
                icp_tier,
                icp_name
            FROM crm_leads
            ORDER BY created_at DESC
            LIMIT 10000
            """,
        )

        funnel_rows = _rows(
            conn,
            """
            SELECT
                prospect_id,
                from_state,
                to_state,
                actor,
                notes,
                occurred_at,
                created_at
            FROM si_funnel_event
            ORDER BY id ASC
            """,
        )

        settlement_rows = _rows(
            conn,
            """
            SELECT
                id,
                prospect_id,
                tenant_id,
                amount_cents,
                settled_at,
                settled_by
            FROM si_settlements
            ORDER BY id DESC
            LIMIT 10000
            """,
        )

        revenue_rows = _rows(
            conn,
            """
            SELECT
                snapshot_date,
                tenant_id,
                gross_cents,
                settled_cents,
                settlement_count,
                updated_at
            FROM daily_revenue_snapshots
            ORDER BY snapshot_date DESC
            LIMIT 365
            """,
        )

        lane_count = len(lanes)
        occupied_lanes = sum(
            1 for lane in lanes if lane.get("occupied_by")
        )

        leads_total = _count(
            conn,
            "SELECT COUNT(*) FROM lane_leads",
        )

        settled_cents = _sum_cents(
            conn,
            "SELECT COALESCE(SUM(amount_cents), 0) FROM si_settlements",
        )

        settlement_count = _count(
            conn,
            "SELECT COUNT(*) FROM si_settlements",
        )

    # Build current funnel state using the latest event per prospect.
    latest_funnel: dict[str, dict] = {}
    for event in funnel_rows:
        prospect_id = str(event.get("prospect_id") or "")
        if prospect_id:
            latest_funnel[prospect_id] = event

    funnel_by_state: dict[str, int] = defaultdict(int)
    for event in latest_funnel.values():
        state = str(event.get("to_state") or "").strip()
        if state:
            funnel_by_state[state] += 1

    # Add useful aggregate counts without changing the raw source records.
    leads_by_status: dict[str, int] = defaultdict(int)
    for lead in leads:
        leads_by_status[str(lead.get("status") or "unknown")] += 1

    leads_by_niche: dict[str, int] = defaultdict(int)
    for lead in crm_leads:
        niche = str(lead.get("niche") or "unknown")
        leads_by_niche[niche] += 1

    current_gross_cents = (
        int(revenue_rows[0].get("gross_cents") or 0)
        if revenue_rows
        else 0
    )
    current_settled_snapshot_cents = (
        int(revenue_rows[0].get("settled_cents") or 0)
        if revenue_rows
        else 0
    )

    return {
        "generated_at": now_iso(),
        "db_path": DB_PATH,
        "lanes": lanes,
        "lane_leads": leads,
        "crm_leads": crm_leads,
        "funnel_events": funnel_rows,
        "settlements": settlement_rows,
        "revenue_snapshots": revenue_rows,
        "lane_count": lane_count,
        "occupied_lanes": occupied_lanes,
        "leads_total": leads_total,
        "leads_by_status": dict(leads_by_status),
        "leads_by_niche": dict(leads_by_niche),
        "funnel": dict(funnel_by_state),
        "settled_cents": settled_cents,
        "settlement_count": settlement_count,
        "current_gross_cents": current_gross_cents,
        "current_settled_snapshot_cents": current_settled_snapshot_cents,
    }


def _agent_health() -> dict[str, dict]:
    """
    Best-effort health projection.

    Predictive Cloud must remain useful even when the fleet health subsystem
    is temporarily unavailable, so absence is represented rather than fatal.
    """
    return {}


def build_prediction_report(state: dict[str, Any]) -> dict[str, Any]:
    revenue = predict_revenue(
        lane_count=state["lane_count"],
        occupied_lanes=state["occupied_lanes"],
        leads_total=state["leads_total"],
        funnel_by_state=state["funnel"],
    )

    gaps = detect_market_gaps(
        state["lanes"],
        state["crm_leads"][:5000],
    )

    leaks = detect_leaks(
        state["funnel"],
    )

    waste = detect_waste(
        state["lanes"],
        agent_health=_agent_health(),
    )

    return {
        "revenue": revenue,
        "market_gaps": gaps,
        "leaks": leaks,
        "waste": waste,
    }


def cycle() -> dict[str, Any]:
    state = gather_state()
    intelligence = build_prediction_report(state)

    report = {
        "schema_version": "predictive_cloud.v2",
        "timestamp": now_iso(),
        "source": {
            "database": DB_PATH,
            "lane_count": state["lane_count"],
            "occupied_lanes": state["occupied_lanes"],
            "leads_total": state["leads_total"],
            "settlement_count": state["settlement_count"],
            "settled_cents": state["settled_cents"],
        },
        "state": {
            "funnel": state["funnel"],
            "leads_by_status": state["leads_by_status"],
            "leads_by_niche": state["leads_by_niche"],
            "current_gross_cents": state["current_gross_cents"],
            "current_settled_snapshot_cents": state["current_settled_snapshot_cents"],
        },
        "intelligence": intelligence,
    }

    log_event(
        "EVENT",
        "predictive_cloud_emitted",
        schema_version=report["schema_version"],
        lanes=state["lane_count"],
        occupied_lanes=state["occupied_lanes"],
        leads=state["leads_total"],
        settlements=state["settlement_count"],
        settled_cents=state["settled_cents"],
        predicted_mrr=intelligence["revenue"].get("total_predicted_mrr", 0),
        unrealized_mrr=intelligence["revenue"].get("unrealized_mrr", 0),
        hot_gaps=intelligence["market_gaps"]["counts"]["hot"],
        unsaturated=intelligence["market_gaps"]["counts"]["unsaturated"],
        total_leaked=intelligence["leaks"]["total_leaked"],
        waste_indicators=intelligence["waste"]["total_waste_indicators"],
    )

    # Audit post is best-effort. Predictive intelligence must not fail because
    # the Hub is temporarily unavailable.
    try:
        import requests

        requests.post(
            f"{HUB_URL}/v1/swarm/audit-log",
            json={
                "kind": "predictive_cloud",
                "ts": report["timestamp"],
                "data": report,
            },
            timeout=15,
        )
    except Exception as exc:
        log_event(
            "WARN",
            "predictive_cloud_audit_post_failed",
            error=str(exc)[:250],
        )

    return report


if __name__ == "__main__":
    print(
        f"[{now_iso()}] predictive-cloud online "
        f"db={DB_PATH} interval={INTERVAL_SEC}s",
        flush=True,
    )

    while True:
        try:
            cycle()
        except Exception as exc:
            log_event(
                "ERROR",
                "predictive_cloud_cycle_failed",
                error=str(exc)[:300],
            )
        time.sleep(INTERVAL_SEC)
