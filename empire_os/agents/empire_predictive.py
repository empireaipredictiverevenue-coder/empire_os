#!/usr/bin/env python3
"""
empire_predictive.py — in-house predictive revenue + market-gap intelligence.

Answers the question: "where should I deploy next quarter?"

For each (metro, niche) lane:
  - lane occupancy (occupied_by set or not)
  - demand signal: how many leads sitting pending vs routed vs delivered
  - lead inflow (last 7 days)
  - delivery rate
  - buyer presence (si_buyer_outreach rows for metro + niche)
  - revenue projection:
      expected_monthly = leads_per_day * conversion_rate * seat_price * 30
      revenue = (delivered leads) * (avg payout_usd)

For each "GAP" (lane occupied-or-not, but low buyer presence):
  - suggested action: "recruit buyer for {niche}:{metro}"
  - risk: empty lanes earning nothing

For each "HOT" (high inflow + low conversion):
  - suggested action: "drop in a deliverer, capacity is being wasted"

Writes:
  /root/feedback/predictive_revenue.jsonl     (append-only JSONL)
  /root/feedback/predictive_revenue_latest.json (latest snapshot)

Cadence: empire-predictive.timer → empire-predictive.service (daily).
"""
from __future__ import annotations
import os, sys, json, sqlite3, time, logging
from datetime import datetime, timezone, timedelta

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.dirname(_THIS_DIR))

log = logging.getLogger("empire_predictive")

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
FEED = "/root/feedback"
JSONL = os.path.join(FEED, "predictive_revenue.jsonl")
LATEST = os.path.join(FEED, "predictive_revenue_latest.json")
MAX_JSONL_BYTES = 5 * 1024 * 1024

# Defaults — tune from real numbers when we have 30 days of telemetry.
AVG_PAYOUT_USD = float(os.getenv("AVG_PAYOUT_USD", "55.0"))
CONVERSION_BASELINE = float(os.getenv("CONVERSION_BASELINE", "0.035"))  # 3.5% delivered/pending
SEAT_PRICE_USD = float(os.getenv("SEAT_PRICE_USD", "3500.0"))


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lane_leads_cols() -> set[str]:
    con = _db()
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(lane_leads)").fetchall()}
    finally:
        con.close()


def _lanes_cols() -> set[str]:
    con = _db()
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(lanes)").fetchall()}
    finally:
        con.close()


def _safe_int(x):
    try:
        return int(x or 0)
    except Exception:
        return 0


def _forecast_for_corpus() -> dict:
    """Whole-corpus revenue forecast over the next 30 days.

    Uses actual delivery rate (delivered / total) × payout × projected lead
    inflow rather than a fixed baseline.
    """
    con = _db()
    try:
        cols = _lane_leads_cols()
        has_metro = "metro" in cols
        has_status = "status" in cols
        total = con.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0]
        pending = _safe_int(con.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE status IN ('pending','new')"
        ).fetchone()[0]) if has_status else 0
        delivered = _safe_int(con.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE status='delivered'"
        ).fetchone()[0]) if has_status else 0
        # Delivery rate over the lifetime of the corpus
        rate = (delivered / total) if total else CONVERSION_BASELINE
        # Inflow projection: median leads per 7-day window over the last 30 days
        inflow_per_day = 0
        if "created_at" in cols:
            seven_day_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            recent = con.execute(
                "SELECT COUNT(*) FROM lane_leads WHERE created_at > ?",
                (seven_day_cutoff,),
            ).fetchone()[0]
            inflow_per_day = recent / 7.0

        # Revenue: we book on delivery, not on creation
        #   next_30d_delivered = inflow_per_day * 30 * rate
        #   revenue = next_30d_delivered * AVG_PAYOUT
        next_30d_delivered = inflow_per_day * 30 * rate
        revenue_30d = next_30d_delivered * AVG_PAYOUT_USD

        # Seat MRR: every occupied lane is $SEAT_PRICE / month
        occupied_seats = _safe_int(con.execute(
            "SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''"
        ).fetchone()[0]) if _lanes_cols() else 0
        seat_mrr = occupied_seats * SEAT_PRICE_USD

        return {
            "total_leads": total,
            "pending": pending,
            "delivered": delivered,
            "delivery_rate_pct": round(rate * 100, 3),
            "inflow_per_day": round(inflow_per_day, 1),
            "projected_30d_delivered": round(next_30d_delivered, 0),
            "projected_30d_revenue_usd": round(revenue_30d, 2),
            "occupied_seats": occupied_seats,
            "seat_mrr_usd": round(seat_mrr, 2),
        }
    finally:
        con.close()


