"""
Revenue Goals — per-agent target + tracking.

Every agent has a revenue responsibility. The Predictive Agent's formula
is the source of truth for total MRR; this module maps each agent's
contribution to that total and tracks progress.

Goal hierarchy:
  total_mrr_goal = sum of per-agent contributions
  each agent's contribution = the lever they control

Agents and their revenue levers:
  mesh          : keep fleet healthy = enabled_mrr (no direct revenue)
  business      : operator decisions → approved_actions_mrr
  growth        : opportunity_backlog_value (proposed test pipeline $)
  engineering   : uptime_pct × potential_mrr (1% downtime = $X lost)
  scheduling    : claimed → booked conversion lift
  copywriting   : landing_page_conversion_lift
  email         : outreach → reply → claimed pipeline
  predictive    : surfaces the goal itself (revenue forecast)
  design        : page_perception_score → bounce_rate
  funnel        : stuck-prospect_recovery → recovered_mrr
  traffic       : allocation recommendations → estimated_CPL_saved
  conversion    : A/B test wins → lift_$MRR
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = "/root/empire_os/empire_os.db"


# ─────────────────────────────────────────────────────────────────
# 1. AGENT REVENUE GOALS
# ─────────────────────────────────────────────────────────────────

AGENT_GOALS = {
    "mesh": {
        "revenue_lever": "fleet_uptime",
        "baseline_target": 0.99,  # 99% uptime
        "description": "Keep every agent's loop alive; downtime = lost MRR",
        "mrr_per_pct_uptime": 3200,  # $3,200/mo per 1% uptime across the fleet
    },
    "business": {
        "revenue_lever": "operator_decisions_approved",
        "baseline_target": 5,  # 5 decisions approved per week
        "description": "Surface decisions the operator approves; each approval unlocks $X",
        "mrr_per_decision": 200,  # avg $200 MRR impact per approved decision
    },
    "growth": {
        "revenue_lever": "opportunity_backlog",
        "baseline_target": 20,  # 20 hot opportunities queued
        "description": "Keep the test pipeline full; kill underperformers",
        "mrr_per_hot_gap": 50,  # $50 MRR per hot gap surfaced
    },
    "engineering": {
        "revenue_lever": "tickets_resolved",
        "baseline_target": 10,  # 10 tickets/week
        "description": "Fix broken things fast; tickets = lost revenue",
        "mrr_per_ticket": 30,  # $30 avg MRR protected per ticket
    },
    "scheduling": {
        "revenue_lever": "claimed_to_booked",
        "baseline_target": 0.40,  # 40% claimed leads → booked
        "description": "Turn claimed leads into appointments",
        "mrr_per_booking": 500,  # $500/seat/booking
    },
    "copywriting": {
        "revenue_lever": "copy_approved",
        "baseline_target": 8,  # 8 copy specs approved per week
        "description": "Draft conversion copy for landing pages and ads",
        "mrr_per_spec": 100,  # $100 MRR per approved spec
    },
    "email": {
        "revenue_lever": "emails_approved",
        "baseline_target": 50,  # 50 emails approved per week
        "description": "Draft outreach emails (operator reviews every send)",
        "mrr_per_email": 20,  # $20 avg MRR per sent email (lifetime)
    },
    "predictive": {
        "revenue_lever": "forecast_accuracy",
        "baseline_target": 0.80,  # 80% prediction accuracy
        "description": "Forecast MRR + flag gaps; owns the source-of-truth number",
        "mrr_per_accurate_call": 0,  # predictive is meta — doesn't add MRR directly
    },
    "design": {
        "revenue_lever": "design_specs_approved",
        "baseline_target": 6,  # 6 design specs approved per week
        "description": "Draft wireframes, palettes, image prompts",
        "mrr_per_spec": 80,  # $80 MRR per design spec
    },
    "funnel": {
        "revenue_lever": "stuck_prospects_recovered",
        "baseline_target": 15,  # 15 stuck leads recovered/week
        "description": "Surface stuck leads + propose transitions",
        "mrr_per_recovered_lead": 35,  # $35 MRR per recovered lead
    },
    "traffic": {
        "revenue_lever": "allocation_recommendations",
        "baseline_target": 3,  # 3 channel moves approved per week
        "description": "Recommend where to put the next traffic dollar",
        "mrr_per_allocation_move": 400,  # $400 MRR per approved move
    },
    "conversion": {
        "revenue_lever": "experiments_shipped",
        "baseline_target": 2,  # 2 A/B tests shipped per week
        "description": "Design A/B tests, calculate sample size, recommend winner",
        "mrr_per_winning_test": 250,  # $250 MRR per winning test
    },
}


# ─────────────────────────────────────────────────────────────────
# 2. GOAL TRACKING
# ─────────────────────────────────────────────────────────────────

def get_agent_goal(agent_name: str) -> dict:
    """Return goal config for a specific agent."""
    if agent_name not in AGENT_GOALS:
        return {}
    g = dict(AGENT_GOALS[agent_name])
    g["agent"] = agent_name
    g["weekly_target"] = g["baseline_target"]
    g["weekly_target_mrr"] = g["baseline_target"] * g.get("mrr_per_pct_uptime",
        g.get("mrr_per_decision", g.get("mrr_per_hot_gap", g.get("mrr_per_ticket",
        g.get("mrr_per_booking", g.get("mrr_per_spec", g.get("mrr_per_email",
        g.get("mrr_per_recovered_lead", g.get("mrr_per_allocation_move",
        g.get("mrr_per_winning_test", 0))))))))))
    return g


def get_all_goals() -> dict:
    """Return goals for every agent, plus the total weekly target MRR."""
    weekly_total = 0
    agents = {}
    for agent in AGENT_GOALS:
        goal = get_agent_goal(agent)
        agents[agent] = goal
        weekly_total += goal.get("weekly_target_mrr", 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": agents,
        "fleet_weekly_target_mrr": weekly_total,
        "fleet_monthly_target_mrr": weekly_total * 4,
    }


# ─────────────────────────────────────────────────────────────────
# 3. ACTUALS — pull from the log files
# ─────────────────────────────────────────────────────────────────

# Agents that are credited with revenue from the marketplace.
# Each agent "owns" a fraction of the total — they all contribute to
# conversion, but we attribute revenue to a single owner to avoid
# double-counting. Operators can adjust the weights in the registry.
REVENUE_OWNERS = {
    "email": 1.0,        # outreach closes the deal
    "business": 0.0,     # decisions enable but don't close
    "scheduling": 0.0,   # books but isn't paid directly
    "copywriting": 0.0,  # enables conversion but doesn't close
    "traffic": 0.0,
    "growth": 0.0,
}


def read_actuals(agent_name: str) -> dict:
    """Read the agent's log + output jsonl to compute actuals this week."""
    log_path = Path(f"/root/{agent_name}/{agent_name}.log")
    data_path = Path(f"/root/{agent_name}")

    cycles = 0
    if log_path.exists():
        try:
            with log_path.open() as f:
                for line in f:
                    if "cycle " in line and "INFO" in line:
                        cycles += 1
        except Exception:
            pass

    outputs = 0
    if data_path.exists():
        for jsonl in data_path.glob("*.jsonl"):
            try:
                with jsonl.open() as f:
                    outputs += sum(1 for _ in f)
            except Exception:
                pass

    # Real revenue: pull paid invoices from marketplace, attributed
    # to a single owner so the fleet total doesn't double-count
    revenue_usd = 0.0
    if agent_name in REVENUE_OWNERS:
        try:
            from empire_os.marketplace import revenue_summary
            rev = revenue_summary()
            total_paid = rev.get("paid_mrr_usd", 0)
            revenue_usd = total_paid * REVENUE_OWNERS.get(agent_name, 0)
        except Exception as e:
            import sys as _sys
            print("DEBUG revenue_attribution failed for %s: %r" % (agent_name, e), file=_sys.stderr)

    return {
        "agent": agent_name,
        "cycles_total": cycles,
        "outputs_total": outputs,
        "revenue_usd": revenue_usd,
    }


