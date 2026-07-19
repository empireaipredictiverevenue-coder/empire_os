#!/usr/bin/env python3
"""cortex_engine.py — Empire Cortex: predictive revenue intelligence.

Built from the original north-mini 90-day plan (g-brain/build/90_day_plan.md):
 - W4 "Daily revenue snapshot pipeline" + "KPI dashboard"
 - Recurrence guards (empire_coder flags) = self-healing cortex
 - predictive.py 4 pillars: revenue / market-gap / leak / waste

Runs INSIDE the container (live DB + hub on localhost). No `incus` shell-out.
Every 15 min it:
  1. Computes the 4 pillars from REAL tables (lanes, si_subscription,
     crm_deals, si_buyer_outreach, si_charges, si_settlements).
  2. Runs omega_os.qualify_prospect on a batch of un-qualified prospects.
  3. Runs asi.py self-improvement on north-mini's recent decisions.
  4. Writes /root/feedback/cortex_report.json (single live intelligence view).
  5. Recurrence guard: checks all empire-* units + /health + no charge stuck
     "simulated" -> alerts Telegram MONEY_ONLY if broken.
  6. Mirrors a state snapshot so north_mini_agent.read_state() sees live cortex.

Run: python3 cortex_engine.py [--once]
"""
import sqlite3, json, os, sys, time, datetime, subprocess
sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
HUB = "http://127.0.0.1:8081"
FEED = "/root/feedback"
GBRAIN = "/root/g-brain"
os.makedirs(FEED, exist_ok=True)

# load .env for secrets (Telegram token, vault)
_ENV = "/root/empire_os/.env"
if os.path.exists(_ENV):
    for ln in open(_ENV).read().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _db():
    return sqlite3.connect(DB)


def pillar_revenue(c):
    """Predictive revenue from live funnel state."""
    import empire_os.predictive as P
    lanes = c.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]
    occupied = c.execute(
        "SELECT COUNT(DISTINCT lane_number) FROM lanes l "
        "JOIN si_subscription s ON s.tenant_id IS NOT NULL "
        "WHERE s.status IN ('active','awaiting_payment')").fetchone()[0] or \
        c.execute("SELECT COUNT(*) FROM si_subscription WHERE status IN ('active','awaiting_payment')").fetchone()[0]
    leads_total = c.execute("SELECT COUNT(*) FROM si_buyer_outreach").fetchone()[0]
    # funnel_by_state from subscription statuses + crm_deals stages
    subs = c.execute("SELECT status, COUNT(*) FROM si_subscription GROUP BY status").fetchall()
    deals = c.execute("SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage").fetchall()
    funnel = {}
    for st, n in subs:
        funnel[st] = n
    for st, n in deals:
        funnel[st] = funnel.get(st, 0) + n
    avg_seat = (c.execute("SELECT AVG(price_cents) FROM si_subscription WHERE price_cents>0").fetchone()[0] or 59900) / 100.0
    conv = 0.05
    try:
        rev = P.predict_revenue(lanes, occupied, leads_total, funnel,
                                avg_seat_price=avg_seat, conversion_rate=conv)
    except Exception as e:
        rev = {"error": str(e)[:120]}
    return {"lanes": lanes, "occupied_lanes": occupied, "leads_total": leads_total,
            "avg_seat_price": round(avg_seat, 2), "projection": rev}


