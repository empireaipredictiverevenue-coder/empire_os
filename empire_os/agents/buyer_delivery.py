#!/usr/bin/env python3
"""
buyer_delivery.py — Empire OS Lead Delivery Platform (Cortex pillar #3).

Delivers qualified leads to subscribed buyers via WEBHOOK (bypasses the
Resend email quota — the active external blocker). Runs as a pm2 daemon
inside empire-hub, looping every DELIVERY_INTERVAL.

Flow per cycle:
  1. Load active si_subscriptions that have a webhook_url (the delivery path)
  2. For each buyer, find leads matching their niche (metro-agnostic fallback)
     not already delivered to that buyer (dedup via si_outbox)
  3. POST a lead payload to the buyer's webhook_url
  4. Record delivery in si_outbox (dedup key = lead_id+buyer_tenant)

This makes the 84 existing subscriptions meaningful: buyers get real leads
without waiting on email quota. No external deps beyond the hub's db.

Env: DELIVERY_INTERVAL (sec, default 120), DELIVERY_PER_BUYER (leads/cycle, 5)
"""
import os, sys, json, time, sqlite3, urllib.request, urllib.error

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
HUB = "http://127.0.0.1:8081"
DELIVERY_INTERVAL = int(os.environ.get("DELIVERY_INTERVAL", "120"))
DELIVERY_PER_BUYER = int(os.environ.get("DELIVERY_PER_BUYER", "5"))
LOG_PATH = "/root/empire_os/logs/buyer_delivery.jsonl"


def _log(level, msg, **fields):
    import datetime
    from datetime import timezone
    event = {"ts": datetime.datetime.now(timezone.utc).isoformat(), "level": level,
             "msg": msg, **fields}
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass
    print(json.dumps(event), flush=True)


def _conn():
    c = sqlite3.connect(DB)
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    return c


def active_buyers():
    c = _conn()
    rows = c.execute(
        "SELECT s.tenant_id, s.plan, s.niche, s.webhook_url, t.name, t.email "
        "FROM si_subscription s JOIN si_tenant t ON t.tenant_id=s.tenant_id "
        "WHERE s.status='active' AND s.webhook_url IS NOT NULL "
        "AND s.webhook_url != ''").fetchall()
    c.close()
    return rows


def matching_leads(vertical, buyer_tenant, per_buyer):
    c = _conn()
    # match leads whose niche contains the buyer's vertical (roofing -> residential_roofing)
    # dedup: not already delivered to THIS buyer (per-buyer, not global)
    rows = c.execute(
        "SELECT lead_uid, business_name, niche, metro, state, phone, website, "
        "icp_score FROM crm_leads "
        "WHERE niche LIKE ? AND lead_uid NOT IN ("
        "  SELECT lead_id FROM si_outbox WHERE buyer_tenant=?) "
        "LIMIT ?",
        (f"%{vertical}%", buyer_tenant, per_buyer)).fetchall()
    c.close()
    return rows


def post_webhook(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()[:160]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]
    except Exception as e:
        return 0, str(e)[:120]


def deliver_once():
    buyers = active_buyers()
    if not buyers:
        _log("INFO", "no_active_buyers_with_webhook")
        return 0
    total = 0
    for b in buyers:
        niche = b["niche"] or b["plan"].replace("lane_", "")  # vertical from apply, fallback to tier
        leads = matching_leads(niche, b["tenant_id"], DELIVERY_PER_BUYER)
        if not leads:
            continue
        for ld in leads:
            payload = {
                "buyer": b["name"], "tenant_id": b["tenant_id"],
                "lead": dict(ld), "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": "empire_os_buyer_delivery",
            }
            st, info = post_webhook(b["webhook_url"], payload)
            c = _conn()
            c.execute(
                "INSERT OR IGNORE INTO si_outbox "
                "(to_email, subject, body, lane, tier, lead_id, source, status, buyer_tenant, meta_json) "
                "VALUES (?, ?, ?, ?, ?, ?, 'buyer_delivery', ?, ?, ?)",
                (b["email"], f"lead:{ld['lead_uid']}", json.dumps(payload)[:4000],
                 niche, b["plan"], ld["lead_uid"],
                 "sent" if 200 <= st < 300 else "failed", b["tenant_id"],
                 json.dumps({"buyer_tenant": b["tenant_id"], "webhook": b["webhook_url"]})))
            c.commit(); c.close()
            total += 1
            _log("DELIVERED" if 200 <= st < 300 else "FAILED",
                 "lead_to_buyer", buyer=b["name"], lead=ld["lead_uid"],
                 status=st)
    return total


def main():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    _log("INFO", "buyer_delivery starting", interval=DELIVERY_INTERVAL,
         per_buyer=DELIVERY_PER_BUYER)
    while True:
        try:
            n = deliver_once()
            if n:
                _log("INFO", "cycle_done", delivered=n)
        except Exception as e:
            _log("ERROR", "cycle_exception", error=str(e)[:160])
        time.sleep(DELIVERY_INTERVAL)


if __name__ == "__main__":
    main()
