"""
Empire OS v3 — Real-time Dashboard
===================================
FastAPI + HTMX + Chart.js dashboard mounted at /dashboard

Features:
- Funnel visualization (pending → routed → delivered → settled)
- Revenue metrics (Active MRR, Projected MRR)
- Buyer performance (leads, payout, conversion)
- Market heat map (niche × metro occupancy + demand)
- Real-time updates via HTMX polling
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from empire_os.funnel import SQLiteBackend, count_by_state, FunnelState
from empire_os.daily_revenue import DailyRevenueSnapshotter
from empire_os.predictive import predict_revenue, detect_market_gaps, detect_leaks
from empire_os.lanes import all_sub_niches

logger = logging.getLogger("dashboard_v2")

# ── Router ──────────────────────────────────────────────────────────────
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Global backend reference (set by hub on startup)
_backend: Optional[SQLiteBackend] = None


def get_backend() -> SQLiteBackend:
    if _backend is None:
        raise HTTPException(503, "Dashboard backend not initialized")
    return _backend


def set_backend(backend: SQLiteBackend) -> None:
    global _backend
    _backend = backend


# ── Data Models ─────────────────────────────────────────────────────────


class FunnelData(BaseModel):
    pending: int
    routed: int
    delivered: int
    settled: int
    total: int
    conversion_rates: dict[str, float]


class RevenueData(BaseModel):
    active_mrr: float
    projected_mrr: float
    total_predicted_mrr: float
    potential_mrr_if_full: float
    unrealized_mrr: float
    funnel_velocity: float
    confidence: float
    last_7_days: list[dict]
    last_30_days: list[dict]


class BuyerPerformance(BaseModel):
    buyer_id: str
    name: str
    tier: str
    status: str
    leads_delivered: int
    leads_pending: int
    payout_cents: int
    conversion_rate: float
    avg_lead_value: float


class MarketHeatPoint(BaseModel):
    niche: str
    metro: str
    lane_count: int
    occupied_count: int
    occupancy_rate: float
    lead_count: int
    lead_intensity: str  # hot, warm, cold, dead
    action: str


class DashboardData(BaseModel):
    funnel: FunnelData
    revenue: RevenueData
    buyers: list[BuyerPerformance]
    market_heat: list[MarketHeatPoint]
    leaks: dict
    market_gaps: dict
    timestamp: str


# ── Data Access Functions ───────────────────────────────────────────────


def get_funnel_data(backend: SQLiteBackend) -> FunnelData:
    """Get funnel counts mapped to pending→routed→delivered→settled states."""
    counts = count_by_state(backend)

    # Map funnel states to dashboard states
    # discovered → pending
    # matched/outreach_drafted/outreach_sent → routed
    # replied/claimed → delivered
    # settled/billed/collected/done → settled
    pending = counts.get("discovered", 0)
    routed = (
        counts.get("matched", 0)
        + counts.get("outreach_drafted", 0)
        + counts.get("outreach_sent", 0)
    )
    delivered = counts.get("replied", 0) + counts.get("claimed", 0)
    settled = (
        counts.get("settled", 0)
        + counts.get("billed", 0)
        + counts.get("collected", 0)
        + counts.get("done", 0)
    )
    total = pending + routed + delivered + settled

    # Calculate conversion rates between stages
    conv_rates = {}
    if pending > 0:
        conv_rates["pending_to_routed"] = round(routed / pending * 100, 1)
    if routed > 0:
        conv_rates["routed_to_delivered"] = round(delivered / routed * 100, 1)
    if delivered > 0:
        conv_rates["delivered_to_settled"] = round(settled / delivered * 100, 1)
    if total > 0:
        conv_rates["overall"] = round(settled / total * 100, 1)

    return FunnelData(
        pending=pending,
        routed=routed,
        delivered=delivered,
        settled=settled,
        total=total,
        conversion_rates=conv_rates,
    )


def get_revenue_data(backend: SQLiteBackend) -> RevenueData:
    """Get revenue metrics from predictive model + daily snapshots."""
    # Get funnel data for predictive model
    funnel_counts = count_by_state(backend)

    # Get lane data
    cursor = backend.execute(
        "SELECT COUNT(*) as total, SUM(CASE WHEN occupied_by IS NOT NULL THEN 1 ELSE 0 END) as occupied FROM lanes"
    )
    lane_row = cursor.fetchone()
    lane_count = lane_row["total"] or 0
    occupied_lanes = lane_row["occupied"] or 0

    # Get leads total
    cursor = backend.execute(
        "SELECT COUNT(*) as c FROM lane_leads WHERE (buyer_id IS NOT NULL AND buyer_id != '') OR buyer_id IS NULL"
    )
    leads_row = cursor.fetchone()
    leads_total = leads_row["c"] or 0

    # Get revenue prediction
    pred = predict_revenue(
        lane_count=lane_count,
        occupied_lanes=occupied_lanes,
        leads_total=leads_total,
        funnel_by_state=funnel_counts,
        avg_seat_price=500.0,
        conversion_rate=0.05,
    )

    # Get last 7 days revenue
    last_7_days = []
    snap = DailyRevenueSnapshotter(backend)
    for i in range(7):
        d = (datetime.now().date() - timedelta(days=i)).isoformat()
        try:
            r = snap.recompute_snapshot(d)
            last_7_days.append(
                {
                    "date": d,
                    "revenue_cents": r.gross_cents,
                    "settlements": r.settlement_count,
                }
            )
        except Exception:
            last_7_days.append({"date": d, "revenue_cents": 0, "settlements": 0})
    last_7_days.reverse()

    # Get last 30 days revenue
    last_30_days = []
    for i in range(30):
        d = (datetime.now().date() - timedelta(days=i)).isoformat()
        try:
            r = snap.recompute_snapshot(d)
            last_30_days.append(
                {
                    "date": d,
                    "revenue_cents": r.gross_cents,
                    "settlements": r.settlement_count,
                }
            )
        except Exception:
            last_30_days.append({"date": d, "revenue_cents": 0, "settlements": 0})
    last_30_days.reverse()

    return RevenueData(
        active_mrr=pred["active_seats_mrr"],
        projected_mrr=pred["projected_new_mrr"],
        total_predicted_mrr=pred["total_predicted_mrr"],
        potential_mrr_if_full=pred["potential_mrr_if_full"],
        unrealized_mrr=pred["unrealized_mrr"],
        funnel_velocity=pred["funnel_velocity"],
        confidence=pred["confidence"],
        last_7_days=last_7_days,
        last_30_days=last_30_days,
    )


def get_buyer_performance(backend: SQLiteBackend) -> list[BuyerPerformance]:
    """Get buyer performance metrics from si_buyer_outreach and lane_leads."""
    buyers = []

    # Get buyers from si_buyer_outreach
    cursor = backend.execute(
        """
        SELECT DISTINCT buyer_id, niche, status, COUNT(*) as lead_count
        FROM si_buyer_outreach
        WHERE buyer_id IS NOT NULL AND buyer_id != ''
        GROUP BY buyer_id, niche, status
        """
    )
    buyer_rows = cursor.fetchall()

    for row in buyer_rows:
        buyer_id = row["buyer_id"]
        niche = row["niche"]
        status = row["status"]
        lead_count = row["lead_count"]

        # Get delivered leads count
        cursor = backend.execute(
            "SELECT COUNT(*) as c FROM lane_leads WHERE buyer_id = ?",
            (buyer_id,),
        )
        delivered_row = cursor.fetchone()
        delivered = delivered_row["c"] or 0

        # Get pending (in outreach but not delivered)
        pending = lead_count - delivered

        # Get payout info from settlements
        cursor = backend.execute(
            """
            SELECT COALESCE(SUM(amount_cents), 0) as total_payout
            FROM si_settlements s
            JOIN si_buyer_outreach bo ON s.prospect_id = bo.buyer_id
            WHERE bo.buyer_id = ?
            """,
            (buyer_id,),
        )
        payout_row = cursor.fetchone()
        payout_cents = payout_row["total_payout"] or 0

        # Calculate conversion rate
        conversion = round(delivered / lead_count * 100, 1) if lead_count > 0 else 0.0

        # Avg lead value
        avg_value = round(payout_cents / delivered / 100, 2) if delivered > 0 else 0.0

        # Get buyer name from tenant
        cursor = backend.execute(
            "SELECT name FROM si_tenant WHERE tenant_id = ?", (buyer_id,)
        )
        tenant_row = cursor.fetchone()
        name = tenant_row["name"] if tenant_row else buyer_id

        # Get tier from subscription
        cursor = backend.execute(
            "SELECT plan FROM si_subscription WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1",
            (buyer_id,),
        )
        sub_row = cursor.fetchone()
        tier = sub_row["plan"] if sub_row else "unknown"

        buyers.append(
            BuyerPerformance(
                buyer_id=buyer_id,
                name=name,
                tier=tier,
                status=status,
                leads_delivered=delivered,
                leads_pending=pending,
                payout_cents=payout_cents,
                conversion_rate=conversion,
                avg_lead_value=avg_value,
            )
        )

    return buyers


def get_market_heat_map(backend: SQLiteBackend) -> list[MarketHeatPoint]:
    """Generate market heat map: niche × metro occupancy + lead demand."""
    heat_points = []

    # Get lane data grouped by niche + metro
    cursor = backend.execute(
        """
        SELECT sub_niche, metro,
               COUNT(*) as lane_count,
               SUM(CASE WHEN occupied_by IS NOT NULL THEN 1 ELSE 0 END) as occupied_count
        FROM lanes
        GROUP BY sub_niche, metro
        """
    )
    lane_data = cursor.fetchall()

    # Get lead counts by niche + metro from lane_leads
    cursor = backend.execute(
        """
        SELECT
            COALESCE(
                (SELECT sub_niche FROM lanes l WHERE l.id = ll.lead_ref),
                'unknown'
            ) as niche,
            COALESCE(
                (SELECT metro FROM lanes l WHERE l.id = ll.lead_ref),
                'unknown'
            ) as metro,
            COUNT(*) as lead_count
        FROM lane_leads ll
        GROUP BY niche, metro
        """
    )
    lead_data = {f"{r['niche']}:{r['metro']}": r["lead_count"] for r in cursor.fetchall()}

    for row in lane_data:
        niche = row["sub_niche"]
        metro = row["metro"]
        lane_count = row["lane_count"]
        occupied = row["occupied_count"]
        occupancy = round(occupied / lane_count * 100, 1) if lane_count > 0 else 0

        lead_count = lead_data.get(f"{niche}:{metro}", 0)

        # Determine lead intensity
        if lead_count >= 10 and occupancy >= 70:
            intensity = "hot"
            action = "raise_seat_price"
        elif lead_count >= 5 and occupancy < 50:
            intensity = "warm"
            action = "recruit_providers"
        elif lead_count < 2 and occupancy < 30:
            intensity = "dead"
            action = "kill_or_pivot"
        else:
            intensity = "cold"
            action = "monitor"

        heat_points.append(
            MarketHeatPoint(
                niche=niche,
                metro=metro,
                lane_count=lane_count,
                occupied_count=occupied,
                occupancy_rate=occupancy,
                lead_count=lead_count,
                lead_intensity=intensity,
                action=action,
            )
        )

    # Sort by lead_count desc, then occupancy desc
    heat_points.sort(key=lambda x: (-x.lead_count, -x.occupancy_rate))
    return heat_points


def get_leak_data(backend: SQLiteBackend) -> dict:
    """Get funnel leak detection."""
    funnel_counts = count_by_state(backend)
    return detect_leaks(funnel_counts)


def get_market_gaps(backend: SQLiteBackend) -> dict:
    """Get market gap detection."""
    # Get lane data
    cursor = backend.execute(
        "SELECT id, category, sub_niche, metro, occupied_by, seat_price FROM lanes"
    )
    lane_data = [dict(r) for r in cursor.fetchall()]

    # Get lead data
    cursor = backend.execute(
        "SELECT lead_ref, niche, metro FROM lane_leads"
    )
    lead_data = [dict(r) for r in cursor.fetchall()]

    return detect_market_gaps(lane_data, lead_data)


# ── API Endpoints ───────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the main dashboard HTML page."""
    template_path = Path(__file__).parent / "templates" / "dashboard" / "index.html"
    if template_path.exists():
        return HTMLResponse(template_path.read_text())
    return HTMLResponse(_get_fallback_html())