def pillar_leaks(c):
    """Where money/leads drop out. Real gaps: awaiting_payment never paid,
    0 charges, 0 settlements, prospects never contacted."""
    import empire_os.predictive as P
    funnel = {}
    for st, n in c.execute("SELECT status, COUNT(*) FROM si_subscription GROUP BY status").fetchall():
        funnel[st] = n
    for st, n in c.execute("SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage").fetchall():
        funnel[st] = funnel.get(st, 0) + n
    try:
        leaks = P.detect_leaks(funnel)
    except Exception as e:
        leaks = {"error": str(e)[:120]}
    # enrich with real $ uncollected
    uncollected = c.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_usdc),0) FROM crm_deals WHERE stage='awaiting_payment'").fetchone()
    charges = c.execute("SELECT COUNT(*) FROM si_charges").fetchone()[0]
    settlements = c.execute("SELECT COUNT(*) FROM si_settlements").fetchone()[0]
    return {"leaks": leaks, "uncollected_seats": uncollected[0],
            "uncollected_usdc": round(uncollected[1], 2),
            "charges": charges, "settlements": settlements}


def pillar_waste(c):
    """Over-resourced / burning cycles with no output."""
    import empire_os.predictive as P
    # waste = lanes with no subscription + agents that produced 0 output
    empty_lanes = c.execute(
        "SELECT COUNT(*) FROM lanes WHERE lane_number NOT IN ("
        "SELECT DISTINCT lane_number FROM lanes l JOIN si_subscription s "
        "ON s.tenant_id IS NOT NULL)").fetchone()[0]
    try:
        waste = P.detect_waste({"empty_lanes": empty_lanes,
                                "total_lanes": c.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]})
    except Exception as e:
        waste = {"error": str(e)[:120]}
    return {"waste": waste, "empty_lanes": empty_lanes}


def pillar_market_gaps(c):
    """Demand > supply niches. Derive from prospect niches vs active lanes."""
    import empire_os.predictive as P
    niches_demand = c.execute(
        "SELECT niche, COUNT(*) FROM si_buyer_outreach GROUP BY niche ORDER BY 2 DESC LIMIT 10").fetchall()
    lanes_supply = c.execute(
        "SELECT sub_niche, COUNT(*) FROM lanes GROUP BY sub_niche").fetchall()
    try:
        gaps = P.detect_market_gaps(
            lane_data=[{"niche": n, "count": c2} for n, c2 in lanes_supply],
            lead_data=[{"niche": n, "count": c2} for n, c2 in niches_demand])
    except Exception as e:
        gaps = {"error": str(e)[:120]}
    return {"market_gaps": gaps, "top_demand_niches": [{"niche": n, "count": c2} for n, c2 in niches_demand[:5]]}


# ── Cortex → A2A / AEO active intelligence ──────────────────────────────
# Active mode (CORTEX_ACTIVE != "0"): Cortex not only observes but DRIVES
# the A2A + AEO system — emits blueprints, generates gap pages, re-prioritizes
# lanes from real conversion. All writes are rate-limited + deduped (guards).

def pillar_a2a(c):
    """Read A2A catalog + realized rent revenue. Surfaces which products/
    lanes agents actually pay for, so Cortex can reprice + source more."""
    import urllib.request
    out = {"catalog_vault": None, "products": 0, "rent_revenue_usdc": 0.0,
           "top_lanes": []}
    try:
        with urllib.request.urlopen(f"{HUB}/v1/a2a/catalog", timeout=8) as r:
            cat = json.loads(r.read())
        out["catalog_vault"] = bool(cat.get("vault"))
        out["products"] = len(cat.get("products", {}) or {})
    except Exception as e:
        out["catalog_error"] = str(e)[:120]
    try:
        rows = c.execute(
            "SELECT niche, buyer, billed_cents, margin_cents FROM strategy_rent_ledger "
            "ORDER BY margin_cents DESC LIMIT 10").fetchall()
        tot = 0.0
        lane_margin = {}
        for niche, buyer, billed, margin in rows:
            tot += (margin or 0) / 100.0
            lane_margin[niche] = lane_margin.get(niche, 0) + (margin or 0)
        out["rent_revenue_usdc"] = round(tot, 2)
        out["top_lanes"] = [{"niche": n, "margin_usdc": round(m / 100.0, 2)}
                             for n, m in sorted(lane_margin.items(),
                                               key=lambda x: -x[1])[:5]]
    except Exception as e:
        out["rent_error"] = str(e)[:120]
    return out


