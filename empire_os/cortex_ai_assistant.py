"""
Empire OS v3 — Cortex AI Business Assistant
==========================================
AI-powered business operator that observes Empire state + asks LLM
(MiniMax M3 via OpenRouter) for actionable recommendations.

Single endpoint, drops to /root/feedback/cortex_brain.json, polled
by empire-cortex-engine.timer (10m cadence).
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

import requests
from openai import OpenAI

DB_PATH = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = FEEDBACK_DIR / "cortex_brain.json"


def get_snapshot() -> Dict:
    """Pull current empire state from DB."""
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tables": {},
        "alerts": [],
        "kpis": {},
    }

    try:
        # Lead counts
        snapshot["tables"]["lane_leads_total"] = c.execute(
            "SELECT COUNT(*) FROM lane_leads"
        ).fetchone()[0]
        snapshot["tables"]["lane_leads_today"] = c.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now', '-1 day')"
        ).fetchone()[0]

        # Tier breakdown (use whatever tiers the DB has)
        tier_rows = c.execute(
            "SELECT omega_tier, COUNT(*) FROM lane_leads GROUP BY omega_tier"
        ).fetchall()
        snapshot["tables"]["tiers"] = {r["omega_tier"]: r["COUNT(*)"] for r in tier_rows if r["omega_tier"]}

        # A2A matches
        try:
            snapshot["tables"]["buyer_leads_total"] = c.execute(
                "SELECT COUNT(*) FROM buyer_leads"
            ).fetchone()[0]
            snapshot["tables"]["buyer_leads_with_endpoint"] = c.execute(
                "SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status = 'ok' OR endpoint_status = 'received'"
            ).fetchone()[0]
        except Exception:
            snapshot["tables"]["buyer_leads_total"] = 0
            snapshot["tables"]["buyer_leads_with_endpoint"] = 0

        # Test deliveries
        try:
            snapshot["tables"]["test_received_count"] = c.execute(
                "SELECT COUNT(*) FROM test_received_leads"
            ).fetchone()[0]
        except Exception:
            snapshot["tables"]["test_received_count"] = 0

        # Buyer population
        try:
            snapshot["tables"]["active_buyers"] = c.execute(
                "SELECT COUNT(*) FROM si_buyer_outreach WHERE active = 1"
            ).fetchone()[0]
        except Exception:
            try:
                snapshot["tables"]["active_buyers"] = c.execute(
                    "SELECT COUNT(*) FROM si_buyer_outreach"
                ).fetchone()[0]
            except Exception:
                snapshot["tables"]["active_buyers"] = 0
        try:
            snapshot["tables"]["buyers_with_pricing"] = c.execute(
                "SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0"
            ).fetchone()[0]
        except Exception:
            snapshot["tables"]["buyers_with_pricing"] = 0

        # CRM
        try:
            snapshot["tables"]["crm_leads_total"] = c.execute(
                "SELECT COUNT(*) FROM crm_leads"
            ).fetchone()[0]
        except Exception:
            snapshot["tables"]["crm_leads_total"] = 0

        # Tenants
        try:
            snap_tenants = c.execute(
                "SELECT COUNT(*) FROM si_tenant"
            ).fetchone()
            snapshot["tables"]["tenants"] = snap_tenants[0] if snap_tenants else 0
        except Exception:
            snapshot["tables"]["tenants"] = 0

        # Invoices / settlements
        try:
            inv_open = c.execute(
                "SELECT COUNT(*) FROM invoices WHERE status = 'open'"
            ).fetchone()[0]
            snapshot["tables"]["invoices_open"] = inv_open
        except Exception:
            pass

        try:
            settled = c.execute(
                "SELECT COUNT(*) FROM si_settlements WHERE status = 'confirmed'"
            ).fetchone()[0]
            snapshot["tables"]["settlements_paid"] = settled
        except Exception:
            pass

    finally:
        c.close()

    # KPIs / alerts
    total = snapshot["tables"].get("lane_leads_total", 0)
    settled = snapshot["tables"].get("settlements_paid", 0)
    buyers_priced = snapshot["tables"].get("buyers_with_pricing", 0)

    if buyers_priced < 100:
        snapshot["alerts"].append(
            f"Only {buyers_priced}/30192 buyers have payout_per_lead configured. Revenue blocked."
        )
    if settled == 0 and total > 1000:
        snapshot["alerts"].append(
            f"{total} leads scored, 0 settlements. Revenue loop is dry."
        )
    if snapshot["tables"].get("buyers_with_endpoint", 0) > 0:
        snapshot["kpis"]["delivery_rate"] = round(
            100 * snapshot["tables"]["buyers_with_endpoint"]
            / max(1, snapshot["tables"]["buyer_leads_total"]),
            1,
        )

    return snapshot


# ─── LLM prompt ───────────────────────────────────────────────────────

BRAIN_PROMPT = """
You are **Cortex**, the AI business operator for Empire OS v3 — an autonomous
B2B lead-generation + lead-marketplace platform. The system scrapes leads
from public sources, scores them via AI, matches to buyers, and delivers
leads to buyers for a pay-per-lead fee. Revenue is settled in USDC on Solana.

