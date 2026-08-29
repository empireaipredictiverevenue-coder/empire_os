#!/usr/bin/env python3
"""Strategist Agent — Weekly Revenue Architecture.

Synthesizes Cortex + CEO + Business + Innovator + R&D + Settlement data
into master weekly revenue plan with executable moves.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("strategist_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

FEEDBACK_DIR = Path("/root/empire_os/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

INTERVAL = 7 * 24 * 3600  # weekly


def read_feedback_files() -> dict:
    """Read all feedback sources."""
    data = {}
    
    # Cortex report
    try:
        with open(FEEDBACK_DIR / "cortex_report.json") as f:
            data["cortex"] = json.load(f)
    except Exception:
        data["cortex"] = {}
    
    # CEO brief (latest)
    try:
        for f in sorted(FEEDBACK_DIR.glob("ceo_brief_*.jsonl"), reverse=True):
            with open(f) as fh:
                lines = fh.readlines()
                if lines:
                    data["ceo"] = json.loads(lines[-1])
                    break
    except Exception:
        data["ceo"] = {}
    
    # Business decisions
    try:
        with open("/root/business/decisions.jsonl") as f:
            lines = f.readlines()
            data["business"] = [json.loads(l) for l in lines[-10:]]
    except Exception:
        data["business"] = []
    
    # Innovator proposals
    try:
        with open(FEEDBACK_DIR / "innovator_proposals.jsonl") as f:
            lines = f.readlines()
            data["innovator"] = [json.loads(l) for l in lines[-10:]]
    except Exception:
        data["innovator"] = []
    
    # R&D opportunities
    try:
        with open(FEEDBACK_DIR / "rnd_opportunities.jsonl") as f:
            lines = f.readlines()
            data["rnd"] = [json.loads(l) for l in lines[-10:]]
    except Exception:
        data["rnd"] = []
    
    # Settlement data
    try:
        import sqlite3
        conn = sqlite3.connect("/root/empire_os/empire_os.db")
        conn.row_factory = sqlite3.Row
        settlements = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_cents)/100.0,0) FROM si_settlements WHERE settled_at > date('now', '-7 days')"
        ).fetchone()
        charges = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_cents)/100.0,0) FROM si_charges WHERE created_at > date('now', '-7 days')"
        ).fetchone()
        payouts = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_cents)/100.0,0) FROM payout_log WHERE created_at > date('now', '-7 days') AND status='confirmed'"
        ).fetchone()
        conn.close()
        data["settlement"] = {
            "settlements_7d": settlements[0] if settlements else 0,
            "settled_usd_7d": round(settlements[1] if settlements else 0, 2),
            "charges_7d": charges[0] if charges else 0,
            "charged_usd_7d": round(charges[1] if charges else 0, 2),
            "payouts_7d": payouts[0] if payouts else 0,
            "paid_usd_7d": round(payouts[1] if payouts else 0, 2),
        }
    except Exception:
        data["settlement"] = {}
    
    return data


def generate_moves(data: dict, llm) -> list:
    """Generate weekly revenue moves from synthesized data."""
    
    # Build prompt for LLM
    prompt = f"""You are the Strategist for Empire OS v3. Synthesize all intelligence into 3-5 executable revenue moves for this week.

CORTEX: {json.dumps(data.get('cortex', {}).get('kpi', {}), default=str)[:2000]}
CEO: {json.dumps(data.get('ceo', {}), default=str)[:2000]}
BUSINESS: {json.dumps(data.get('business', []), default=str)[:2000]}
INNOVATOR: {[p for p in data.get('innovator', []) if p.get('decision') == 'ship'][:3]}
R&D: {data.get('rnd', [])[:3]}
SETTLEMENT: {data.get('settlement', {})}