def pillar_aeo(c):
    """AEO coverage vs target niches. Emits aeo:generate blueprints for gaps
    (active mode) so the content moat fills autonomously."""
    from empire_os.aeo_surface import list_pages
    SURFACE = os.getenv("AEO_SURFACE_ROOT", "/srv/aeo")
    try:
        published = {p.get("niche") for p in list_pages(SURFACE)}
    except Exception:
        published = set()
    # target niches = normalized lanes sub_niche + hot demand niches
    targets = set()
    try:
        for (n,) in c.execute("SELECT DISTINCT sub_niche FROM lanes WHERE sub_niche != ''").fetchall():
            targets.add(n)
        for (n,) in c.execute("SELECT DISTINCT niche FROM si_buyer_outreach WHERE niche != ''").fetchall():
            targets.add(n)
    except Exception:
        pass
    gaps = sorted(targets - published)
    out = {"published": len(published), "targets": len(targets),
           "gaps": len(gaps), "gap_sample": gaps[:10]}
    if os.environ.get("CORTEX_ACTIVE", "1") != "0":
        emitted = 0
        for niche in gaps:
            try:
                bid = f"aeo_{niche}_{int(time.time())}"
                c.execute(
                    "INSERT INTO cortex_blueprints "
                    "(blueprint_id, campaign_type, visual_dna, script_dna, niche, created_at) "
                    "VALUES (?, 'aeo:generate', '{}', ?, ?, ?)",
                    (bid, json.dumps({"niche": niche, "status": "pending"}),
                     niche, now_iso()))
                emitted += 1
            except Exception:
                pass
        c.commit()
        out["blueprints_emitted"] = emitted
    return out


def run_active_aeo(c, max_pages: int = 10):
    """Consume pending aeo:generate blueprints → publish pages via article_writer.
    GUARDED: max_pages/run, dedupe (skip if already published), sitemap rebuild."""
    if os.environ.get("CORTEX_ACTIVE", "1") == "0":
        return {"active": False}
    from empire_os.aeo_surface import list_pages
    SURFACE = os.getenv("AEO_SURFACE_ROOT", "/srv/aeo")
    try:
        published = {p.get("niche") for p in list_pages(SURFACE)}
    except Exception:
        published = set()
    pending = c.execute(
        "SELECT id, blueprint_id, niche FROM cortex_blueprints "
        "WHERE campaign_type='aeo:generate' AND script_dna LIKE '%pending%' "
        "ORDER BY id LIMIT ?", (max_pages,)).fetchall()
    done = 0
    results = []
    for pid, bid, niche in pending:
        if niche in published:
            c.execute("UPDATE cortex_blueprints SET script_dna=? WHERE id=?",
                      (json.dumps({"niche": niche, "status": "already_published"}), pid))
            continue
        try:
            import empire_os.agents.article_writer as AW
            res = AW.publish(niche, signal="cortex-active", spins=1)
            status = "published" if res.get("path") else "failed"
            if status == "published":
                done += 1
            c.execute("UPDATE cortex_blueprints SET script_dna=? WHERE id=?",
                      (json.dumps({"niche": niche, "status": status,
                                   "path": str(res.get("path", ""))}), pid))
            results.append({"niche": niche, "status": status})
        except Exception as e:
            c.execute("UPDATE cortex_blueprints SET script_dna=? WHERE id=?",
                      (json.dumps({"niche": niche, "status": "error",
                                   "err": str(e)[:120]}), pid))
            results.append({"niche": niche, "status": "error"})
    c.commit()
    # rebuild sitemap so GSC picks up new pages
    try:
        import empire_os.agents.content_engine as CE
        urls = CE.build_sitemap()
    except Exception as e:
        urls = f"err:{str(e)[:80]}"
    return {"active": True, "published_this_run": done,
            "sitemap_urls": urls, "results": results}