@router.get("/api/data")
async def dashboard_data(backend: SQLiteBackend = Depends(get_backend)):
    """Get all dashboard data as JSON."""
    funnel = get_funnel_data(backend)
    revenue = get_revenue_data(backend)
    buyers = get_buyer_performance(backend)
    market_heat = get_market_heat_map(backend)
    leaks = get_leak_data(backend)
    gaps = get_market_gaps(backend)

    return DashboardData(
        funnel=funnel,
        revenue=revenue,
        buyers=buyers,
        market_heat=market_heat,
        leaks=leaks,
        market_gaps=gaps,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/api/funnel")
async def funnel_endpoint(backend: SQLiteBackend = Depends(get_backend)):
    """Get funnel data for real-time updates."""
    return get_funnel_data(backend)


@router.get("/api/revenue")
async def revenue_endpoint(backend: SQLiteBackend = Depends(get_backend)):
    """Get revenue data for real-time updates."""
    return get_revenue_data(backend)


@router.get("/api/buyers")
async def buyers_endpoint(backend: SQLiteBackend = Depends(get_backend)):
    """Get buyer performance data."""
    return get_buyer_performance(backend)


@router.get("/api/heatmap")
async def market_heat_endpoint(backend: SQLiteBackend = Depends(get_backend)):
    """Get market heat map data."""
    return get_market_heat_map(backend)


@router.get("/api/leaks")
async def leaks_endpoint(backend: SQLiteBackend = Depends(get_backend)):
    """Get funnel leak data."""
    return get_leak_data(backend)


@router.get("/api/gaps")
async def market_gaps_endpoint(backend: SQLiteBackend = Depends(get_backend)):
    """Get market gap data."""
    return get_market_gaps(backend)


# ── Fallback HTML (in case template file missing) ───────────────────────


def _get_fallback_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Empire OS v3 — Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --txt:#c9d1d9; --mut:#8b949e; --grn:#3fb950; --blu:#58a6ff; --yel:#d29922; --pur:#bc8cff; --red:#f85149; }
  body { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background:var(--bg); color:var(--txt); font-size: 13px; line-height: 1.5; }
  .stat { font-size: 28px; font-weight: 700; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 10px; font-weight: 600; text-transform: uppercase; }
  .badge-pending { background: #3a2d00; color: var(--yel); }
  .badge-routed { background: #3b1f6e; color: var(--pur); }
  .badge-delivered { background: #0d419d; color: var(--blu); }
  .badge-settled { background: #06280f; color: var(--grn); }
  .badge-active { background: #06280f; color: var(--grn); }
  .badge-pending-soft { background: #3a2d00; color: var(--yel); }
  .badge-high { background: #3a0d0d; color: var(--red); }
  .badge-medium { background: #3a2d00; color: var(--yel); }
  .badge-low { background: #0d419d; color: var(--blu); }
  .badge-dead { background: #1a1a1a; color: var(--mut); }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
  .chart-container { width: 100%; height: 220px; }
  .table-container { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }
  th { color: var(--mut); font-weight: 500; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
  tr:hover { background: rgba(88, 166, 255, 0.05); }
  .section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--mut); margin-bottom: 12px; }
  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  .kpi-card { padding: 16px; }
  .kpi-label { font-size: 10px; color: var(--mut); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .kpi-value { font-size: 24px; font-weight: 700; }
  .kpi-value-green { color: var(--grn); }
  .kpi-value-blue { color: var(--blu); }
  .kpi-value-purple { color: var(--pur); }
  .kpi-value-yellow { color: var(--yel); }
  .kpi-value-red { color: var(--red); }
  .heat-cell { padding: 6px 8px; text-align: center; border: 1px solid var(--line); font-size: 11px; }
  .heat-hot { background: #3a0d0d; color: var(--red); }
  .heat-warm { background: #3a2d00; color: var(--yel); }
  .heat-cool { background: #0d419d; color: var(--blu); }
  .heat-dead { background: #1a1a1a; color: var(--mut); }
  .refresh-indicator { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--grn); margin-left: 8px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
</head>
<body class="p-6">
<div class="max-w-7xl mx-auto">
  <header class="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
    <h1 class="text-xl font-bold text-blue-400">Empire OS v3 — Real-time Dashboard</h1>
    <div class="flex items-center gap-4 text-xs text-slate-500">
      <span id="last-updated">Loading...</span>
      <span class="refresh-indicator" aria-hidden="true"></span>
      <span id="auto-refresh-status">Auto-refresh: 30s</span>
    </div>
  </header>

  <!-- Funnel Section -->
  <section class="mb-6" hx-get="/dashboard/api/funnel" hx-trigger="load, every 30s" hx-target="#funnel-content" hx-swap="innerHTML">
    <h2 class="section-title">Funnel: Pending → Routed → Delivered → Settled</h2>
    <div id="funnel-content" class="kpi-grid">
      <div class="card kpi-card"><div class="kpi-label">Pending</div><div class="kpi-value kpi-value-yellow" id="funnel-pending">—</div></div>
      <div class="card kpi-card"><div class="kpi-label">Routed</div><div class="kpi-value kpi-value-purple" id="funnel-routed">—</div></div>
      <div class="card kpi-card"><div class="kpi-label">Delivered</div><div class="kpi-value kpi-value-blue" id="funnel-delivered">—</div></div>
      <div class="card kpi-card"><div class="kpi-label">Settled</div><div class="kpi-value kpi-value-green" id="funnel-settled">—</div></div>
    </div>
    <div class="card p-4 mt-4">
      <canvas id="funnel-chart" class="chart-container"></canvas>
    </div>
    <div class="grid grid-cols-4 gap-2 mt-2 text-xs">
      <div class="card p-2 text-center">P→R: <span id="cr-pr" class="font-bold">—%</span></div>
      <div class="card p-2 text-center">R→D: <span id="cr-rd" class="font-bold">—%</span></div>
      <div class="card p-2 text-center">D→S: <span id="cr-ds" class="font-bold">—%</span></div>
      <div class="card p-2 text-center">Overall: <span id="cr-overall" class="font-bold">—%</span></div>
    </div>
  </section>

  <!-- Revenue Section -->
  <section class="mb-6" hx-get="/dashboard/api/revenue" hx-trigger="load, every 60s" hx-target="#revenue-content" hx-swap="innerHTML">
    <h2 class="section-title">Revenue: Active MRR & Projected</h2>
    <div id="revenue-content" class="kpi-grid">
      <div class="card kpi-card"><div class="kpi-label">Active MRR</div><div class="kpi-value kpi-value-green" id="rev-active">$—</div></div>
      <div class="card kpi-card"><div class="kpi-label">Projected New MRR</div><div class="kpi-value kpi-value-blue" id="rev-projected">$—</div></div>
      <div class="card kpi-card"><div class="kpi-label">Total Predicted MRR</div><div class="kpi-value kpi-value-purple" id="rev-total">$—</div></div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
      <div class="card p-4"><h3 class="text-xs text-slate-500 mb-2">Last 7 Days Revenue</h3><canvas id="rev-7d-chart" class="chart-container"></canvas></div>
      <div class="card p-4"><h3 class="text-xs text-slate-500 mb-2">Last 30 Days Revenue</h3><canvas id="rev-30d-chart" class="chart-container"></canvas></div>
    </div>
    <div class="grid grid-cols-3 gap-2 mt-2 text-xs">
      <div class="card p-2">Potential if Full: <span id="rev-potential" class="font-bold">$—</span></div>
      <div class="card p-2">Unrealized: <span id="rev-unrealized" class="font-bold">$—</span></div>
      <div class="card p-2">Velocity: <span id="rev-velocity" class="font-bold">—</span> | Confidence: <span id="rev-conf" class="font-bold">—</span></div>
    </div>
  </section>

  <!-- Buyer Performance Section -->
  <section class="mb-6" hx-get="/dashboard/api/buyers" hx-trigger="load, every 30s" hx-target="#buyers-body" hx-swap="innerHTML">
    <h2 class="section-title">Buyer Performance: Leads / Payout / Conversion</h2>
    <div class="card overflow-x-auto">
      <table>
        <thead>
          <tr>
            <th>Buyer</th><th>Tier</th><th>Status</th><th>Delivered</th><th>Pending</th>
            <th>Payout</th><th>Conv. Rate</th><th>Avg Value</th>
          </tr>
        </thead>
        <tbody id="buyers-body">
          <tr><td colspan="8" class="text-center text-slate-500 py-4">Loading buyers...</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Market Heat Map Section -->
  <section class="mb-6" hx-get="/dashboard/api/heatmap" hx-trigger="load, every 60s" hx-target="#heatmap-body" hx-swap="innerHTML">
    <h2 class="section-title">Market Heat Map: Niche × Metro (Occupancy + Demand)</h2>
    <div class="card overflow-x-auto">
      <table>
        <thead>
          <tr>
            <th>Niche</th><th>Metro</th><th>Lanes</th><th>Occupied</th><th>Occupancy</th>
            <th>Leads</th><th>Intensity</th><th>Action</th>
          </tr>
        </thead>
        <tbody id="heatmap-body">
          <tr><td colspan="8" class="text-center text-slate-500 py-4">Loading heatmap...</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Leaks & Gaps Section -->
  <section class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="card p-4" hx-get="/dashboard/api/leaks" hx-trigger="load, every 60s" hx-target="#leaks-content" hx-swap="innerHTML">
      <h3 class="text-xs text-red-400 mb-2">Funnel Leaks</h3>
      <pre id="leaks-content" class="text-xs text-slate-400">Loading...</pre>
    </div>
    <div class="card p-4" hx-get="/dashboard/api/gaps" hx-trigger="load, every 60s" hx-target="#gaps-content" hx-swap="innerHTML">
      <h3 class="text-xs text-yellow-400 mb-2">Market Gaps</h3>
      <pre id="gaps-content" class="text-xs text-slate-400">Loading...</pre>
    </div>
  </section>
</div>

<script>
// Chart instances
let funnelChart = null, rev7dChart = null, rev30dChart = null;

// Colors
const colors = {
  pending: '#d29922', routed: '#bc8cff', delivered: '#58a6ff', settled: '#3fb950',
  active: '#3fb950', projected: '#58a6ff', total: '#bc8cff'
};

// Update timestamp
function updateTimestamp() {
  document.getElementById('last-updated').textContent = 'Updated: ' + new Date().toLocaleTimeString();
}

// Render funnel chart from JSON data
function renderFunnelChart(data) {
  document.getElementById('funnel-pending').textContent = data.pending;
  document.getElementById('funnel-routed').textContent = data.routed;
  document.getElementById('funnel-delivered').textContent = data.delivered;
  document.getElementById('funnel-settled').textContent = data.settled;

  document.getElementById('cr-pr').textContent = (data.conversion_rates.pending_to_routed || 0) + '%';
  document.getElementById('cr-rd').textContent = (data.conversion_rates.routed_to_delivered || 0) + '%';
  document.getElementById('cr-ds').textContent = (data.conversion_rates.delivered_to_settled || 0) + '%';
  document.getElementById('cr-overall').textContent = (data.conversion_rates.overall || 0) + '%';

  const ctx = document.getElementById('funnel-chart');
  if (!ctx) return;
  if (funnelChart) funnelChart.destroy();
  funnelChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Pending', 'Routed', 'Delivered', 'Settled'],
      datasets: [{
        label: 'Count',
        data: [data.pending, data.routed, data.delivered, data.settled],
        backgroundColor: [colors.pending, colors.routed, colors.delivered, colors.settled],
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: '#30363d' }, ticks: { color: '#8b949e' } },
        x: { grid: { display: false }, ticks: { color: '#8b949e' } }
      }
    }
  });
}

// Render revenue charts
function renderRevenueCharts(data) {
  document.getElementById('rev-active').textContent = '$' + data.active_mrr.toLocaleString();
  document.getElementById('rev-projected').textContent = '$' + data.projected_mrr.toLocaleString();
  document.getElementById('rev-total').textContent = '$' + data.total_predicted_mrr.toLocaleString();
  document.getElementById('rev-potential').textContent = '$' + data.potential_mrr_if_full.toLocaleString();
  document.getElementById('rev-unrealized').textContent = '$' + data.unrealized_mrr.toLocaleString();
  document.getElementById('rev-velocity').textContent = (data.funnel_velocity * 100).toFixed(1) + '%';
  document.getElementById('rev-conf').textContent = (data.confidence * 100).toFixed(0) + '%';

  // 7-day chart
  const ctx7 = document.getElementById('rev-7d-chart');
  if (ctx7 && data.last_7_days) {
    const labels7 = data.last_7_days.map(d => d.date.slice(5));
    const values7 = data.last_7_days.map(d => d.revenue_cents / 100);
    if (rev7dChart) rev7dChart.destroy();
    rev7dChart = new Chart(ctx7, {
      type: 'line',
      data: { labels: labels7, datasets: [{ label: 'Revenue ($)', data: values7, borderColor: colors.active, backgroundColor: colors.active + '33', fill: true, tension: 0.3, pointRadius: 3 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#30363d' }, ticks: { color: '#8b949e' } }, x: { grid: { display: false }, ticks: { color: '#8b949e' } } } }
    });
  }

  // 30-day chart
  const ctx30 = document.getElementById('rev-30d-chart');
  if (ctx30 && data.last_30_days) {
    const labels30 = data.last_30_days.map(d => d.date.slice(5));
    const values30 = data.last_30_days.map(d => d.revenue_cents / 100);
    if (rev30dChart) rev30dChart.destroy();
    rev30dChart = new Chart(ctx30, {
      type: 'line',
      data: { labels: labels30, datasets: [{ label: 'Revenue ($)', data: values30, borderColor: colors.projected, backgroundColor: colors.projected + '33', fill: true, tension: 0.3, pointRadius: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#30363d' }, ticks: { color: '#8b949e' } }, x: { grid: { display: false }, ticks: { color: '#8b949e' } } } }
    });
  }
}

// Render buyers table
function renderBuyers(buyers) {
  const tbody = document.getElementById('buyers-body');
  if (!tbody) return;
  if (!buyers || buyers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-slate-500 py-4">No buyers</td></tr>';
    return;
  }
  tbody.innerHTML = buyers.map(b => `
    <tr class="hover:bg-slate-800/50">
      <td class="font-mono">${b.name}</td>
      <td><span class="badge badge-settled">${b.tier}</span></td>
      <td><span class="badge ${b.status==='active'?'badge-active':'badge-pending-soft'}">${b.status}</span></td>
      <td class="font-bold text-green-400">${b.leads_delivered}</td>
      <td class="text-yellow-400">${b.leads_pending}</td>
      <td>$${(b.payout_cents/100).toLocaleString()}</td>
      <td class="font-bold">${b.conversion_rate}%</td>
      <td>$${b.avg_lead_value.toFixed(2)}</td>
    </tr>
  `).join('');
}

// Render heatmap
function renderHeatmap(heat) {
  const tbody = document.getElementById('heatmap-body');
  if (!tbody) return;
  if (!heat || heat.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-slate-500 py-4">No market data</td></tr>';
    return;
  }
  const intensityClass = { hot: 'badge-high', warm: 'badge-medium', cold: 'badge-low', dead: 'badge-dead' };
  tbody.innerHTML = heat.slice(0, 50).map(h => `
    <tr class="hover:bg-slate-800/50">
      <td class="font-mono text-xs">${h.niche}</td>
      <td class="font-mono text-xs">${h.metro}</td>
      <td>${h.lane_count}</td>
      <td>${h.occupied_count}</td>
      <td class="font-bold">${h.occupancy_rate}%</td>
      <td class="font-bold ${h.lead_count > 10 ? 'text-yellow-400' : h.lead_count > 5 ? 'text-blue-400' : 'text-slate-400'}">${h.lead_count}</td>
      <td><span class="badge ${intensityClass[h.lead_intensity] || 'badge-dead'}">${h.lead_intensity.toUpperCase()}</span></td>
      <td class="text-xs">${h.action}</td>
    </tr>
  `).join('');
}

// HTMX response handlers
document.body.addEventListener('htmx:afterSwap', function(evt) {
  const target = evt.detail.target;
  if (target.id === 'funnel-content') {
    updateTimestamp();
    fetch('/dashboard/api/funnel').then(r => r.json()).then(renderFunnelChart);
  } else if (target.id === 'revenue-content') {
    fetch('/dashboard/api/revenue').then(r => r.json()).then(renderRevenueCharts);
  } else if (target.id === 'buyers-body') {
    fetch('/dashboard/api/buyers').then(r => r.json()).then(renderBuyers);
  } else if (target.id === 'heatmap-body') {
    fetch('/dashboard/api/heatmap').then(r => r.json()).then(renderHeatmap);
  }
});

// Initial data fetch
fetch('/dashboard/api/funnel').then(r => r.json()).then(renderFunnelChart);
fetch('/dashboard/api/revenue').then(r => r.json()).then(renderRevenueCharts);
fetch('/dashboard/api/buyers').then(r => r.json()).then(renderBuyers);
fetch('/dashboard/api/heatmap').then(r => r.json()).then(renderHeatmap);

// Periodic full refresh for all data
setInterval(() => {
  fetch('/dashboard/api/funnel').then(r => r.json()).then(renderFunnelChart);
  fetch('/dashboard/api/revenue').then(r => r.json()).then(renderRevenueCharts);
  fetch('/dashboard/api/buyers').then(r => r.json()).then(renderBuyers);
  fetch('/dashboard/api/heatmap').then(r => r.json()).then(renderHeatmap);
}, 30000);

</script>
</body>
</html>"""


# ── Module initialization ──────────────────────────────────────────────

def init_dashboard(backend: SQLiteBackend) -> None:
    """Initialize dashboard with backend reference."""
    set_backend(backend)
    logger.info("Dashboard v2 initialized")