def compute_progress(agent_name: str) -> dict:
    """Compute actual progress against weekly target.

    When real revenue is flowing through the marketplace, the actual
    revenue_usd overrides the count-based estimate. Otherwise, the
    actual is $0 — typing in logs does not count as revenue.
    """
    goal = get_agent_goal(agent_name)
    if not goal:
        return {}
    actuals = read_actuals(agent_name)
    target = goal["weekly_target"]
    revenue = actuals.get("revenue_usd", 0)

    # If we have real revenue, use it directly
    weekly_mrr = goal.get("weekly_target_mrr", 0)
    if revenue > 0 and weekly_mrr > 0:
        progress_pct = min(revenue / weekly_mrr * 100, 100)
        actual_mrr = revenue
        status = "on_track" if progress_pct >= 50 else "behind" if progress_pct >= 20 else "stalled"
    else:
        # No real revenue yet — actual is $0 regardless of how much
        # "work" the agent's logs show
        progress_pct = 0.0
        actual_mrr = 0.0
        status = "no_revenue_yet"

    return {
        "agent": agent_name,
        "lever": goal["revenue_lever"],
        "target": target,
        "actual_outputs": actuals.get("outputs_total", 0),
        "actual_cycles": actuals.get("cycles_total", 0),
        "actual_revenue_usd": revenue,
        "progress_pct": round(progress_pct, 1),
        "weekly_target_mrr": weekly_mrr,
        "actual_mrr": round(actual_mrr, 2),
        "status": status,
    }