def _per_metro_breakdown() -> list:
    """Per-metro revenue + demand breakdown. Sorted by gap-revenue upside."""
    con = _db()
    try:
        cols = _lane_leads_cols()
        if "metro" not in cols:
            return []
        has_status = "status" in cols

        sql = """
        SELECT
            metro,
            COUNT(*) AS total,
            SUM(CASE WHEN status IN ('pending','new') OR status IS NULL THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status IN ('delivered','delivered_processed') THEN 1 ELSE 0 END) AS delivered
        FROM lane_leads
        WHERE metro IS NOT NULL AND metro != ''
        GROUP BY metro
        ORDER BY total DESC
        """
        rows = con.execute(sql).fetchall()

        result = []
        for r in rows:
            total = _safe_int(r["total"])
            pending = _safe_int(r["pending"])
            delivered = _safe_int(r["delivered"])
            rate = (delivered / total) if total else 0
            # Daily inflow in this metro: average over last 7 days, divide by 7
            if "created_at" in cols:
                seven_day_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                recent = con.execute(
                    "SELECT COUNT(*) FROM lane_leads WHERE metro=? AND created_at > ?",
                    (r["metro"], seven_day_cutoff),
                ).fetchone()[0]
                inflow_per_day = recent / 7.0
            else:
                inflow_per_day = total / 30.0
            proj_30d = inflow_per_day * 30 * max(rate, CONVERSION_BASELINE)
            revenue_30d = proj_30d * AVG_PAYOUT_USD
            result.append({
                "metro": r["metro"],
                "total_leads": total,
                "pending": pending,
                "delivered": delivered,
                "delivery_rate_pct": round(rate * 100, 3),
                "inflow_per_day": round(inflow_per_day, 1),
                "projected_30d_revenue_usd": round(revenue_30d, 2),
            })
        return result
    finally:
        con.close()


def _gap_opportunities() -> list:
    """Find metros/niches that have demand but no buyer presence.

    A "gap" = metro has >= 50 pending leads but no si_buyer_outreach rows
    for that metro+niche combo. Each gap is a recruitment opportunity.
    """
    con = _db()
    try:
        cols = _lane_leads_cols()
        if "metro" not in cols or "niche" not in cols:
            return []
        # pending leads grouped by (metro, niche)
        demand_rows = con.execute("""
            SELECT metro, niche, COUNT(*) AS pending
            FROM lane_leads
            WHERE (metro IS NOT NULL AND metro != '')
              AND (niche IS NOT NULL AND niche != '')
              AND (status IN ('pending','new') OR status IS NULL)
            GROUP BY metro, niche
            HAVING pending >= 50
            ORDER BY pending DESC
            LIMIT 50
        """).fetchall()

        # buyer presence per (metro, niche)
        buyer_rows = con.execute("""
            SELECT metro, niche, COUNT(*) AS buyers
            FROM si_buyer_outreach
            WHERE metro IS NOT NULL AND metro != ''
              AND niche IS NOT NULL AND niche != ''
              AND active = 1
            GROUP BY metro, niche
        """).fetchall()
        buyer_lookup = {(b["metro"], b["niche"]): _safe_int(b["buyers"]) for b in buyer_rows}

        gaps = []
        for d in demand_rows:
            key = (d["metro"], d["niche"])
            if buyer_lookup.get(key, 0) == 0:
                gaps.append({
                    "type": "buyer_gap",
                    "metro": d["metro"],
                    "niche": d["niche"],
                    "pending_leads": _safe_int(d["pending"]),
                    "buyers_present": 0,
                    "action": f"recruit USDC buyer for {d['metro']}/{d['niche']}",
                    "revenue_potential_usd": round(
                        _safe_int(d["pending"]) * AVG_PAYOUT_USD * 0.10, 2  # 10% close-rate assumption
                    ),
                })
        return gaps
    finally:
        con.close()


def _saturation_alerts() -> list:
    """Metros where leads are landing but delivery rate is near zero.

    A "saturation" = metro has >= 100 leads AND delivery_rate < 1%.
    Likely cause: too many leads per buyer, or no buyers. Either way,
    pause inflow or expand the buyer pool.
    """
    con = _db()
    try:
        cols = _lane_leads_cols()
        if "metro" not in cols or "status" not in cols:
            return []
        rows = con.execute("""
            SELECT metro,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status IN ('delivered','delivered_processed') THEN 1 ELSE 0 END) AS delivered
            FROM lane_leads
            WHERE metro IS NOT NULL AND metro != ''
            GROUP BY metro
            HAVING total >= 100
        """).fetchall()
        alerts = []
        for r in rows:
            total = _safe_int(r["total"])
            delivered = _safe_int(r["delivered"])
            rate = delivered / total if total else 0
            if rate < 0.01 and total >= 100:
                alerts.append({
                    "type": "saturation",
                    "metro": r["metro"],
                    "total_leads": total,
                    "delivered_leads": delivered,
                    "delivery_rate_pct": round(rate * 100, 3),
                    "action": "expand buyer pool OR pause lead inflow for this metro",
                    "revenue_lost_usd_estimate": round(total * AVG_PAYOUT_USD * rate * 30, 2),
                })
        return alerts
    finally:
        con.close()


