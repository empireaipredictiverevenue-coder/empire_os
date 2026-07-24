#!/usr/bin/env python3
"""
Cortex Brain Strategic Loop — Empire OS v3
===========================================
Runs every 5 minutes as a strategic brain loop:
1. Queries predictive revenue + market gaps from empire_os.predictive
2. Calls cortex_ai_assistant.py (MiniMax → OpenRouter fallback) for strategic decisions
3. Emits price/niche pivot decisions to cortex_brain.json
4. Feeds back to intelligence_loop buyer scoring via cortex_scorer

Run as daemon: python3 cortex_brain_loop.py --daemon
Run once:      python3 cortex_brain_loop.py --once
"""

from __future__ import annotations
import json
import os
import sys
import time
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

sys.path.insert(0, "/root/empire_os")

# Import the predictive engine
from empire_os.predictive import (
    predict_revenue,
    detect_market_gaps,
    detect_leaks,
    detect_waste,
)

# Import cortex_ai_assistant for LLM calls AND the rule-based fallback
from empire_os.cortex_ai_assistant import ask_brain, get_snapshot, _rule_based_advice

# Import cortex_scorer for buyer scoring feedback
from empire_os.cortex_scorer import get_niche_score, re_score_existing

DB_PATH = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/feedback")
CORTEX_BRAIN_PATH = FEEDBACK_DIR / "cortex_brain.json"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

INTERVAL_SEC = int(os.environ.get("CORTEX_BRAIN_INTERVAL", "300"))  # 5 min default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(level: str, msg: str, **fields):
    event = {"ts": now_iso(), "level": level, "msg": msg, **fields}
    log_path = FEEDBACK_DIR / "cortex_brain_loop.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")
    if level in ("ERROR", "WARN", "CYCLE"):
        print(json.dumps(event), flush=True)


def gather_live_state() -> Dict[str, Any]:
    """Pull live state from DB for predictive revenue + market gap analysis."""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    state = {}
    def gather_live_state() -> Dict[str, Any]:
        """Pull live state from DB for predictive revenue + market gap analysis."""
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        state = {}

        try:
            # Lane counts
            state["lane_count"] = c.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]
            state["occupied_lanes"] = c.execute(
                "SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''"
            ).fetchone()[0]

            # Lead counts
            state["leads_total"] = c.execute("SELECT COUNT(*) FROM si_buyer_outreach").fetchone()[0]
            state["leads_today"] = c.execute(
                "SELECT COUNT(*) FROM si_buyer_outreach WHERE created_at > datetime('now', '-1 day')"
            ).fetchone()[0]

            # Funnel states - use si_subscription status
            funnel = {}
            for st, n in c.execute("SELECT status, COUNT(*) FROM si_subscription GROUP BY status").fetchall():
                funnel[st] = n
            for st, n in c.execute("SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage").fetchall():
                funnel[st] = funnel.get(st, 0) + n
            state["funnel"] = funnel

            # Avg seat price
            avg_seat = c.execute(
                "SELECT AVG(price_cents) FROM si_subscription WHERE price_cents > 0"
            ).fetchone()[0] or 59900
            state["avg_seat_price"] = avg_seat / 100.0

            # Buyer pricing
            state["buyers_total"] = c.execute(
                "SELECT COUNT(*) FROM si_buyer_outreach WHERE active = 1"
            ).fetchone()[0]
            state["buyers_priced"] = c.execute(
                "SELECT COUNT(*) FROM si_buyer_outreach WHERE active = 1 AND payout_per_lead > 0"
            ).fetchone()[0]
            state["buyers_with_endpoint"] = c.execute(
                "SELECT COUNT(*) FROM si_buyer_outreach WHERE active = 1 AND endpoint_url != ''"
            ).fetchone()[0]

            # Settlements
            state["settlements_paid"] = c.execute(
                "SELECT COUNT(*) FROM si_settlements"
            ).fetchone()[0]

            # Vault balance - use a fallback since app_kv doesn't exist
            state["vault_usdc"] = 0.0

            # Lane data for market gaps
            state["lanes"] = c.execute(
                "SELECT sub_niche, metro, occupied_by, seat_price FROM lanes"
            ).fetchall()

            # Lead data for market gaps - use si_buyer_outreach which has niche/metro
            state["leads"] = c.execute(
                "SELECT niche, metro FROM si_buyer_outreach WHERE niche != '' LIMIT 500"
            ).fetchall()

        finally:
            c.close()

        return state