# ─────────────────────────────────────────────────────────────────
# 4. FLEET SUMMARY
# ─────────────────────────────────────────────────────────────────

def fleet_summary() -> dict:
    """Build the full fleet revenue goals summary."""
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": {},
        "fleet": {
            "total_agents": len(AGENT_GOALS),
            "weekly_target_mrr": 0,
            "actual_mrr": 0,
            "progress_pct": 0,
        },
    }
    for agent in AGENT_GOALS:
        p = compute_progress(agent)
        if p:
            out["agents"][agent] = p
            out["fleet"]["weekly_target_mrr"] += p["weekly_target_mrr"]
            out["fleet"]["actual_mrr"] += p["actual_mrr"]

    if out["fleet"]["weekly_target_mrr"] > 0:
        out["fleet"]["progress_pct"] = round(
            out["fleet"]["actual_mrr"] / out["fleet"]["weekly_target_mrr"] * 100, 1
        )
    return out


if __name__ == "__main__":
    summary = fleet_summary()

    out = Path("/root/feedback/revenue_goals_%s.json"
               % datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str))

    print("=" * 60)
    print("Empire OS v3 — Revenue Goals (per agent)")
    print("=" * 60)
    for agent, p in summary["agents"].items():
        lever = p["lever"]
        target = p["target"]
        mrr = p["weekly_target_mrr"]
        actual = p["actual_mrr"]
        pct = p["progress_pct"]
        status = p["status"]
        print(f"  {agent:<14} | {lever:<32} | target {target:>6.1f}/wk | ${mrr:>6.0f}/wk MRR | {pct:>5.1f}% [{status}]")

    print()
    print(f"Fleet weekly target:   ${summary['fleet']['weekly_target_mrr']:,.0f}")
    print(f"Fleet monthly target:  ${summary['fleet']['weekly_target_mrr'] * 4:,.0f}")
    print(f"Fleet actual (week):   ${summary['fleet']['actual_mrr']:,.0f}")
    print(f"Fleet progress:        {summary['fleet']['progress_pct']}%")
    print()
    print(f"Full report: {out}")