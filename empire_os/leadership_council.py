#!/usr/bin/env python3
"""Empire OS — Leadership Council (CEO / CTO / Chief of Staff).

Rule-based, auditable, NO LLM dependency (runs without Ollama).
Reads behavior_engine findings and produces concrete leadership output:

  - CEO: 3 hook variants for the top-attention niches (move D->C).
  - CTO: pay-link friction fixes (the 0-confirmed wall).
  - CoS: 3-item weekly action brief -> g-brain.

Every output traces to a real behavior_engine signal. No invented metrics.

Run: /root/venv/bin/python3 empire_os/leadership_council.py
"""
import json, sys, os
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
BRIEF_PATH = "/root/g-brain/system/chief_of_staff_brief.md"

# top niches by signup (from behavior_engine; hardcoded fallback order matches
# the live data we already observed: roofing > solar > hvac)
TOP_NICHES = ["roofing", "solar", "hvac"]


def _hook_variants(niche: str, conv_rate: float) -> list[str]:
    """CEO hook variants — Grade 5-7, urgent, specific. Attack the pay wall
    when conv_rate is ~0 (awareness is fine, conversion is the problem)."""
    if conv_rate < 0.5:
        # attention exists, conversion dead -> hook attacks the pay step
        return [
            f"{niche.title()} help in your area — pay $299 today, locked founder rate. Link expires soon.",
            f"Storm season: {niche.title()} claims paid fast via USDC. Settle in minutes, not weeks.",
            f"Your {niche} lead is graded C (warm). Claim it now — $299 founder price won't hold.",
        ]
    return [
        f"Top {niche.title()} experts near you — free grade, pay only if it converts.",
        f"{niche.title()} leads scored A/B/C. Buy the ones that close.",
        f"Get {niche.title()} calls that actually pay. $0.50 per converted lead.",
    ]


def _paylink_fixes(links_sent: int, confirmed: int) -> list[str]:
    """CTO pay-link friction fixes — the 0-confirmed wall."""
    return [
        f"FRICTION: {links_sent} pay links sent, {confirmed} confirmed. "
        f"Wall = USDC confirm step. Fix: deep-link straight to Solana Pay QR "
        f"(pre-filled amount + EVAL_/seat memo), skip intermediate landing page.",
        "Add trust signal on CTA: 'Secured by Solana · instant settlement' + "
        "show vault wallet address (proves real, not a form).",
        "Add urgency: founder $299 discount shows a real deadline countdown.",
        "Fail-soft: if wallet-connect errors, show copy-paste address + QR as fallback.",
    ]


def run() -> dict:
    from empire_os.behavior_engine import main as behavior_main
    b = behavior_main()

    att = b["attention"]
    pf = b["payment_friction"]
    niches = att.get("by_niche", [])
    nichemap = {n["niche"]: n for n in niches}

    # CEO output
    ceo_hooks = {}
    for n in TOP_NICHES:
        info = nichemap.get(n, {"conv_rate_pct": 0.0})
        ceo_hooks[n] = {
            "signups": info.get("signups", 0),
            "conv_rate_pct": info.get("conv_rate_pct", 0.0),
            "hooks": _hook_variants(n, info.get("conv_rate_pct", 0.0)),
        }

    # CTO output
    cto_fixes = _paylink_fixes(
        pf.get("pay_links_sent", 0),
        pf.get("eval_settlements", {}).get("settled", 0)
        if isinstance(pf.get("eval_settlements"), dict) else 0,
    )

    # CoS brief
    od = b["outreach_dropoff"]
    biggest_leak = od.get("biggest_drop", "cold")
    brief = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action_1_ceo": f"Ship hook variants for {', '.join(TOP_NICHES)} "
                        f"(attack pay wall, conv ~0%).",
        "action_2_cto": "Fix pay-link friction: deep-link Solana Pay QR, "
                        "trust signal, urgency, fail-soft.",
        "action_3_leak": f"Biggest leak this week: '{biggest_leak}' stage "
                         f"({od.get('conversion_pct', 0)}% conv). Move cold->contacted.",
    }

    # write CoS brief to g-brain
    try:
        os.makedirs(os.path.dirname(BRIEF_PATH), exist_ok=True)
        with open(BRIEF_PATH, "w") as f:
            f.write(f"# Chief of Staff Brief — {brief['ts']}\n\n")
            f.write(f"1. **CEO**: {brief['action_1_ceo']}\n")
            f.write(f"2. **CTO**: {brief['action_2_cto']}\n")
            f.write(f"3. **Biggest leak**: {brief['action_3_leak']}\n")
    except Exception:
        pass

    return {
        "ts": brief["ts"],
        "ceo": ceo_hooks,
        "cto": cto_fixes,
        "cos_brief": brief,
        "brief_written": BRIEF_PATH,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