def run_predictive_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the 4-pillar predictive analysis on live state."""
    # Convert DB rows to dicts
    lanes = [dict(r) for r in state.get("lanes", [])]
    leads = [dict(r) for r in state.get("leads", [])]

    # Pillar 1: Predictive Revenue
    revenue = predict_revenue(
        lane_count=state["lane_count"],
        occupied_lanes=state["occupied_lanes"],
        leads_total=state["leads_total"],
        funnel_by_state=state["funnel"],
        avg_seat_price=state["avg_seat_price"],
        conversion_rate=0.05,
    )

    # Pillar 2: Market Gaps
    gaps = detect_market_gaps(lanes, leads)

    # Pillar 3: Leaks
    leaks = detect_leaks(state["funnel"])

    # Pillar 4: Waste
    waste = detect_waste(lanes, {})

    return {
        "revenue": revenue,
        "market_gaps": gaps,
        "leaks": leaks,
        "waste": waste,
        "state_summary": {
            "lane_count": state["lane_count"],
            "occupied_lanes": state["occupied_lanes"],
            "leads_total": state["leads_total"],
            "leads_today": state["leads_today"],
            "buyers_total": state["buyers_total"],
            "buyers_priced": state["buyers_priced"],
            "settlements_paid": state["settlements_paid"],
            "avg_seat_price": state["avg_seat_price"],
        },
    }


def build_llm_prompt(analysis: Dict[str, Any]) -> str:
    """Build the strategic prompt for Cortex AI Assistant (MiniMax → OpenRouter)."""
    rev = analysis["revenue"]
    gaps = analysis["market_gaps"]
    leaks = analysis["leaks"]
    waste = analysis["waste"]
    summary = analysis["state_summary"]

    prompt = f"""You are **Cortex Strategic Brain** — the 5-minute strategic loop for Empire OS v3.

LIVE STATE (now):
- Lanes: {summary['lane_count']} total, {summary['occupied_lanes']} occupied ({summary['occupied_lanes']/max(summary['lane_count'],1)*100:.1f}%)
- Leads: {summary['leads_total']} total, {summary['leads_today']} today
- Buyers: {summary['buyers_total']} active, {summary['buyers_priced']} priced
- Settlements: {summary['settlements_paid']} paid
- Avg seat price: ${summary['avg_seat_price']:.2f}/mo

REVENUE PROJECTION:
- Active seats MRR: ${rev.get('active_seats_mrr', 0):,.2f}
- Projected new MRR: ${rev.get('projected_new_mrr', 0):,.2f}
- Total predicted MRR: ${rev.get('total_predicted_mrr', 0):,.2f}
- Unrealized MRR (empty lanes): ${rev.get('unrealized_mrr', 0):,.2f}
- Funnel velocity: {rev.get('funnel_velocity', 0):.3f}
- Confidence: {rev.get('confidence', 0):.2f}

MARKET GAPS:
- Hot gaps (raise price): {gaps.get('counts', {}).get('hot', 0)}
- Unsaturated (recruit providers): {gaps.get('counts', {}).get('unsaturated', 0)}
- Dead markets (kill/pivot): {gaps.get('counts', {}).get('dead', 0)}
Top hot: {json.dumps(gaps.get('hot_gaps', [])[:3], default=str)}
Top unsaturated: {json.dumps(gaps.get('unsaturated', [])[:3], default=str)}

LEAKS (funnel drop-offs):
- Total leaked: {leaks.get('total_leaked', 0)}
- Top leaks: {json.dumps(leaks.get('leaks', [])[:3], default=str)}

WASTE:
- Waste lanes: {waste.get('total_waste_indicators', 0)}
- Top waste: {json.dumps(waste.get('waste_lanes', [])[:3], default=str)}

