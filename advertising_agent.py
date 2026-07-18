#!/usr/bin/env python3
"""
Empire OS — Advertising Agent (BOTH sides of the business).
Runs the 9-step advertising-skills pipeline (avatar -> offer -> schwartz ->
mechanism -> angle -> creative -> conversion -> objection -> generic-killer)
via Hermes brain (tencent/hy3:free) to produce scroll-stopping ad copy for our products,
then pairs it with empire-leads real prospects and feeds outreach.py (Resend).

Pipeline source: /root/advertising-skills (realkimbarrett, MIT).
Lead engine: /root/empire-leads (zero-Chrome, Overpass + NWS storm).
Copy cleanup: /root/EmpireHermes/skills/creative/humanizer + /root/unslop.

Usage:
  python advertising_agent.py --product vertical_feed --niche logistics --side both --send
  python advertising_agent.py --product aeo_generator --niche roofing --side sell --dry
"""
import sys, os, json, argparse, subprocess
sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire-leads")
sys.path.insert(0, "/root/advertising-skills")

# Brain: use Hermes brain (tencent/hy3 via OpenRouter) when a key is present.
# Otherwise copy is authored externally (the agent IS the brain) and loaded from file.
import os as _os
_OPENROUTER_KEY = _os.environ.get("OPENROUTER_API_KEY", "")
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_HERMES_MODEL = "tencent/hy3:free"

PRODUCTS = {
    "vertical_feed":   "Real-time vertical lead-intent firehose (permits, jobs, business triggers).",
    "aeo_generator":   "AEO pages that make your business the answer AI engines cite.",
    "aeo_monitor":     "Track where AI engines cite (or ignore) your business.",
    "aeo_refresh":     "Monthly re-optimization of your AEO pages from live search signal.",
    "business_dir":    "Verified business directory + trust layer for AI agents.",
    "verify_business": "KYC-lite verification so agents trust your business.",
    "settlement_gateway":"USDC settlement rail — pay/receive without Stripe or banks.",
    "synthetic_agent": "Your own self-learning agent (white-label).",
    "agent_copilot":   "Let foreign agents route + settle through your stack.",
}

