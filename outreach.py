#!/usr/bin/env python3
"""
Empire OS — Two-sided Outreach (sell-side + buy-side).
Uses existing mail_sender._send (Resend, free tier).
Sell-side: pitch businesses our AEO / lead-gen product.
Buy-side:  pitch businesses to BUY verified leads (seat-based, USDC).
Source: real businesses from empire-leads (Overpass) + advertising_agent campaign copy.
NO fake data — only real businesses with real emails/phones we pull live.

Chaining with advertising_agent.py:
  python advertising_agent.py --product vertical_feed --niche roofing \
      --copy campaigns/vertical_feed_roofing_copy.json --send
  -> calls: outreach.py --side both --vertical roofing --copy <campaign.json> --send
"""
import sys, os, json
sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")
import mail_sender as ms

SELL_SUBJECT = "Get cited by AI — your AEO page is ready"
BUY_SUBJECT  = "Verified B2B leads, exclusive per lane — USDC settlement"

SELL_BODY = """Hi,

Your business shows up in searches for {v} services. Right now AI engines
(Google, ChatGPT, Perplexity) decide who gets cited — and you're likely invisible.

We build AEO (Answer Engine Optimization) pages that make LLMs cite YOU.
See: https://empire-ai.co.uk/aeo/empire/{v}/

No Stripe, no KYC — settle in USDC. Setup from $3k.

— Empire OS
https://empire-ai.co.uk/buy-leads
"""

BUY_BODY = """Hi,

We have verified B2B {v} leads — real company domains, exclusive per lane
(one buyer per vertical). No per-lead junk fees; seat-based, settle in USDC.

Grab a seat: https://empire-ai.co.uk/buy-leads
Tiers: bronze $15/lead-equivalent · gold $45 · platinum $90.

— Empire OS
"""

def run(side="both", vertical="logistics", limit=5, dry=False, copy=None, storm=False):
    # Load campaign copy if provided (authored by Hermes via advertising_agent)
    campaign = None
    prospects = []
    if copy and os.path.exists(copy):
        try:
            campaign = json.load(open(copy))
            prospects = campaign.get("prospects", [])
            if campaign.get("pipeline", {}).get("final_copy"):
                SELL_BODY_C = campaign["pipeline"]["final_copy"]
            else:
                SELL_BODY_C = SELL_BODY.format(v=vertical)
        except Exception as e:
            print(f"[outreach] copy load failed: {e}")
            campaign = None
    if not prospects:
        # fallback: pull live from empire-leads
        try:
            sys.path.insert(0, "/root/empire-leads")
            from empire_leads.engine import discover
            srcs = ["nws", "overpass"] if storm else ["overpass"]
            r = discover(vertical, near="Phoenix, AZ", radius=25000, limit=limit, sources=srcs)
            leads = r.leads if hasattr(r, "leads") else []
            for l in leads:
                prospects.append({"name": l.name, "email": l.email or "", "website": l.website or ""})
        except Exception as e:
            print(f"[outreach] no prospects: {e}"); return
    if not prospects:
        print("no real businesses pulled"); return
    sent = 0
    for p in prospects[:limit]:
        dom = (p.get("website") or "").replace("https://", "").replace("http://", "").split("/")[0]
        to = p.get("email") or (f"info@{dom}" if dom else None)
        if not to:
            continue
        if side in ("sell", "both"):
            body = SELL_BODY_C if campaign else SELL_BODY.format(v=vertical)
            if dry: print(f"[dry] SELL -> {to}"); sent += 1
            else:
                r = ms._send(to, SELL_SUBJECT, body)
                if r.get("ok"): sent += 1
                print(f"SELL {to}: {r.get('ok')}")
        if side in ("buy", "both"):
            body = BUY_BODY.format(v=vertical)
            if dry: print(f"[dry] BUY  -> {to}"); sent += 1
            else:
                r = ms._send(to, BUY_SUBJECT, body)
                if r.get("ok"): sent += 1
                print(f"BUY  {to}: {r.get('ok')}")
    print(f"outreach done: {sent} emails ({side}) to {vertical} businesses")

if __name__ == "__main__":
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("--side", default="both", choices=["sell","buy","both"])
    a.add_argument("--vertical", default="logistics")
    a.add_argument("--limit", type=int, default=5)
    a.add_argument("--dry", action="store_true")
    a.add_argument("--copy", default="", help="campaign JSON from advertising_agent")
    a.add_argument("--storm", action="store_true", help="include NWS storm leads")
    args = a.parse_args()
    run(args.side, args.vertical, args.limit, args.dry, args.copy, args.storm)
