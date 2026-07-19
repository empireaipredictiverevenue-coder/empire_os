#!/usr/bin/env python3
"""lead_deliverer — bridge crm_leads inventory -> seated buyers -> per-lead charge.

Uses empire_os.niche_map as the single source of truth for vertical
normalization so leads and buyers are separated by ONE canonical vertical
regardless of alias drift ('roofing' vs 'residential_roofing').

For every crm_lead whose canonical vertical has a seated, PAID buyer, deliver it:
POST to ppc_router /v1/ppc/lead-intake (bills the buyer their tier's per_lead
amount) and record the delivery so we never double-bill.

Safety:
  - PAID-only: a buyer must have an active subscription with a non-empty
    payment_ref. Never bill an unpaid/seated-only buyer (no fake revenue).
  - BATCH cap per run so a backfill never floods a buyer with thousands of
    charges in one tick.
  - idempotent: delivered_leads prevents re-billing.

Run:  python3 lead_deliverer.py            # new leads (last hour), capped
      python3 lead_deliverer.py --backfill # sweep inventory (capped by BATCH)
      python3 lead_deliverer.py --batch 20
"""
import sqlite3, json, sys, os, argparse, urllib.request, urllib.error
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
PPC = "http://127.0.0.1:9200"
BATCH_DEFAULT = 5

import empire_os.niche_map as nm


def init():
    c = sqlite3.connect(DB, timeout=20)
    c.execute("PRAGMA busy_timeout=15000")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS delivered_leads (
        id INTEGER PRIMARY KEY,
        crm_lead_id TEXT,
        tenant_id TEXT,
        lane_id TEXT,
        charge_id TEXT,
        amount_cents INTEGER,
        status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    c.commit(); c.close()


def seated_buyers():
    """Return {canonical_vertical: {metro_code: tenant_id}} for PAID buyers.

    Only buyers with an active subscription AND a real payment_ref are eligible
    — we never bill an unpaid buyer.
    """
    c = sqlite3.connect(DB, timeout=20); c.row_factory = sqlite3.Row
    out = {}
    for r in c.execute(
        """SELECT l.id, l.occupied_by, s.per_lead_cents, s.plan
           FROM lanes l
           JOIN si_subscription s ON s.tenant_id = l.occupied_by
           WHERE l.occupied_by IS NOT NULL AND l.occupied_by != ''
             AND s.status = 'active' AND s.payment_ref IS NOT NULL
             AND s.payment_ref != ''""").fetchall():
        lid = r["id"]
        if ":" not in lid:
            continue
        prefix, metro = lid.split(":", 1)
        vert = nm.canonical(prefix)
        if not vert:
            continue
        # amount: per_lead_cents from sub, fallback to tier default
        amt = r["per_lead_cents"] or nm.per_lead_cents(r["plan"] or "")
        out.setdefault(vert, {})[metro] = {"tenant_id": r["occupied_by"], "amount_cents": amt}
    c.close()
    return out


def map_metro(name: str) -> str:
    """crm_leads.metro full-name -> lane metro code (best-effort)."""
    if not name:
        return ""
    n = name.strip().lower()
    MAP = {
        "atlanta, ga": "ATL", "chicago, il": "CHI", "dallas, tx": "DFW",
        "houston, tx": "HOU", "miami, fl": "MIA", "new york, ny": "NYC",
        "los angeles, ca": "LAX", "boston, ma": "BOS", "philadelphia, pa": "PHL",
        "san francisco, ca": "SFO", "washington, dc": "WDC",
        "nassau, ny": "NYC", "bergen, nj": "NYC", "westchester, ny": "NYC",
        "suffolk, ny": "NYC", "miami-dade, fl": "MIA", "denver, co": "None",
        "phoenix, az": "None", "seattle, wa": "None", "austin, tx": "DFW",
    }
    if n in MAP:
        return MAP[n]
    if "," in n:
        st = n.split(",")[1].strip()[:2].upper()
        for k, v in MAP.items():
            if v and k.endswith(st.lower()):
                return v
    return ""


def deliver_one(lead, buyers):
    """Route a lead to a seated buyer in its canonical vertical.

    Returns dict with charge result, or None if no buyer.
    """
    niche = lead["sub_niche"] or lead["niche"] or ""
    vert = nm.canonical(niche)
    if not vert or vert not in buyers:
        return None
    metro = map_metro(lead["metro"])
    vbuyers = buyers[vert]
    if metro and metro in vbuyers:
        tenant_id = vbuyers[metro]["tenant_id"]
        amount = vbuyers[metro]["amount_cents"]
        lane_id = f"{nm.lane_prefixes(vert)[0]}:{metro}"
    else:
        # fallback: first seated metro for this vertical
        metro = next(iter(vbuyers))
        tenant_id = vbuyers[metro]["tenant_id"]
        amount = vbuyers[metro]["amount_cents"]
        lane_id = f"{nm.lane_prefixes(vert)[0]}:{metro}"
    lead_id = f"crm_{lead['lead_uid']}"
    body = json.dumps({
        "lead_id": lead_id, "niche": vert,
        "metro": lane_id.split(":")[1], "source": "lead_deliverer"
    }).encode()
    req = urllib.request.Request(f"{PPC}/v1/ppc/lead-intake", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "err": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "err": str(e)[:120]}
    return {"ok": True, "lane_id": lane_id, "tenant_id": tenant_id,
            "amount_cents": amount, "lead_id": lead_id, "resp": resp}


def run(batch=BATCH_DEFAULT, backfill=False):
    init()
    buyers = seated_buyers()
    if not buyers:
        print("no seated PAID buyers — nothing to deliver")
        return 0
    c = sqlite3.connect(DB, timeout=20); c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=15000")
    where = "" if backfill else "AND created_at > datetime('now','-1 hour')"
    # only pull leads whose canonical vertical has a buyer
    verts = list(buyers.keys())
    rows = c.execute(f"""
        SELECT * FROM crm_leads
        WHERE lead_uid NOT IN (SELECT crm_lead_id FROM delivered_leads)
        AND ({' OR '.join(['niche LIKE ?' for _ in verts])})
        {where}
        ORDER BY id DESC LIMIT ?""",
        [f"%{v}%" for v in verts] + [batch]).fetchall()
    print(f"candidates: {len(rows)} (batch={batch}, backfill={backfill}, verticals={verts})")
    delivered = 0
    for lead in rows:
        # confirm canonical match (LIKE is loose)
        if not nm.canonical(lead["sub_niche"] or lead["niche"] or "") in buyers:
            continue
        res = deliver_one(lead, buyers)
        if not res:
            continue
        if res.get("ok"):
            c.execute("INSERT INTO delivered_leads (crm_lead_id, tenant_id, lane_id, charge_id, amount_cents) VALUES (?,?,?,?,?)",
                      (lead["lead_uid"], res["tenant_id"], res["lane_id"],
                       res["resp"].get("charge_id"), int((res["resp"].get("amount_usdc") or 0) * 100)))
            c.commit()
            delivered += 1
            print(f"  delivered crm_{lead['lead_uid']} -> {res['lane_id']} ${res['resp'].get('amount_usdc')} charge {res['resp'].get('charge_id')}")
        else:
            print(f"  SKIP crm_{lead['lead_uid']}: {res.get('err')}")
    c.close()
    print(f"delivered this run: {delivered}")
    return delivered


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=BATCH_DEFAULT)
    ap.add_argument("--backfill", action="store_true")
    a = ap.parse_args()
    run(batch=a.batch, backfill=a.backfill)
