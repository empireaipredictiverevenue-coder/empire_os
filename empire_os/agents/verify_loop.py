#!/usr/bin/env python3
"""Continuous self-verification loop.

Proves the revenue surface stays correct without human scripts:
  - pricing endpoint returns all SKUs with T4 + setup fees + specs
  - titanium (T4) delivery returns the titanium flags
  - seat lead-prices match the mandated table
  - health responds fast (no worker saturation)

Runs forever (systemd). On drift it logs + fires a Telegram money-channel alert.
Ad-hoc `hermes-verify-*.py` one-shot scripts are replaced by this loop.
"""
import os, sys, time, json, sqlite3, urllib.request, urllib.error

sys.path.insert(0, "/root/empire_os")
from empire_os.auto_onboard import TIER_RATES

BASE = "http://127.0.0.1:8081"
DB = "/root/empire_os/empire_os.db"
INTERVAL = int(os.environ.get("VERIFY_INTERVAL", "300"))  # 5 min

EXPECT_SETUP = {
    "empire_leads_engine": 10000, "hermes_framework": 8000,
    "opencut_studio": 5000, "empire_templates": 3000, "marketingskills": 3000,
}
EXPECT_SEATS = {"bronze": 15.0, "silver": 25.0, "gold": 45.0, "platinum": 90.0}
T4_FLAGS = ("dedicated_monitoring", "priority_support", "api_webhook_ready")


def _get(p):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=20).read())


def _post(p, d):
    r = urllib.request.Request(BASE + p, data=json.dumps(d).encode(),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=20).read())


def telegram_alert(msg):
    # route through gateway so TELEGRAM_MONEY_ONLY gate applies
    try:
        import empire_os.hermes_gateway as g
        g._telegram_send(msg, revenue=False)
    except Exception:
        pass


def check():
    fails = []
    # pricing + specs + T4 + setup
    pr = _get("/v1/products/pricing").get("pricing", {})
    if len(pr) < 11:
        fails.append(f"pricing returned {len(pr)} SKUs (<11)")
    for sku, x in pr.items():
        t = x.get("tiers", {})
        if not t.get("T4_titanium"):
            fails.append(f"{sku}: no T4_titanium")
        if not x.get("features"):
            fails.append(f"{sku}: no features")
    for sku, fee in EXPECT_SETUP.items():
        if pr.get(sku, {}).get("setup_fee_usdc") != fee:
            fails.append(f"{sku}: setup {pr.get(sku, {}).get('setup_fee_usdc')}!={fee}")
        if not pr.get(sku, {}).get("whitelabel"):
            fails.append(f"{sku}: whitelabel flag missing")
    # detail endpoint
    det = _get("/v1/products/empire_leads_engine")
    if det.get("setup_fee_usdc") != 10000 or not det.get("features"):
        fails.append("detail endpoint wrong")
    # T4 delivery
    c = sqlite3.connect(DB, timeout=5)
    c.execute("DELETE FROM si_subscription WHERE tenant_id='verify_loop_t4'")
    c.execute("INSERT INTO si_subscription (subscription_id,tenant_id,plan,"
              "billing_cycle,seats,price_cents,status,payment_method,started_at,"
              "current_period_end,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              ("vl_t4", "verify_loop_t4", "sku_satellite_idle_watch", "monthly", 4,
               299900, "active", "usdc", "2026-07-16T00:00:00Z",
               "2026-08-16T00:00:00Z", "2026-07-16T00:00:00Z"))
    c.commit(); c.close()
    body = _post("/v1/satellite/idle-watch/report",
                 {"tenant": "verify_loop_t4", "tier": 4}).get("report", {})
    if body.get("tier") != "T4 (titanium)":
        fails.append(f"T4 delivery tier={body.get('tier')}")
    for fl in T4_FLAGS:
        if not body.get(fl):
            fails.append(f"T4 delivery missing {fl}")
    c = sqlite3.connect(DB, timeout=5)
    c.execute("DELETE FROM si_subscription WHERE tenant_id='verify_loop_t4'")
    c.commit(); c.close()
    # seat prices
    for t, p in EXPECT_SEATS.items():
        if TIER_RATES.get(t, (0,))[0] != p:
            fails.append(f"seat {t}={TIER_RATES.get(t,(0,))[0]}!={p}")
    # health timing
    t0 = time.time(); h = _get("/health"); htime = round(time.time() - t0, 2)
    if h.get("status") != "online":
        fails.append("health not online")
    if htime > 5:
        fails.append(f"health slow {htime}s (worker saturation)")
    return fails, htime


def main():
    print(f"[verify_loop] started, interval={INTERVAL}s, base={BASE}", flush=True)
    import urllib.parse  # for alert quoting
    last_ok = True
    while True:
        try:
            fails, htime = check()
        except Exception as e:
            fails, htime = [f"CHECK ERROR: {type(e).__name__}: {str(e)[:80]}"], 0
        if fails:
            msg = "⚠️ VERIFY LOOP DRIFT:\n" + "\n".join(" - " + f for f in fails)
            print(msg, flush=True)
            telegram_alert(msg)
            last_ok = False
        else:
            if not last_ok:
                print(f"[verify_loop] RECOVERED — all green (health {htime}s)", flush=True)
                telegram_alert("✅ Empire verify loop: all green again")
                last_ok = True
            else:
                print(f"[verify_loop] ok — {len(_get('/v1/products/pricing').get('pricing',{}))} SKUs, T4 live, health {htime}s", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