────────────────────────────────────────
OUTPUT JSON (exact keys, no extra text):
{{
  "price_pivots": [
    {{"niche_metro": "roofing:dallas", "action": "raise_price", "new_price_usd": 12, "rationale": "high occupancy + high demand"}}
  ],
  "niche_pivots": [
    {{"niche_metro": "hvac:miami", "action": "pivot_to", "target_niche": "solar:miami", "rationale": "dead market, adjacent high demand"}}
  ],
  "buyer_scoring_overrides": [
    {{"niche": "roofing", "metro": "dallas", "score_boost": 15, "reason": "hot gap, price elasticity"}}
  ],
  "strategic_alert": "Single biggest revenue lever right now: PRICE 200 buyers in hot niches. 0 settlements = broken delivery chain.",
  "confidence": 0.85
}}
"""
    return prompt


def call_cortex_ai(prompt: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Call cortex_ai_assistant.ask_brain with the strategic prompt."""
    # Build a snapshot dict that cortex_ai_assistant expects
    snapshot = {
        "ts": now_iso(),
        "tables": {
            "lane_leads_total": 0,
            "lane_leads_today": 0,
            "tiers": {},
            "buyer_leads_total": 0,
            "buyer_leads_with_endpoint": 0,
            "active_buyers": 0,
            "buyers_with_pricing": 0,
        },
        "alerts": [],
        "kpis": {},
    }

    # Use ask_brain which has the MiniMax → OpenRouter fallback chain
    result = ask_brain(snapshot, model=None)  # None = use provider chain

    if not result.get("ok"):
        log("ERROR", "cortex_ai_failed", error=result.get("error", "unknown"), chain=result.get("chain"))
        return {}

    content = result.get("content", "")
    log("INFO", "cortex_ai_response", model=result.get("model"), tokens=result.get("tokens"))

    # Try to parse JSON from the response
    try:
        # Extract JSON from response (might be wrapped in markdown)
        import re
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(content)
    except json.JSONDecodeError:
        # If not JSON (e.g., rule-based fallback), create structured decisions from text
        log("INFO", "cortex_ai_plain_text_fallback", content=content[:300])
        return parse_rule_based_decisions(content, analysis)