Output JSON: {{
  "week": "2026-W34",
  "revenue_target_usd": 5000,
  "moves": [
    {{
      "move": "Deploy bsc-listener watchdog cron",
      "owner": "engineering",
      "deadline": "2026-08-25",
      "expected_usd": 12000,
      "rationale": "0 settlements with 677K leads — vault watchdog is blocker #1"
    }}
  ],
  "loop_closure": {{
    "last_week_moves": 3,
    "completed": 1,
    "blocked": 1,
    "revenue_realized": 3400
  }}
}}"""
    
    try:
        result = llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return result.get("moves", [])
    except Exception as e:
        logger.warning("LLM strategist failed: %s, using fallback", e)
        return fallback_moves(data)


def fallback_moves(data: dict) -> list:
    """Rule-based fallback when LLM unavailable."""
    moves = []
    cortex = data.get("cortex", {})
    settlement = data.get("settlement", {})
    
    # Move 1: Always need settlement bridge if no settlements
    if settlement.get("settlements_7d", 0) == 0:
        moves.append({
            "move": "Deploy bsc-listener watchdog cron (every 60s)",
            "owner": "engineering",
            "deadline": (datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
            "expected_usd": 12000,
            "rationale": f"0 settlements in 7d with {cortex.get('kpi', {}).get('leads_total', '677K')} leads — vault watchdog is blocker #1"
        })
    
    # Move 2: Stuck-deal recovery
    moves.append({
        "move": "Ship Innovator: Stuck-Deal Recovery Engine (/v1/recovery/sequence)",
        "owner": "engineering",
        "deadline": (datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
        "expected_usd": 8500,
        "rationale": "$297K awaiting_payment, 15% recovery = $44K/mo"
    })
    
    # Move 3: LLM keys for Cortex AEO
    moves.append({
        "move": "Add GOOGLE_API_KEY for Cortex AEO generation",
        "owner": "infra",
        "deadline": (datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
        "expected_usd": 5000,
        "rationale": "5 cortex blueprints failing — AEO moat generates buyer intent"
    })
    
    # Move 4: R&D top opportunity
    rnd = data.get("rnd", [])
    if rnd:
        top = rnd[0]
        moves.append({
            "move": f"R&D: {top.get('signal', 'New lead source')[:60]}",
            "owner": "engineering",
            "deadline": (datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
            "expected_usd": int(top.get("score", 3) * 1000),
            "rationale": top.get("rationale", "High-scoring R&D signal")
        })
    
    return moves


def cycle():
    """Single Strategist cycle."""
    logger.info("Strategist cycle starting...")
    
    llm = OllamaClient()
    data = read_feedback_files()
    moves = generate_moves(data, llm)
    
    # Loop closure: read last week's moves
    last_moves = []
    try:
        with open(FEEDBACK_DIR / "strategist_moves.jsonl") as f:
            last_moves = [json.loads(l) for l in f.readlines()[-5:]]
    except Exception:
        pass
    
    completed = sum(1 for m in last_moves if m.get("done"))
    blocked = sum(1 for m in last_moves if m.get("blocked"))
    
    plan = {
        "week": datetime.now(timezone.utc).strftime("%Y-W%U"),
        "revenue_target_usd": 5000,
        "moves": moves,
        "loop_closure": {
            "last_week_moves": len(last_moves),
            "completed": completed,
            "blocked": blocked,
            "revenue_realized": 3400,  # TODO: calculate from settlement data
        }
    }
    
    # Log plan
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_DIR / f"strategist_weekly_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json", "w") as f:
        json.dump(plan, f, indent=2)
    
    # Log moves
    for move in moves:
        move["ts"] = datetime.now(timezone.utc).isoformat()
        move["done"] = False
        with open(FEEDBACK_DIR / "strategist_moves.jsonl", "a") as f:
            f.write(json.dumps(move) + "\n")
    
    logger.info("Strategist plan: %d moves", len(moves))
    return {"moves": len(moves)}


def main():
    logger.info("Strategist agent starting — weekly cadence")
    consecutive_failures = 0
    while True:
        try:
            result = cycle()
            consecutive_failures = 0
            print(json.dumps(result))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            logger.error("Strategist cycle failed: %s (backoff %ds)", e, backoff)
            time.sleep(backoff)
            continue
        time.sleep(INTERVAL)


if __name__ == "__main__":
    import json
    import time
    from datetime import datetime, timezone
    main()