Snapshot (live state):
{snapshot}

Operator signal (Philipp, founder):
- Aggressive revenue framing, real verification (no fabrication), concise.
- Wants ACTIONS, not opinions.
- 1) Recommend 3 high-impact actions for the next 24h.
- 2) Call out the single biggest leak blocking revenue.
- 3) Confirm or reject any suspicious-looking numbers.
- 4) Suggest 1 cron/agent to spin up if missing.

Keep answer under 350 words. Plain text, executive tone.
""".strip()


def _get_key(env_name: str, secret_file: str) -> str:
    """Pull key from env or /root/empire_secrets/<file>."""
    k = os.environ.get(env_name, "").strip()
    if not k:
        p = Path(f"/root/empire_secrets/{secret_file}")
        if p.exists():
            k = p.read_text().strip()
    return k


def _ask_provider(api_key: str, base_url: str, model: str, snapshot: Dict,
                  max_tokens: int = 900) -> Dict:
    """Single-provider LLM call. Returns dict with content/error/usage."""
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": BRAIN_PROMPT.format(snapshot=json.dumps(snapshot, indent=2))
            }],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        usage = resp.usage
        return {
            "model": model,
            "content": content,
            "tokens": usage.total_tokens if usage else 0,
            "ok": True,
        }
    except Exception as e:
        return {"error": str(e), "ok": False}


# Provider chain — tried in order; first OK wins. Skip providers with no key.
# Order: free/cheap first, paid last.
PROVIDERS = [
    {
        "name": "gemini",
        "key_env": "GOOGLE_API_KEY",
        "key_file": "google_api_key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
        "max_tokens": 900,
    },
    {
        "name": "minimax",
        "key_env": "MINIMAX_API_KEY",
        "key_file": "minimax_api_key",
        "base_url": "https://api.minimax.io/v1",
        "model": "MiniMax-M3",
        "max_tokens": 900,
    },
    {
        "name": "openrouter",
        "key_env": "OPENROUTER_API_KEY",
        "key_file": "openrouter_api_key",
        "base_url": "https://openrouter.ai/api/v1",
        "model": os.environ.get("CORTEX_MODEL", "google/gemini-2.5-flash"),
        "max_tokens": 900,
    },
]


def _rule_based_advice(snapshot: Dict) -> Dict:
    """No-LLM fallback. Deterministic recommendations from live state.

    Same shape as LLM advice (model/content/tokens/ok) so downstream
    consumers don't care which path produced it.
    """
    t = snapshot.get("tables", {})
    alerts = snapshot.get("alerts", [])
    leads = t.get("lane_leads_total", 0)
    buyers = t.get("active_buyers", 0)
    buyers_priced = t.get("buyers_with_pricing", 0)
    settled = t.get("settlements_paid", 0)
    delivery = t.get("buyer_leads_with_endpoint", 0)
    leads_today = t.get("lane_leads_today", 0)

    actions = []
    leak = None

    # 1. The single biggest leak
    if buyers and buyers_priced and buyers_priced < buyers * 0.05:
        leak = (
            f"BLOCKER: only {buyers_priced}/{buyers} buyers have "
            f"payout_per_lead configured. No price = no delivery = no revenue. "
            f"Backfill si_buyer_outreach.payout_per_lead for at least 200 active buyers."
        )
    elif settled == 0 and leads > 1000:
        leak = (
            f"BLOCKER: {leads} leads scored but 0 settlements. "
            f"Either delivery is broken (check /v1/swarm/audit-log) or "
            f"buyers won't pay (check buyer webhook responses)."
        )
    elif leads_today == 0 and leads > 100:
        leak = "PIPELINE DRY: 0 new leads in 24h. Scraper or ingest is stalled."
    elif delivery > 0 and settled == 0:
        leak = (
            f"Delivered {delivery} test leads but 0 settlements — buyer ack/payment broken."
        )
    else:
        leak = "No dominant leak — focus on volume (more leads) or price (raise payout)."

    # 2. Three high-impact actions
    if buyers_priced < 100:
        actions.append(
            f"PRICE 200 BUYERS NOW: si_buyer_outreach.payout_per_lead is "
            f"missing for {buyers - buyers_priced} buyers. Run a bulk UPDATE "
            f"with market-rate defaults ($4-15/lead by niche)."
        )
    if settled == 0:
        actions.append(
            "REPLAY 3 TEST LEADS end-to-end: pick 3 graded leads, POST to "
            "/v1/finance/replay (NOT force_status), trace the audit log to "
            "see exactly where the chain breaks."
        )
    if leads_today < 50:
        actions.append(
            f"BOOST SUPPLY: only {leads_today} new leads today. "
            f"Run /root/empire_os/scripts/lead_scrape.py or add 1 metro "
            f"to the daily market sweep."
        )
    actions.append(
        "DEPLOY solana-listener watchdog: cron every 60s checking "
        "vault_balance_usdc + matching inbound tx memos to "
        "si_ppl_leads.without status update."
    )

    # 3. Confirm/reject suspicious numbers
    confirmations = []
    if settled == 0 and leads > 50000:
        confirmations.append(
            f"REJECT: {leads} scored leads is suspicious — verify lane_leads "
            f"row count directly. May include duplicates / failed scrapes."
        )
    if buyers > 1000 and buyers_priced < 5:
        confirmations.append(
            f"REJECT: claiming {buyers} active buyers but only "
            f"{buyers_priced} priced = the buyer outreach didn't actually "
            f"close deals. Re-qualify."
        )

    # 4. Suggested cron
    cron_suggestion = (
        "empire-settlement-watchdog.timer (every 60s): poll "
        "solana vault + match inbound USDC to si_ppl_leads. "
        "Auto-flip lead status to 'paid' on memo match."
    )

    body = (
        "CORTEX (rule-based, no LLM available)\n\n"
        f"BIGGEST LEAK:\n{leak}\n\n"
        "TOP 3 ACTIONS (next 24h):\n"
        + "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions[:3]))
        + "\n\n"
        "NUMBER CHECKS:\n"
        + ("\n".join(f"- {c}" for c in confirmations) if confirmations
           else "- No suspicious numbers flagged.")
        + "\n\n"
        f"MISSING CRON:\n{cron_suggestion}\n"
    )

    return {
        "model": "rule-based-fallback",
        "content": body,
        "tokens": 0,
        "ok": True,
        "alerts_count": len(alerts),
        "snapshot_summary": {
            "leads": leads,
            "buyers_priced": buyers_priced,
            "settled": settled,
            "leads_today": leads_today,
        },
    }


def ask_brain(snapshot: Dict, model: str = None) -> Dict:
    """Send snapshot to LLM. Try each provider in chain until one succeeds.

    Chain order: MiniMax first (free, no credits issue), OpenRouter fallback.
    If all providers fail or no key is available, fall back to a rule-based
    recommender that reads the snapshot and emits actionable advice.
    """
    tried = []
    for prov in PROVIDERS:
        if model and prov["name"] not in model.lower():
            # Allow caller to pin a specific provider by substring
            continue
        key = _get_key(prov["key_env"], prov["key_file"])
        if not key:
            tried.append({"provider": prov["name"], "skip": "no_key"})
            continue
        result = _ask_provider(
            api_key=key,
            base_url=prov["base_url"],
            model=prov["model"],
            snapshot=snapshot,
            max_tokens=prov["max_tokens"],
        )
        tried.append({"provider": prov["name"], "model": prov["model"],
                      "ok": result.get("ok"), "err": result.get("error", "")[:120]})
        if result.get("ok"):
            result["chain"] = tried
            return result
        # On hard failure (402 credits, 429, 401), try next provider
        err_str = str(result.get("error", "")).lower()
        if not any(t in err_str for t in ["402", "credits", "429", "rate", "401", "unauthorized"]):
            # Non-billing error — log but don't spin through whole chain
            result["chain"] = tried
            return result

    return {"error": "all_providers_failed", "ok": False, "chain": tried,
            "fallback": _rule_based_advice.__name__}


def main():
    """Entry point — save snapshot + LLM advice to feedback dir."""
    snap = get_snapshot()
    advice = ask_brain(snap)
    # If every LLM provider failed, drop to the rule-based fallback so the
    # cortex_brain.json always has actionable content (no empty ok=False).
    if not advice.get("ok"):
        rb = _rule_based_advice(snap)
        advice["llm_failed"] = True
        advice["fallback_used"] = True
        # Merge: keep the chain log, but serve rule-based content
        advice["content"] = rb["content"]
        advice["ok"] = True
        advice["model"] = rb["model"] + " (after LLM chain failed)"
        advice["fallback_snapshot"] = rb["snapshot_summary"]
    out = {"snapshot": snap, "advice": advice}
    OUTPUT_PATH.write_text(json.dumps(out, indent=2, default=str))
    print(f"WROTE {OUTPUT_PATH} (tokens={advice.get('tokens', 0)})")
    # Echo key alerts
    for a in snap.get("alerts", [])[:3]:
        print(f"  ALERT: {a}")
    if advice.get("content"):
        print("--- AI BRAIN ---")
        print(advice["content"][:1500])


if __name__ == "__main__":
    main()