def _buyer_coverage() -> dict:
    """Are buyers spread across the same metros as leads?

    Returns coverage stats: how many metros have zero buyers but active
    demand; what % of leads sit in metros with at least one buyer.
    """
    con = _db()
    try:
        demand_metros = [
            r["metro"]
            for r in con.execute(
                "SELECT DISTINCT metro FROM lane_leads "
                "WHERE metro IS NOT NULL AND metro != ''"
            ).fetchall()
        ]
        buyer_metros = [
            r["metro"]
            for r in con.execute(
                "SELECT DISTINCT metro FROM si_buyer_outreach "
                "WHERE metro IS NOT NULL AND metro != '' AND active = 1"
            ).fetchall()
        ]
        demand_set = set(demand_metros)
        buyer_set = set(buyer_metros)
        unmet = sorted(demand_set - buyer_set)
        return {
            "demand_metros": len(demand_set),
            "buyer_metros": len(buyer_set),
            "metros_with_active_demand_no_buyer": unmet,
            "coverage_pct": (
                round(len(demand_set & buyer_set) / len(demand_set) * 100, 1)
                if demand_set else 0.0
            ),
        }
    finally:
        con.close()


def _build_competitor_snapshot() -> dict:
    """For each lead source, count what fraction of inserts mention competing
    firms (rough heuristic: same source produced leads in same metro).

    Empire OS is the buyer itself. So competitor intel = who else has
    capacity buying leads in each metro. We approximate from
    si_buyer_outreach.business_name cluster.
    """
    con = _db()
    try:
        # Top "buyers" (business names) per metro. These are the actual
        # competitors for our supply — the firms we'd be competing with
        # to sell leads to in each metro.
        rows = con.execute("""
            SELECT metro, business_name, COUNT(*) AS c
            FROM si_buyer_outreach
            WHERE metro IS NOT NULL AND metro != ''
              AND business_name IS NOT NULL AND business_name != ''
            GROUP BY metro, business_name
            ORDER BY metro, c DESC
        """).fetchall()
        # Group by metro: top 3 buyers per metro
        by_metro = {}
        for r in rows:
            by_metro.setdefault(r["metro"], []).append({
                "business": r["business_name"][:60],
                "touchpoints": _safe_int(r["c"]),
            })
        # Trim to top 3 per metro
        return {m: arr[:3] for m, arr in by_metro.items()}
    finally:
        con.close()


def main() -> dict:
    t0 = time.time()
    snap = {
        "ts": _now(),
        "schema_drift_safe": True,
    }
    try:
        snap["forecast_30d"] = _forecast_for_corpus()
        snap["per_metro"] = _per_metro_breakdown()
        snap["buyer_coverage"] = _buyer_coverage()
        snap["gap_opportunities"] = _gap_opportunities()
        snap["saturation_alerts"] = _saturation_alerts()
        snap["competitor_snapshot"] = _build_competitor_snapshot()
        snap["top_5_market_gaps"] = sorted(
            snap["gap_opportunities"], key=lambda g: -g["revenue_potential_usd"]
        )[:5]
        snap["duration_ms"] = round((time.time() - t0) * 1000)
    except Exception as e:
        log.exception("predictive failed")
        snap["error"] = str(e)[:300]

    # Append JSONL with rotation
    os.makedirs(FEED, exist_ok=True)
    if os.path.exists(JSONL) and os.path.getsize(JSONL) > MAX_JSONL_BYTES:
        try:
            os.rename(JSONL, JSONL + ".1")
        except OSError:
            pass
    with open(JSONL, "a") as f:
        f.write(json.dumps(snap, default=str) + "\n")
    with open(LATEST, "w") as f:
        json.dump(snap, f, indent=2, default=str)

    print(json.dumps({
        "ts": snap["ts"],
        "duration_ms": snap["duration_ms"],
        "forecast_30d": snap.get("forecast_30d"),
        "buyer_coverage": snap.get("buyer_coverage"),
        "top_3_gaps": [
            (g["metro"], g["niche"], g["revenue_potential_usd"])
            for g in snap.get("top_5_market_gaps", [])[:3]
        ],
        "saturation_alerts_count": len(snap.get("saturation_alerts", [])),
    }, indent=2, default=str))
    return snap


if __name__ == "__main__":
    main()
