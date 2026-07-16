"""Dashboard — web UI served from the hub for funnel viz & AGI activity.

Adds:
- /dashboard — interactive HTML/SVG dashboard
- /v1/dashboard/data — JSON data endpoint
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from empire_os.funnel import (
    SQLiteBackend, FunnelState, count_by_state, list_states,
)
from empire_os.ceo import build_brief
from empire_os.daily_revenue import DailyRevenueSnapshotter

logger = logging.getLogger("dashboard")

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Empire OS v3 — Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }
  h1 { color: #58a6ff; font-size: 1.5rem; margin-bottom: 0.5rem; }
  .subtitle { color: #8b949e; font-size: 0.9rem; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem; }
  .card h2 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 0.75rem; }
  .stat { font-size: 2rem; font-weight: 700; }
  .stat.green { color: #3fb950; }
  .stat.blue { color: #58a6ff; }
  .stat.yellow { color: #d29922; }
  .stat.purple { color: #bc8cff; }
  .stat.red { color: #f85149; }
  .funnel-bar { display: flex; align-items: center; margin: 0.35rem 0; }
  .funnel-label { width: 130px; font-size: 0.8rem; color: #8b949e; }
  .funnel-count { width: 40px; text-align: right; font-weight: 600; margin-right: 0.5rem; }
  .funnel-fill { height: 20px; border-radius: 4px; min-width: 4px; transition: width 0.5s; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { text-align: left; color: #8b949e; font-weight: 500; padding: 0.5rem 0.5rem; border-bottom: 1px solid #30363d; }
  td { padding: 0.5rem; border-bottom: 1px solid #21262d; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge.discovered { background: #0d419d; color: #58a6ff; }
  .badge.matched { background: #3b1f6e; color: #bc8cff; }
  .badge.drafted { background: #1a5e2e; color: #3fb950; }
  .badge.sent { background: #5a3e00; color: #d29922; }
  .badge.replied { background: #0d419d; color: #58a6ff; }
  .badge.claimed { background: #5a2e00; color: #f0883e; }
  .badge.settled { background: #1a5e2e; color: #3fb950; }
  .refresh { text-align: right; font-size: 0.8rem; color: #484f58; margin-top: 0.5rem; }
  .error { color: #f85149; background: #2d1215; border: 1px solid #f85149; padding: 1rem; border-radius: 8px; }
  .loading { color: #8b949e; text-align: center; padding: 3rem; }
  .decision { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; border-bottom: 1px solid #21262d; }
  .decision-priority { background: #f85149; color: #fff; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
  .decision-priority.p2 { background: #d29922; }
  .decision-priority.p3 { background: #6e7681; }
  .decision-target { color: #58a6ff; font-family: monospace; font-size: 0.85rem; flex: 1; }
  .decision-summary { color: #c9d1d9; font-size: 0.85rem; flex: 2; }
  .btn { padding: 0.3rem 0.6rem; border: none; border-radius: 4px; font-size: 0.8rem; cursor: pointer; font-weight: 600; }
  .btn-approve { background: #1a5e2e; color: #3fb950; }
  .btn-deny { background: #5a1215; color: #f85149; }
  .btn:hover { filter: brightness(1.2); }
  .agi-row { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #21262d; }
  .agi-name { color: #bc8cff; font-weight: 600; }
  .agi-cycle-num { color: #58a6ff; font-weight: 700; }
</style>
</head>
<body>
<h1>Empire OS v3</h1>
<p class="subtitle" id="subtitle">Loading dashboard data...</p>

<div class="grid" id="stats-grid">
  <div class="card"><h2>Total Prospects</h2><div class="stat blue" id="total-prospects">—</div></div>
  <div class="card"><h2>Discovered</h2><div class="stat yellow" id="stat-discovered">—</div></div>
  <div class="card"><h2>Matched</h2><div class="stat purple" id="stat-matched">—</div></div>
  <div class="card"><h2>Revenue</h2><div class="stat green" id="stat-revenue">—</div></div>
  <div class="card"><h2>AGI Cycle</h2><div class="stat blue" id="stat-cycle">—</div></div>
  <div class="card"><h2>Settlements</h2><div class="stat green" id="stat-settlements">—</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Funnel</h2>
    <div id="funnel-bars"></div>
  </div>
  <div class="card">
    <h2>AGI Agents</h2>
    <div id="agi-list"><div class="loading">Loading...</div></div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Recent Activity</h2>
    <div id="activity-list"><div class="loading">Loading...</div></div>
  </div>
  <div class="card">
    <h2>Decision Queue <button class="btn btn-approve" onclick="tickAllAgents()" style="float:right;margin-top:-0.3rem">▶ Run All</button></h2>
    <div id="decision-queue"><div class="loading">Loading...</div></div>
  </div>
</div>

<div class="card">
  <h2>All Prospects</h2>
  <div id="prospects-table"><div class="loading">Loading...</div></div>
</div>

<p class="refresh" id="refresh-note">Auto-refreshes every 30s</p>

<script>
async function loadDashboard() {
  try {
    const resp = await fetch('/v1/dashboard/data');
    const d = await resp.json();
    document.getElementById('subtitle').textContent =
      d.timestamp + ' · ' + d.engine + ' v' + d.version;

    document.getElementById('total-prospects').textContent = d.funnel_total;
    document.getElementById('stat-discovered').textContent = d.funnel.discovered;
    document.getElementById('stat-matched').textContent = d.funnel.matched;
    document.getElementById('stat-revenue').textContent = '$' + (d.revenue_cents / 100).toFixed(2);
    document.getElementById('stat-cycle').textContent = d.agi_cycle;
    document.getElementById('stat-settlements').textContent = d.settlements;

    // Funnel bars
    const funnelHtml = Object.entries(d.funnel).map(([state, count]) => {
      const maxCtx = d.funnel_total || 1;
      const pct = Math.round((count / maxCtx) * 100);
      const colors = {discovered: '#58a6ff', matched: '#bc8cff', outreach_drafted: '#3fb950', outreach_sent: '#d29922', replied: '#58a6ff', claimed: '#f0883e', settled: '#3fb950'};
      const labels = {discovered: 'Discovered', matched: 'Matched', outreach_drafted: 'Drafted', outreach_sent: 'Sent', replied: 'Replied', claimed: 'Claimed', settled: 'Settled'};
      return `<div class="funnel-bar">
        <span class="funnel-label">${labels[state] || state}</span>
        <span class="funnel-count">${count}</span>
        <div class="funnel-fill" style="width:${Math.max(pct, 2)}%;background:${colors[state] || '#30363d'}"></div>
      </div>`;
    }).join('');
    document.getElementById('funnel-bars').innerHTML = funnelHtml;

    // Recent activity
    const actHtml = (d.recent_activity || []).map(a =>
      `<div style="margin:0.25rem 0;font-size:0.85rem">
        <span style="color:#8b949e">${a.time}</span>
        <span class="badge ${a.state}">${a.state}</span>
        <span>${a.prospect_id}</span>
        ${a.notes ? `<span style="color:#8b949e">— ${a.notes.slice(0,60)}</span>` : ''}
      </div>`
    ).join('') || '<div style="color:#8b949e">No recent activity</div>';
    document.getElementById('activity-list').innerHTML = actHtml;

    // Prospects table
        const rows = (d.prospects || []).map(p =>
          `<tr>
            <td><span class="badge ${p.state}">${p.state}</span></td>
            <td>${p.prospect_id}</td>
            <td>${p.actor}</td>
            <td style="color:#8b949e">${p.time_ago || p.occurred_at}</td>
          </tr>`
        ).join('');
        document.getElementById('prospects-table').innerHTML =
          `<table><thead><tr><th>State</th><th>Prospect</th><th>Actor</th><th>When</th></tr></thead>
           <tbody>${rows}</tbody></table>`;

        // AGI agents panel
        const agents = [
          {name: 'agi-scout', endpoint: '/v1/agi/scout/state'},
          {name: 'agi-marketing', endpoint: '/v1/agi/marketing/state'},
          {name: 'agi-sales', endpoint: '/v1/agi/sales/state'},
          {name: 'agi-closer', endpoint: '/v1/agi/closer/state'},
        ];
        try {
          const states = await Promise.all(agents.map(async a => {
            try {
              const r = await fetch(a.endpoint);
              if (!r.ok) return {name: a.name, cycle: '—', error: true};
              const s = await r.json();
              return {name: a.name, cycle: s.cycle ?? '—'};
            } catch (e) { return {name: a.name, cycle: '—', error: true}; }
          }));
          const agiHtml = states.map(s =>
            `<div class="agi-row">
              <span class="agi-name">${s.name}</span>
              <span class="agi-cycle-num">cycle ${s.cycle}</span>
             </div>`
          ).join('');
          document.getElementById('agi-list').innerHTML = agiHtml || '<div style="color:#8b949e">No agents</div>';
        } catch (e) {
          document.getElementById('agi-list').innerHTML = '<div style="color:#f85149">Failed to load</div>';
        }

        // Decision queue
        try {
          const decResp = await fetch('/v1/decisions');
          const decData = await decResp.json();
          const decisions = decData.decisions || [];
          const decHtml = decisions.length === 0
            ? '<div style="color:#3fb950;padding:0.5rem">✓ Queue empty — all caught up</div>'
            : decisions.map(dec => `
              <div class="decision">
                <span class="decision-priority p${dec.priority}">P${dec.priority}</span>
                <span class="badge ${dec.target_id === 'overview' ? 'sent' : 'matched'}">${dec.kind.replace('_',' ')}</span>
                <span class="decision-target">${dec.target_id}</span>
                <span class="decision-summary">${dec.summary}</span>
                ${dec.target_id !== 'overview' ? `
                  <button class="btn btn-approve" onclick="decide('${dec.target_id}','approve')">Approve</button>
                  <button class="btn btn-deny" onclick="decide('${dec.target_id}','deny')">Deny</button>
                ` : ''}
              </div>
            `).join('');
          document.getElementById('decision-queue').innerHTML = decHtml;
        } catch (e) {
          document.getElementById('decision-queue').innerHTML = '<div style="color:#f85149">Failed to load</div>';
        }
      } catch(e) {
        document.getElementById('subtitle').textContent = 'Dashboard error';
        document.querySelectorAll('.stat').forEach(el => el.textContent = 'ERR');
      }
    }

    async function decide(prospectId, action) {
      if (!confirm(`${action.toUpperCase()} ${prospectId}?`)) return;
      try {
        const r = await fetch(`/v1/decisions/${encodeURIComponent(prospectId)}/${action}`, {method: 'POST'});
        const data = await r.json();
        alert(data.summary || data.error || 'Done');
        loadDashboard();
      } catch (e) {
        alert('Failed: ' + e);
      }
    }

    async function tickAllAgents() {
      if (!confirm('Tick all AGI agents? This calls LLM and may take 1-3 minutes.')) return;
      document.getElementById('subtitle').textContent = 'Running AGI ticks...';
      const endpoints = [
        '/v1/agi/sales/tick',
        '/v1/agi/closer/tick',
        '/v1/marketing/tick',
      ];
      for (const ep of endpoints) {
        try {
          document.getElementById('subtitle').textContent = `Running ${ep}...`;
          await fetch(ep, {method: 'POST'});
        } catch (e) { console.error(e); }
      }
      document.getElementById('subtitle').textContent = 'All ticks complete';
      loadDashboard();
    }

    loadDashboard();
</script>
</body>
</html>"""


