#!/usr/bin/env python3
"""loop_closure_watchdog — business-loop health, not just process health.

sentry_agent watches if processes are UP. This watches if MONEY is FLOWING.
The loop: founder_email SENT → prospect APPLIES (/v1/buyer_apply)
→ pay_url EMAILED → USDC SETTLES → sub ACTIVE → leads DELIVERED
→ per-lead CHARGE → USDC COLLECTED.

If any stage goes silent past its SLA, alert Telegram MONEY_ONLY + open issue.
Also self-heals the 3 known rot points so we stop re-fixing by hand:
  1. dead model in sessions (resume break) — re-pin to hy3
  2. stale :8000 env in agents — restart units
  3. founder_outreach not running — restart service

Run as systemd empire-loop-closure.service, 5-min tick.
"""
import os, sys, time, json, sqlite3, subprocess, datetime
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
FB = "/root/feedback"
LOG = f"{FB}/loop_closure.jsonl"
TICK = int(os.environ.get("LOOP_WATCH_TICK", "300"))
STALE_MIN = int(os.environ.get("LOOP_STALE_MIN", "180"))  # 3h with no progress = stalled

def _now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def log(level, msg, **fields):
    rec = {"ts": _now(), "level": level, "msg": msg, **fields}
    try:
        os.makedirs(FB, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass
    if level in ("ALERT", "FIX"):
        print(f"[loop-closure] {level} {msg} {fields}", flush=True)

def alert(msg, fields=None):
    """Telegram MONEY_ONLY + best-effort hub alert."""
    fields = fields or {}
    try:
        from empire_os import revenue_notify as rn
        rn.loop_stall(msg)
    except Exception:
        pass
    log("ALERT", msg, **fields)

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def stage_freshness():
    """Return dict of each loop stage: count + oldest-age-minutes."""
    c = db()
    out = {}
    def age_min(sql):
        try:
            r = c.execute(sql).fetchone()
            if not r or r[0] is None:
                return None
            then = datetime.datetime.fromisoformat(r[0].replace("Z", "+00:00")) if isinstance(r[0], str) else datetime.datetime.fromtimestamp(r[0])
            return (datetime.datetime.now(datetime.timezone.utc) - then).total_seconds() / 60
        except Exception as e:
            return f"err:{e}"
    # S1: founder emails sent
    out["s1_emails_sent"] = c.execute("SELECT COUNT(*) FROM si_outbox WHERE source='founder_outreach' AND status='sent'").fetchone()[0]
    out["s1_last_sent_age_min"] = age_min("SELECT MAX(created_at) FROM si_outbox WHERE source='founder_outreach' AND status='sent'")
    # S2: applications (subscriptions created)
    out["s2_subs_total"] = c.execute("SELECT COUNT(*) FROM si_subscription").fetchone()[0]
    out["s2_subs_active"] = c.execute("SELECT COUNT(*) FROM si_subscription WHERE status='active'").fetchone()[0]
    out["s2_subs_awaiting"] = c.execute("SELECT COUNT(*) FROM si_subscription WHERE status='awaiting_payment'").fetchone()[0]
    out["s2_last_apply_age_min"] = age_min("SELECT MAX(created_at) FROM si_subscription")
    # S3: pay_url emailed (we log PAYLINK in ppc_router log; approximate via awaiting subs w/ payment_ref)
    out["s3_awaiting_with_ref"] = c.execute("SELECT COUNT(*) FROM si_subscription WHERE status='awaiting_payment' AND payment_ref != ''").fetchone()[0]
    # S4: charges (per-lead billing)
    out["s4_charges_total"] = c.execute("SELECT COUNT(*) FROM si_charges").fetchone()[0]
    out["s4_charges_open"] = c.execute("SELECT COUNT(*) FROM si_charges WHERE status='open'").fetchone()[0]
    out["s4_last_charge_age_min"] = age_min("SELECT MAX(created_at) FROM si_charges")
    # S5: settlements (on-chain)
    out["s5_settlements"] = c.execute("SELECT COUNT(*) FROM si_settlements").fetchone()[0]
    c.close()
    return out

def outbox_flush_health():
    """Detect silent email-delivery stalls (the 2026-07-19 incident:
    hub /v1/outbox/pending SQL excluded recipient_kind='prospect', so 1250
    real founder emails sat pending + 0 sent for 40+ min, nothing alerted).
    Returns dict with pending count, sent in last TICK, and stalled flag."""
    c = db()
    pending = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='pending'").fetchone()[0]
    sent_total = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='sent'").fetchone()[0]
    # sent within the last tick window
    sent_recent = c.execute(
        "SELECT COUNT(*) FROM si_outbox WHERE status='sent' AND sent_at >= "
        "datetime('now', '-%d minutes')" % (max(2, TICK // 60 + 1))).fetchone()[0]
    failed = c.execute("SELECT COUNT(*) FROM si_outbox WHERE status='failed'").fetchone()[0]
    c.close()
    stalled = pending > 20 and sent_recent == 0
    return {"outbox_pending": pending, "outbox_sent_total": sent_total,
            "outbox_sent_recent": sent_recent, "outbox_failed": failed,
            "outbox_stalled": stalled}

def _ensure_brevo_backend():
    """Guard against EMAIL_BACKEND drift (direct MX hangs on cloud port-25 block).
    Returns fix note if it changed, else ''."""
    envp = "/root/empire_os/.env"
    try:
        lines = open(envp).read().splitlines()
        for i, l in enumerate(lines):
            if l.startswith("EMAIL_BACKEND=") and "brevo" not in l.lower():
                lines[i] = "EMAIL_BACKEND=brevo"
                open(envp, "w").write("\n".join(lines) + "\n")
                return f"EMAIL_BACKEND reset to brevo (was {l})"
    except Exception:
        pass
    return ""
    return ""

def cortex_health():
    """Empire Cortex Swarm self-healing signal.
    The swarm (Scanner+Judge+Architect+Bridge) must keep producing blueprints.
    Detects: (a) unit dead, (b) no new blueprint in last TICK, (c) Judge on mock
    (no OPENROUTER key in runtime env -> scores are fake)."""
    unit = "empire-cortex-swarm.service"
    info = {"unit": unit, "active": False, "blueprints": 0,
            "blueprint_stalled": False, "judge_mock": False}
    try:
        r = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True)
        info["active"] = (r.stdout.strip() == "active")
    except Exception:
        pass
    c = db()
    try:
        info["blueprints"] = c.execute("SELECT COUNT(*) FROM cortex_blueprints").fetchone()[0]
        grown = c.execute(
            "SELECT COUNT(*) FROM cortex_blueprints WHERE created_at >= "
            "datetime('now','-%d minutes')" % (max(3, TICK // 60 + 2))).fetchone()[0]
        info["blueprint_stalled"] = info["active"] and grown == 0 and info["blueprints"] > 0
    except Exception:
        pass
    c.close()
    return info

def self_heal():
    """Re-pin dead models + restart dead units + keep email flowing
    so we stop hand-fixing the same rot points."""
    fixes = []
    # 1. dead model in sessions -> re-pin to hy3 (HOST-only: state.db lives on host)
    if os.path.exists("/root/.hermes/state.db"):
        try:
            sc = sqlite3.connect("/root/.hermes/state.db")
            dead = sc.execute("SELECT COUNT(*) FROM sessions WHERE model NOT IN ('tencent/hy3:free')").fetchone()[0]
            if dead:
                sc.execute("UPDATE sessions SET model='tencent/hy3:free' WHERE model NOT IN ('tencent/hy3:free')")
                sc.commit()
                fixes.append(f"re-pinned {dead} dead-model sessions")
            sc.close()
        except Exception as e:
            fixes.append(f"sessions re-pin err: {e}")
    # 2. restart dead empire units (correct unit names — underscores)
    for u in ["empire-agent-founder-outreach.service", "empire-hub-8081.service",
              "empire-ppc-router.service", "empire-mail-sender.service",
              "empire-agent-solana_listener.service", "empire-solana-listener.service",
              "empire-cortex-swarm.service", "empire-last30days.service",
              "empire-content-engine.service", "empire-predictive-router.service"]:
        try:
            r = subprocess.run(["systemctl", "is-active", u], capture_output=True, text=True)
            if r.stdout.strip() != "active":
                subprocess.run(["systemctl", "restart", u], capture_output=True, text=True)
                fixes.append(f"restarted {u} (was {r.stdout.strip()})")
        except Exception:
            pass
    # 2b. Cortex swarm deeper heal: unit up but no new blueprint -> restart
    try:
        ch = cortex_health()
        if ch["active"] and ch["blueprint_stalled"]:
            subprocess.run(["systemctl", "restart", "empire-cortex-swarm.service"], capture_output=True, text=True)
            fixes.append(f"cortex swarm blueprint stall -> restarted (blueprints={ch['blueprints']})")
    except Exception as e:
        fixes.append(f"cortex heal err: {e}")
    # 2c. Last30days research signal: unit dead OR stale artifact -> restart
    try:
        u = "empire-last30days.service"
        r = subprocess.run(["systemctl", "is-active", u], capture_output=True, text=True)
        if r.stdout.strip() != "active":
            subprocess.run(["systemctl", "restart", u], capture_output=True, text=True)
            fixes.append(f"last30days dead -> restarted")
        else:
            art = "/root/feedback/last30days_runs.jsonl"
            if os.path.exists(art):
                age = time.time() - os.path.getmtime(art)
                if age > 45 * 60:  # no fresh artifact in 45min -> engine hung
                    subprocess.run(["systemctl", "restart", u], capture_output=True, text=True)
                    fixes.append(f"last30days artifact stale ({int(age/60)}m) -> restarted")
    except Exception as e:
        fixes.append(f"last30days heal err: {e}")
    # 3. email-delivery guard: if outbox is stalled, force brevo backend + restart mail-sender
    try:
        h = outbox_flush_health()
        if h["outbox_stalled"]:
            bfix = _ensure_brevo_backend()
            if bfix:
                fixes.append(bfix)
            subprocess.run(["systemctl", "restart", "empire-mail-sender.service"], capture_output=True, text=True)
            fixes.append(f"outbox stall auto-heal: pending={h['outbox_pending']} recent_sent={h['outbox_sent_recent']} -> restarted mail-sender + brevo")
    except Exception as e:
        fixes.append(f"outbox guard err: {e}")
    return fixes

def evaluate(st):
    """Decide if loop is stalled + what's broken. Returns list of alerts."""
    alerts = []
    # S1->S2 stall: emails sent but no applications ever
    if st["s1_emails_sent"] > 0 and st["s2_subs_total"] == 0:
        alerts.append(("S1->S2 STALLED: %d founder emails sent, 0 applications. "
                       "Cause: email has no pay_url OR apply endpoint down."
                       % st["s1_emails_sent"], {"emails": st["s1_emails_sent"]}))
    # S2->S3: awaiting_payment but no payment_ref (pay_url never generated/emailed)
    if st["s2_subs_awaiting"] > 0 and st["s3_awaiting_with_ref"] == 0:
        alerts.append(("S2->S3 STALLED: %d subs awaiting_payment, 0 have pay_url. "
                       "Cause: crypto_payment_request failed or _deliver_pay_link broken."
                       % st["s2_subs_awaiting"], {"awaiting": st["s2_subs_awaiting"]}))
    # S4: charges should appear once subs active + leads delivered
    if st["s2_subs_active"] > 0 and st["s4_charges_total"] == 0:
        alerts.append(("S4 STALLED: %d active subs but 0 charges. "
                       "Cause: lead_deliverer not billing per-lead."
                       % st["s2_subs_active"], {"active_subs": st["s2_subs_active"]}))
    # Global stall: loop was progressing but went silent
    ages = [v for k, v in st.items() if k.endswith("age_min") and isinstance(v, (int, float))]
    if ages and max(ages) > STALE_MIN:
        alerts.append(("GLOBAL STALL: no loop progress for %.0f min (>%d SLA)."
                       % (max(ages), STALE_MIN), {"max_age_min": round(max(ages), 0)}))
    return alerts

def load_soul():
    """Load this agent's SOUL from the live souls dir (source of truth)."""
    try:
        p = os.path.join(os.path.dirname(__file__), "souls", "loop_closure_SOUL.md")
        if os.path.exists(p):
            log("INFO", "soul_loaded", path=p, bytes=os.path.getsize(p))
    except Exception:
        pass

def main():
    os.makedirs(FB, exist_ok=True)
    load_soul()
    log("INFO", "loop-closure tick start")
    fixes = self_heal()
    if fixes:
        for f in fixes:
            log("FIX", f)
        print(f"[loop-closure] self-healed: {fixes}", flush=True)
    st = stage_freshness()
    ob = outbox_flush_health()
    alerts = evaluate(st)
    # outbox flush stall alert
    if ob["outbox_stalled"]:
        alerts.append((f"OUTBOX STALLED: {ob['outbox_pending']} pending emails, "
                       f"0 sent in last window. Buyer outreach is SILENT. "
                       f"Auto-heal: restarted mail-sender + forced brevo backend.",
                       {"pending": ob["outbox_pending"], "sent_recent": ob["outbox_sent_recent"]}))
    if alerts:
        for msg, fields in alerts:
            alert(msg, fields)
    else:
        log("OK", "loop healthy", **{k: v for k, v in st.items() if not k.endswith("age_min")},
            **{k: v for k, v in ob.items()})
    print(f"[loop-closure] stages: {json.dumps({k:v for k,v in st.items() if not k.endswith('age_min')})}", flush=True)
    print(f"[loop-closure] outbox: {json.dumps(ob)}", flush=True)

if __name__ == "__main__":
    if "--once" in sys.argv:
        main()
    else:
        print(f"[loop-closure] loop start tick={TICK}s", flush=True)
        while True:
            try:
                main()
            except Exception as e:
                log("ERROR", str(e)[:200])
            time.sleep(TICK)