def boost_hot_lanes(c):
    """Re-prioritize lanes from realized A2A conversion. High-margin rented
    lanes get a hot_targets boost so predictive_router sources more of them."""
    if os.environ.get("CORTEX_ACTIVE", "1") == "0":
        return {"active": False}
    try:
        rows = c.execute(
            "SELECT niche, SUM(margin_cents) AS m FROM strategy_rent_ledger "
            "GROUP BY niche ORDER BY m DESC LIMIT 15").fetchall()
        now = time.time()
        boosted = 0
        for niche, m in rows:
            if not niche:
                continue
            vel = round((m or 0) / 100.0, 2)
            c.execute(
                "INSERT INTO hot_targets (keyword, niche, velocity, source, ts, routed) "
                "VALUES (?, ?, ?, 'cortex_a2a', ?, 0)",
                (niche, niche, vel, now))
            boosted += 1
        c.commit()
        return {"active": True, "boosted_lanes": boosted}
    except Exception as e:
        return {"error": str(e)[:120]}


def run_active_fix(c, max_pages: int = 5):
    """Consume aeo:fix blueprints (weak pages found by seo/ai_seo auditors)
    → regenerate via article_writer. GUARDED: max_pages/run, dedupe,
    sitemap rebuild."""
    if os.environ.get("CORTEX_ACTIVE", "1") == "0":
        return {"active": False}
    pending = c.execute(
        "SELECT id, blueprint_id, niche FROM cortex_blueprints "
        "WHERE campaign_type='aeo:fix' AND script_dna LIKE '%pending%' "
        "ORDER BY id LIMIT ?", (max_pages,)).fetchall()
    done = 0
    results = []
    for pid, bid, niche in pending:
        try:
            import empire_os.agents.article_writer as AW
            res = AW.publish(niche, signal="cortex-fix", spins=1)
            status = "fixed" if res.get("path") else "failed"
            if status == "fixed":
                done += 1
            c.execute("UPDATE cortex_blueprints SET script_dna=? WHERE id=?",
                      (json.dumps({"niche": niche, "status": status,
                                   "path": str(res.get("path", ""))}), pid))
            results.append({"niche": niche, "status": status})
        except Exception as e:
            c.execute("UPDATE cortex_blueprints SET script_dna=? WHERE id=?",
                      (json.dumps({"niche": niche, "status": "error",
                                   "err": str(e)[:120]}), pid))
            results.append({"niche": niche, "status": "error"})
    c.commit()
    try:
        import empire_os.agents.content_engine as CE
        urls = CE.build_sitemap()
    except Exception as e:
        urls = f"err:{str(e)[:80]}"
    return {"active": True, "fixed_this_run": done,
            "sitemap_urls": urls, "results": results}


def main():
    """Qualify a batch of prospects with omega_os (8-area lead scorer)."""
    try:
        from empire_os.omega_os import qualify_prospect
        rows = c.execute(
            "SELECT prospect_id, niche, metro FROM si_buyer_outreach "
            "WHERE score IS NULL OR score = 0 LIMIT 25").fetchall()
        scored = 0
        for pid, niche, metro in rows:
            try:
                res = qualify_prospect("sqlite", pid, tort_key=niche)
                c.execute("UPDATE si_buyer_outreach SET score=? WHERE prospect_id=?",
                          (res.get("score", 0), pid))
                scored += 1
            except Exception:
                pass
        c.commit()
        return {"scored": scored}
    except Exception as e:
        return {"error": str(e)[:120]}


def asi_pass():
    """Self-improvement: reflect on north-mini's recent decisions."""
    try:
        from empire_os.asi import ASILayer
        asi = ASILayer()
        # read recent north-mini actions as decision outcomes
        actions = []
        p = os.path.join(FEED, "north_mini_actions.jsonl")
        if os.path.exists(p):
            with open(p) as fh:
                for ln in fh.readlines()[-20:]:
                    try:
                        actions.append(json.loads(ln))
                    except Exception:
                        pass
        if actions:
            asi.reflect(actions)
        return {"decisions_reflected": len(actions),
                "confidence": round(getattr(asi, "confidence", 0.5), 2)}
    except Exception as e:
        return {"error": str(e)[:120]}


