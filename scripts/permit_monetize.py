#!/usr/bin/env python3
"""
permit_monetize.py — turn NYC permit leads (sellable_permits_dedup) into
buyer-facing intro emails via the hub outbox.

Revenue thesis: each A2.OT/NYC construction permit = a live project a
contractor (registered buyer) will pay for. We bridge permit holders ->
registered NYC buyers and enqueue intro emails. The hub outbox sends them;
buyers that respond become paid leads.

Dry-run by default. --apply to enqueue. Idempotent: skips lead_ids already
in si_outbox for this source.
"""
import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error

DB = os.environ.get("EMPIRE_DB_PATH", "/root/empire_os/empire_os.db")
HUB = "http://127.0.0.1:8081"
SOURCE = "permit_monetize"
MAX_PER_BUYER = 3  # cap intro emails per buyer per run to avoid spam


def fetch_permits(conn):
    rows = conn.execute(
        "SELECT phone, name, lead_ref, notes FROM sellable_permits_dedup"
    ).fetchall()
    return [
        {"phone": r[0], "name": r[1], "lead_ref": r[2], "notes": r[3],
         "metro": "NYC", "niche": ""} for r in rows
    ]


def parse_permit_type(notes):
    # e.g. "details=A2.OT permit 101801748 issued..." -> 'A2.OT'
    try:
        pt = notes.split("details=")[1].split(" permit")[0].strip()
        return pt
    except Exception:
        return "construction"


# permit type -> buyer niche keywords (broad: all NYC permits = construction)
NICHE_MAP = {
    "a2.ot": ["roof", "plumb", "gc", "general", "contractor", "construction",
              "electric", "hvac", "mechanical", "build"],
    "construction": ["roof", "plumb", "gc", "general", "contractor",
                     "construction", "electric", "hvac", "mechanical", "build"],
}


def buyer_match(buyer, ptype):
    cov = (buyer.get("state_coverage") or "") + " " + (buyer.get("metro") or "")
    if "NY" not in cov.upper() and "NYC" not in cov.upper():
        return False
    niche = (buyer.get("niche") or "").lower()
    if not niche:
        return True  # generic buyer accepts all NYC construction
    kws = NICHE_MAP.get(ptype.lower().replace(".", ""), NICHE_MAP["construction"])
    for kw in kws:
        if kw in niche:
            return True
    return False


def fetch_buyers(conn):
    rows = conn.execute(
        "SELECT id, buyer_name, niche, state_coverage, metro, email, contact_name "
        "FROM buyers WHERE is_active=1 OR is_active IS NULL"
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "niche": r[2], "state_coverage": r[3],
         "metro": r[4], "email": r[5], "contact": r[6]} for r in rows
    ]


def enqueue(to_email, subject, body, lane, tier, lead_id):
    payload = json.dumps({
        "to_email": to_email, "subject": subject, "body": body,
        "lane": lane, "tier": tier, "lead_id": lead_id, "source": SOURCE,
    }).encode()
    req = urllib.request.Request(
        f"{HUB}/v1/outbox/enqueue", data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def already_sent(conn, lead_id):
    n = conn.execute(
        "SELECT count(*) FROM si_outbox WHERE lead_id=? AND source=?",
        (lead_id, SOURCE)).fetchone()[0]
    return n > 0


def main():
    apply = "--apply" in sys.argv
    print(f"MODE={'APPLY' if apply else 'DRYRUN'}", flush=True)
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    permits = fetch_permits(conn)
    buyers = fetch_buyers(conn)
    print(f"  permits={len(permits)} buyers(nyc-capable)={len(buyers)}", flush=True)

    queued = 0
    sent_pairs = set()  # (lead_ref, buyer_id) to avoid dup
    # assign each buyer up to MAX_PER_BUYER permits (round-robin spread)
    for b in buyers:
        bid = b["id"]
        if not b["email"]:
            continue
        matched_perms = [p for p in permits if buyer_match(b, parse_permit_type(p["notes"]))]
        assigned = 0
        for p in matched_perms:
            lid = f"{p['lead_ref']}|{bid}"
            if lid in sent_pairs:
                continue
            if already_sent(conn, lid):
                sent_pairs.add(lid)
                continue
            if apply:
                try:
                    ptype = parse_permit_type(p["notes"])
                    subject = f"New {ptype} project lead in {p['metro'] or 'NYC'} — {p['name']}"
                    body = (
                        f"Project owner: {p['name']}\n"
                        f"Phone: {p['phone']}\n"
                        f"Location: {p['metro']} (NYC)\n"
                        f"Permit: {ptype} — {p['notes'][:400]}\n\n"
                        f"Reply to claim this lead. Pay-per-call or per-lead terms available."
                    )
                    enqueue(b["email"], subject, body, "permits", "silver", lid)
                    queued += 1
                    sent_pairs.add(lid)
                    assigned += 1
                except Exception as e:
                    print(f"    enqueue ERR {b['email']}: {e}", flush=True)
            else:
                queued += 1
                sent_pairs.add(lid)
                assigned += 1
            if assigned >= MAX_PER_BUYER:
                break
    conn.close()
    print(f"  -> would/enqueued {queued} intro emails (cap {MAX_PER_BUYER}/buyer)",
          flush=True)
    if not apply:
        print("DRYRUN complete. Re-run with --apply to enqueue.")


if __name__ == "__main__":
    main()
