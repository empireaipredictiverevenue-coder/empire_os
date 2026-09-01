"""
hermes_signal_feed.py — Feed REAL market signals into the Hermes v9 Growth Engine.

Pulls the latest raw market signals from live sources (no hardcoded sample):
  1. Reddit sniper output (.scout_output.json) — buyer intent / pain posts
  2. Inbound reply daemon log (feedback/inbound_reply_daemon.jsonl) — prospect replies
  3. Audit API runs (audit_api.run_audit) — site-owner friction / complaints

Each signal is run through HermesAgentLoop (Customer Truth -> Objection -> Growth ->
Self-reflect) and persisted to our self-hosted pgvector memory. Drives continuous
learning instead of the static demo string.

Run: python3 empire_os/hermes_signal_feed.py [--limit N]
Cron: every 20m recommended (rotates sources).
"""

import argparse
import asyncio
import glob
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = "/root/empire_os"
SCOUT_PATH = os.path.join(ROOT, ".scout_output.json")
INBOUND_LOG = os.path.join(ROOT, "feedback", "inbound_reply_daemon.jsonl")


def _reddit_signals(limit: int):
    out = []
    if not os.path.exists(SCOUT_PATH):
        return out
    try:
        data = json.load(open(SCOUT_PATH))
    except Exception:
        return out
    leads = data if isinstance(data, list) else data.get("leads", [])
    for ld in leads[:limit]:
        text = (ld.get("title", "") + " " + ld.get("preview", "") + " " + ld.get("body", "")).strip()
        if text:
            out.append(("reddit_intent_monitor", text))
    return out


def _inbound_signals(limit: int):
    """Real prospect reply signals from the inbound reply daemon log.
    event types include reply/forward; body_text holds the actual reply
    (e.g. 'yes', 'buy', 'interested'). These are high-intent buyer signals."""
    out = []
    if not os.path.exists(INBOUND_LOG):
        return out
    lines = []
    with open(INBOUND_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)
    for line in lines[-limit:]:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        text = rec.get("body_text") or rec.get("text") or rec.get("body") or ""
        if isinstance(text, list):
            text = " ".join(str(t) for t in text)
        text = (text or "").strip()
        if text and len(text) > 4:
            evt = rec.get("event", "inbound_reply")
            out.append((f"inbound_reply:{evt}", text[:800]))
    return out


def _buyer_intent_signals(limit: int):
    """Real buyer/lane intent signals from the live sales-loop log:
    sub_niche + metro + seat_price = concrete buyer demand + pricing truth."""
    out = []
    path = os.path.join(ROOT, "feedback", "lane_sales_loop.jsonl")
    if not os.path.exists(path):
        return out
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)
    for line in lines[-limit:]:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        nic = rec.get("sub_niche") or rec.get("niche") or "unknown"
        metro = rec.get("metro") or ""
        price = rec.get("seat_price")
        matched = rec.get("matched_buyers", 0)
        text = (f"Buyer demand in {nic} at {metro}. "
                f"Seat price {price}. Matched buyers: {matched}. "
                f"{'Strong intent, supply thin.' if matched and matched > 0 else 'Demand present, no buyer matched yet.'}")
        out.append(("buyer_intent_signal", text))
    return out


def _audit_signals(limit: int):
    out = []
    try:
        from empire_os.audit_api import run_audit
        targets = ["empire-ai.co.uk", "app.empire-ai.co.uk"]
        for t in targets[:limit]:
            try:
                res = run_audit(f"https://{t}")
                score = res.get("score") if isinstance(res, dict) else None
                issues = " ".join(str(v) for v in (res.get("issues") or [])[:3])
                text = f"Site audit for {t} score {score}. Issues: {issues}".strip()
                if text:
                    out.append(("geo_aeo_radar", text))
            except Exception as e:
                out.append(("geo_aeo_radar", f"Audit of {t} flagged: {str(e)[:200]}"))
    except Exception:
        pass
    return out


async def run(limit: int = 5):
    from empire_os.hermes_master_engine_v9 import HermesAgentLoop
    loop = HermesAgentLoop()

    signals = []
    signals += _reddit_signals(limit)
    signals += _inbound_signals(limit)
    signals += _buyer_intent_signals(limit)
    signals += _audit_signals(limit)

    if not signals:
        print("NO_REAL_SIGNALS (all sources empty — run reddit_sniper / inbound daemon first)")
        return {"processed": 0}

    results = []
    for channel, text in signals:
        try:
            insights = await loop.learning_engine.extract_and_learn(text, channel)
            growth = await loop.growth_engine.Engineer_growth_loop(
                base_copy=insights["refined_copy"], customer_truth=insights["customer_truth"])
            await loop.vector_store.insert_customer_truth(
                channel=channel, raw_text=text[:500],
                pain_point=insights["objection_category"],
                core_truth=insights["customer_truth"],
                metadata={"objection_type": insights["objection_category"]})
            await loop.vector_store.store_objection_pattern(
                objection_category=insights["objection_category"], raw_objection=text[:300],
                counter_angle=insights["counter_angle"], confidence_score=insights["confidence"])
            await loop.vector_store.store_growth_experiment(
                experiment_type=growth["experiment_type"], hypothesis=growth["hypothesis"],
                viral_hook=growth["viral_hook"], projected_k_factor=growth["projected_k_factor"])
            await loop.vector_store.log_learning_cycle(
                original_output=text[:200], critic_score=insights["confidence"],
                refined_output=growth["growth_copy"], learned_truth=insights["customer_truth"])
            results.append({"channel": channel, "objection": insights["objection_category"],
                            "k": growth["projected_k_factor"]})
        except Exception as e:
            results.append({"channel": channel, "error": str(e)[:120]})

    print(json.dumps({"processed": len(results), "results": results}, indent=2))
    return {"processed": len(results), "results": results}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    asyncio.run(run(args.limit))