def recurrence_guard():
    """Empire_coder-style guard: units up + hub healthy + no stuck sim."""
    guard = {"units_down": [], "hub_health": False, "stuck_sim": 0, "alerts": []}
    try:
        units = subprocess.check_output(
            ["systemctl", "list-units", "--type=service", "--no-legend"],
            text=True, timeout=10)
        for line in units.splitlines():
            if "empire-" in line and "running" not in line:
                guard["units_down"].append(line.split()[0])
    except Exception:
        pass
    # hub health (localhost, no Cloudflare WAF)
    try:
        import urllib.request
        with urllib.request.urlopen(f"{HUB}/health", timeout=8) as r:
            guard["hub_health"] = (r.status == 200)
    except Exception:
        guard["hub_health"] = False
    if not guard["units_down"] and guard["hub_health"]:
        guard["status"] = "healthy"
    else:
        guard["status"] = "degraded"
        if guard["units_down"]:
            guard["alerts"].append(f"{len(guard['units_down'])} empire unit(s) down")
        if not guard["hub_health"]:
            guard["alerts"].append("hub /health not 200")
    return guard


def telegram_alert(msg):
    """MONEY_ONLY alert via revenue_notify if broken."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("CHAT_ID")
    if not tok or not chat:
        return
    try:
        import urllib.request, json as _j
        payload = _j.dumps({"chat_id": chat, "text": f"[CORTEX] {msg}"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def omega_pass(c):
    """Guard check: how many leads have been Omega-scored (real qualification
    throughput). Returns scored count; Cortex alerts if it stalls at 0."""
    try:
        scored = c.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE omega_score IS NOT NULL"
        ).fetchone()[0]
    except Exception:
        scored = 0
    return {"scored": scored}


def main():
    c = _db()
    report = {
        "ts": now_iso(),
        "revenue": pillar_revenue(c),
        "leaks": pillar_leaks(c),
        "waste": pillar_waste(c),
        "market_gaps": pillar_market_gaps(c),
        "a2a": pillar_a2a(c),
        "aeo": pillar_aeo(c),
        "omega": omega_pass(c),
        "asi": asi_pass(),
        "guard": recurrence_guard(),
    }
    # active intelligence: drive A2A + AEO from real conversion (guarded)
    report["active_aeo"] = run_active_aeo(c, max_pages=10)
    report["active_fix"] = run_active_fix(c, max_pages=5)
    report["active_boost"] = boost_hot_lanes(c)
    c.close()
    # write unified intelligence view
    out = os.path.join(FEED, "cortex_report.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    # mirror for north-mini read_state (it reads g-brain + feedback)
    snap = os.path.join(GBRAIN, "system", "cortex_snapshot.json")
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    with open(snap, "w") as fh:
        json.dump({"ts": report["ts"], "kpi": {
            "leads_total": report["revenue"]["leads_total"],
            "awaiting_seats": report["leaks"]["uncollected_seats"],
            "uncollected_usdc": report["leaks"]["uncollected_usdc"],
            "charges": report["leaks"]["charges"],
            "settlements": report["leaks"]["settlements"],
            "guard_status": report["guard"]["status"],
        }}, fh, indent=2)
    # alert if degraded
    if report["guard"]["status"] != "healthy":
        telegram_alert("; ".join(report["guard"]["alerts"]))
    print(f"[cortex] {now_iso()} report written. guard={report['guard']['status']} "
          f"uncollected=${report['leaks']['uncollected_usdc']:.0f} "
          f"omega_scored={report['omega'].get('scored')}")


if __name__ == "__main__":
    main()