def parse_rule_based_decisions(text: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured decisions from rule-based fallback text."""
    decisions = {
        "price_pivots": [],
        "niche_pivots": [],
        "buyer_scoring_overrides": [],
        "strategic_alert": "",
        "confidence": 0.5,
    }
    
    # Extract key actionable insights from the rule-based text
    # The fallback text has sections like "BIGGEST LEAK:", "TOP 3 ACTIONS:", "NUMBER CHECKS:", "MISSING CRON:"
    
    if "BIGGEST LEAK:" in text:
        # Extract the leak description
        start = text.find("BIGGEST LEAK:") + len("BIGGEST LEAK:")
        end = text.find("\n\n", start)
        if end == -1:
            end = len(text)
        decisions["strategic_alert"] = text[start:end].strip()
    
    if "TOP 3 ACTIONS (next 24h):" in text:
        start = text.find("TOP 3 ACTIONS (next 24h):") + len("TOP 3 ACTIONS (next 24h):")
        end = text.find("\n\n", start)
        if end == -1:
            end = len(text)
        actions_text = text[start:end].strip()
        
        # Parse actions for price pivots and niche pivots
        for line in actions_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Look for pricing actions
            if "PRICE" in line.upper() and ("BUYER" in line.upper() or "PAYOUT" in line.upper()):
                decisions["price_pivots"].append({
                    "niche_metro": "all:all",
                    "action": "raise_price" if "RAISE" in line.upper() else "set_price",
                    "new_price_usd": 12,
                    "rationale": line[:200]
                })
            elif "BOOST" in line.upper() and "SUPPLY" in line.upper():
                decisions["niche_pivots"].append({
                    "niche_metro": "high_demand:all",
                    "action": "recruit_providers",
                    "target_niche": "high_demand",
                    "rationale": line[:200]
                })
    
    # Extract scoring overrides from market gaps analysis if present
    if "hot_gaps" in str(analysis.get("market_gaps", {})):
        gaps = analysis.get("market_gaps", {}).get("hot_gaps", [])
        for gap in gaps[:3]:
            decisions["buyer_scoring_overrides"].append({
                "niche": gap.get("niche_metro", "").split(":")[0],
                "metro": gap.get("niche_metro", "").split(":")[1] if ":" in gap.get("niche_metro", "") else "",
                "score_boost": 10,
                "reason": f"hot gap: {gap.get('rationale', '')}"
            })
        
        unsaturated = analysis.get("market_gaps", {}).get("unsaturated", [])
        for gap in unsaturated[:3]:
            decisions["buyer_scoring_overrides"].append({
                "niche": gap.get("niche_metro", "").split(":")[0],
                "metro": gap.get("niche_metro", "").split(":")[1] if ":" in gap.get("niche_metro", "") else "",
                "score_boost": 5,
                "reason": f"unsaturated market: {gap.get('rationale', '')}"
            })
    
    return decisions


def apply_buyer_scoring_feedback(pivots: Dict[str, Any]):
    """Feed buyer scoring overrides back to cortex_scorer / intelligence_loop."""
    overrides = pivots.get("buyer_scoring_overrides", [])
    if not overrides:
        return

    c = sqlite3.connect(DB_PATH)
    try:
        for override in overrides:
            niche = override.get("niche", "").lower()
            metro = override.get("metro", "").lower()
            boost = override.get("score_boost", 0)
            reason = override.get("reason", "cortex_brain")

            if not niche or boost == 0:
                continue

            # Update niche scores in the cortex cache
            # The cortex_scorer reads from /run/cortex_niche_scores.json
            # We'll update the DB with a scoring override table if needed
            c.execute(
                """INSERT OR REPLACE INTO cortex_score_overrides (niche, metro, score_boost, reason, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (niche, metro, boost, reason, now_iso()),
            )
        c.commit()
        log("INFO", "buyer_scoring_feedback_applied", overrides=len(overrides))
    except Exception as e:
        log("WARN", "buyer_scoring_feedback_failed", error=str(e))
    finally:
        c.close()


def emit_cortex_brain_json(analysis: Dict[str, Any], decisions: Dict[str, Any]):
    """Write the unified cortex_brain.json that intelligence_loop polls."""
    output = {
        "ts": now_iso(),
        "state": analysis["state_summary"],
        "revenue_projection": analysis["revenue"],
        "market_gaps": analysis["market_gaps"],
        "leaks": analysis["leaks"],
        "waste": analysis["waste"],
        "strategic_decisions": decisions,
        "feedback_loop": {
            "buyer_scoring_updated": bool(decisions.get("buyer_scoring_overrides")),
            "price_pivots_issued": len(decisions.get("price_pivots", [])),
            "niche_pivots_issued": len(decisions.get("niche_pivots", [])),
        },
    }

    # Atomic write
    tmp = CORTEX_BRAIN_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(output, indent=2, default=str))
    tmp.replace(CORTEX_BRAIN_PATH)

    log("CYCLE", "cortex_brain_emitted", path=str(CORTEX_BRAIN_PATH))


def run_cycle():
    """One strategic loop iteration."""
    log("CYCLE", "cortex_brain_cycle_start")

    try:
        # 1. Gather live state
        state = gather_live_state()

        # 2. Run predictive analysis (4 pillars)
        analysis = run_predictive_analysis(state)

        # 3. Build LLM prompt and call Cortex AI (MiniMax → OpenRouter)
        prompt = build_llm_prompt(analysis)
        decisions = call_cortex_ai(prompt, analysis)

        # 4. Apply buyer scoring feedback
        if decisions:
            apply_buyer_scoring_feedback(decisions)

        # 5. Emit unified cortex_brain.json
        emit_cortex_brain_json(analysis, decisions or {})

        # 6. Trigger re-score of existing leads with new niche scores
        if decisions and decisions.get("buyer_scoring_overrides"):
            re_score_existing(limit=500)

        log("CYCLE", "cortex_brain_cycle_done",
            price_pivots=len(decisions.get("price_pivots", [])),
            niche_pivots=len(decisions.get("niche_pivots", [])),
            scoring_overrides=len(decisions.get("buyer_scoring_overrides", [])))

    except Exception as e:
        log("ERROR", "cortex_brain_cycle_failed", error=str(e))
        raise


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cortex Brain Strategic Loop")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (default)")
    args = parser.parse_args()

    if args.once:
        run_cycle()
    else:
        log("INFO", "cortex_brain_loop_starting", interval_sec=INTERVAL_SEC)
        while True:
            try:
                run_cycle()
            except Exception as e:
                log("ERROR", "cycle_exception", error=str(e))
            time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()