def build_dashboard_data(backend: SQLiteBackend) -> dict:
    """Build the dashboard data payload."""
    funnel_counts = count_by_state(backend)
    total = sum(funnel_counts.values())

    # Revenue
    rev = DailyRevenueSnapshotter(backend)
    snap = rev.yesterday()
    revenue_cents = snap.gross_cents if snap else 0
    settlements = snap.settlement_count if snap else 0

    # All prospects
    all_prospects = list_states(backend, limit=500)

    # Recent activity (last 20 events from DB)
    import sqlite3
    try:
        cursor = backend.execute(
            "SELECT prospect_id, to_state, actor, notes, occurred_at "
            "FROM si_funnel_event ORDER BY id DESC LIMIT 20"
        )
        recent = [dict(r) for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        recent = []

    # AGI cycle count (heuristic: count of agi-scout/agi-marketing events)
    try:
        cursor = backend.execute(
            "SELECT COUNT(*) AS cnt FROM si_funnel_event WHERE actor LIKE 'agi-%'"
        )
        agi_cycle = cursor.fetchone()["cnt"]
    except sqlite3.OperationalError:
        agi_cycle = 0

    brief = build_brief(backend)

    return {
        "engine": "Empire OS",
        "version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "funnel_total": total,
        "funnel": funnel_counts,
        "revenue_cents": revenue_cents,
        "settlements": settlements,
        "agi_cycle": agi_cycle,
        "revenue_date": snap.date if snap else None,
        "brief_headline": brief.headline if hasattr(brief, 'headline') else {},
        "prospects": [
            {
                "prospect_id": p.prospect_id,
                "state": p.current_state,
                "actor": p.actor,
                "occurred_at": p.occurred_at,
            }
            for p in all_prospects
        ],
        "recent_activity": [
            {
                "prospect_id": r["prospect_id"],
                "state": r["to_state"],
                "actor": r["actor"],
                "notes": r.get("notes", ""),
                "time": r.get("occurred_at", ""),
            }
            for r in recent
        ],
    }