def _llm(prompt, sys=None, temp=0.7):
    """Hermes brain (tencent/hy3 via OpenRouter). Falls back to file-authored copy."""
    if _OPENROUTER_KEY:
        try:
            import urllib.request, json as _json
            body = {
                "model": _HERMES_MODEL,
                "messages": [
                    {"role": "system", "content": sys or "You are a direct-response copywriter."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temp,
            }
            req = urllib.request.Request(
                _OPENROUTER_URL, data=_json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {_OPENROUTER_KEY}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return _json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM error: {e}]"
    # No key: the agent (Hermes) authors copy — return a marker so run_pipeline
    # knows to load external copy. Caller handles fallback.
    return None

def avatar(niche):
    return _llm(
        f"For a B2B buyer in the '{niche}' vertical, extract the ideal customer avatar: "
        f"role, company size, daily pains, what keeps them up at night, where they hang out online. "
        f"Bullet form, 5 items, no fluff.",
        sys="You are a direct-response avatar researcher. Be specific, named, real.")

def offer(product, niche):
    desc = PRODUCTS.get(product, product)
    return _llm(
        f"Product: {product} — {desc}\nVertical: {niche}\n"
        f"Extract the core offer: the single outcome, the proof, the risk-reversal (guarantee), the price anchor. "
        f"Bullet form.",
        sys="You are an offer architect. One clear promise, proof, and a no-brainer CTA.")

def schwartz(product, niche):
    # 8 of Schwartz's 10 life motivators most relevant to B2B
    return _llm(
        f"Map our {product} offer for {niche} buyers to Schwartz awareness triggers. "
        f"Pick the top 3 from: survival/safety, belonging, achievement, efficiency, fear of loss, "
        f"convenience, curiosity, ambition. For each: the trigger + the angle it justifies.",
        sys="You are a persuasion psychologist. Map product to deep human motivators.")

def mechanism(product, niche):
    return _llm(
        f"What is the UNIQUE MECHANISM that makes {product} actually work for {niche}? "
        f"Not a feature — the proprietary 'how'. 2 sentences, concrete.",
        sys="You are a copy chief. The mechanism is the 'secret sauce' that makes the claim believable.")

def angle(product, niche, mech):
    return _llm(
        f"From this mechanism: '{mech}'\nGenerate 5 distinct ad angles for {niche} buyers. "
        f"Each angle = a different hook frame (contrarian, insider, cost-of-inaction, social-proof, curiosity).",
        sys="You are an ad-angle multiplier. Each angle opens a different cognitive door.")

def creative(product, niche, angle):
    return _llm(
        f"Write 3 scroll-stopping ad creatives for {product} to {niche} buyers using this angle:\n{angle}\n"
        f"Each: HOOK (first 3 sec), BODY (2-3 lines), CTA. Pattern-interrupt, no generic openings.",
        sys="You design for attention. First 3 seconds win. No 'Unlock'/'Dive in'/'Leverage'.")

def conversion(product, niche):
    return _llm(
        f"Build a conversion path for {product} -> {niche} buyer: landing message, 3-email sequence theme, "
        f"objection each email kills, and the close. Concrete.",
        sys="You are a conversion-path builder. Map attention to action.")

def objection(product, niche):
    return _llm(
        f"Top 3 objections a {niche} buyer has about {product}, and a crisp rebuttal for each.",
        sys="You are an objection crusher. Name the fear, kill it with proof.")

def generic_kill(copy):
    # uses humanizer + unslop principles (see /root/EmpireHermes/skills/creative/humanizer)
    return _llm(
        f"Rewrite this ad copy to remove ALL generic language, AI-isms, and corporate sludge. "
        f"Make it sound like a sharp human wrote it. Keep the offer. Vary sentence length. No em-dashes, "
        f"no 'leverage/enhance/delve/robust/seamless', no rule-of-three padding.\n\nCOPY:\n{copy}",
        sys="You are a humanizer/de-slopper. Strip AI tells. Add a pulse.")

def run_pipeline(product, niche, copy_override=None):
    """If copy_override (dict) is given, use it (the agent/Hermes authored it).
    Else call _llm for each stage (needs OPENROUTER_API_KEY)."""
    if copy_override:
        print(f"[ad-agent] using Hermes-authored copy for {product}/{niche}")
        copy_override["product"] = product
        copy_override["niche"] = niche
        return copy_override
    print(f"[ad-agent] pipeline start: {product} / {niche}")
    av = avatar(niche); print("  avatar ✓")
    of = offer(product, niche); print("  offer ✓")
    sc = schwartz(product, niche); print("  schwartz ✓")
    me = mechanism(product, niche); print("  mechanism ✓")
    an = angle(product, niche, me); print("  angle ✓")
    cr = creative(product, niche, an); print("  creative ✓")
    cv = conversion(product, niche); print("  conversion ✓")
    ob = objection(product, niche); print("  objection ✓")
    clean = generic_kill(cr + "\n\n" + cv) if cr and cv else f"[copy-authoring-pending: {product}/{niche}]"
    print("  generic-kill ✓")
    return {
        "product": product, "niche": niche,
        "avatar": av, "offer": of, "schwartz": sc, "mechanism": me,
        "angle": an, "creative": cr, "conversion": cv, "objection": ob,
        "final_copy": clean,
    }

def get_prospects(niche, limit=10, storm=False):
    """Pull REAL prospects from empire-leads (Overpass OSM + optional NWS storm)."""
    import time
    def _retry(discover, *a, **kw):
        for i in range(4):
            try:
                return discover(*a, **kw)
            except Exception:
                if i == 3: raise
                time.sleep(2 ** i * 5)
    try:
        from empire_leads.engine import discover
        srcs = ["nws", "overpass"] if storm else ["overpass"]
        r = _retry(discover, niche, near="Phoenix, AZ", radius=25000, limit=limit, sources=srcs)
        leads = r.leads if hasattr(r, "leads") else []
        if not leads and niche != "roofing":
            # Overpass tags vary; roofing is a reliable fallback vertical
            r2 = _retry(discover, "roofing", near="Phoenix, AZ", radius=25000, limit=limit, sources=srcs)
            leads = r2.leads if hasattr(r2, "leads") else []
        out = []
        for l in leads[:limit]:
            out.append({"name": l.name, "email": l.email or "", "phone": l.phone or "",
                        "website": l.website or "", "city": l.city or "", "state": l.state or ""})
        return out
    except Exception as e:
        return [{"error": str(e)}]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="vertical_feed")
    ap.add_argument("--niche", default="logistics")
    ap.add_argument("--side", choices=["sell","buy","both"], default="both")
    ap.add_argument("--storm", action="store_true", help="include NWS storm-triggered leads")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--dry", action="store_true", help="build copy + show, do not send")
    ap.add_argument("--send", action="store_true", help="send via outreach.py (Resend)")
    ap.add_argument("--copy", default="", help="path to Hermes-authored copy JSON (override LLM)")
    a = ap.parse_args()

    copy_override = None
    if a.copy and os.path.exists(a.copy):
        try:
            copy_override = json.load(open(a.copy))
            print(f"[ad-agent] loaded authored copy: {a.copy}")
        except Exception as e:
            print(f"[ad-agent] copy load failed ({e}); falling back to LLM")

    pipe = run_pipeline(a.product, a.niche, copy_override)
    pros = get_prospects(a.niche, a.limit, a.storm)
    print(f"\n[ad-agent] prospects found: {len([p for p in pros if 'error' not in p])}")

    # write the campaign asset
    os.makedirs("/root/feedback/campaigns", exist_ok=True)
    camp = {"pipeline": pipe, "prospects": pros, "side": a.side, "storm": a.storm}
    fn = f"/root/feedback/campaigns/{a.product}_{a.niche}.json"
    with open(fn, "w") as f: json.dump(camp, f, indent=2)
    print(f"[ad-agent] campaign saved: {fn}")

    print("\n========== FINAL AD COPY ==========")
    print(pipe["final_copy"][:1200])
    print("===================================\n")

    if a.send and not a.dry:
        # feed outreach.py with the crafted copy + real prospects
        cmd = [sys.executable, "outreach.py", "--side", a.side, "--vertical", a.niche,
               "--limit", str(a.limit), "--copy", fn]
        if a.storm: cmd.append("--storm")
        print("[ad-agent] launching outreach.py ...")
        subprocess.run(cmd)
    elif a.dry:
        print("[ad-agent] DRY mode — no send. Use --send to dispatch via Resend.")

if __name__ == "__main__":
    main()
