#!/usr/bin/env python3
"""crm_cli.py — CLI for the Empire OS CRM (segmentation + pipeline view).

Usage:
  python3 crm_cli.py summary                 # pipeline by stage/tier/niche
  python3 crm_cli.py stuck [--days N]        # contacts/deals with no progress
  python3 crm_cli.py segment --niche ROOFING # buyers in a lane
  python3 crm_cli.py segment --tier SILVER
  python3 crm_cli.py contact EMAIL           # full record for one contact
  python3 crm_cli.py update EMAIL --stage X --status Y --owner Z --note "..."

Reads the live container DB. No UI. Pipe-friendly.
"""
import sqlite3, sys, datetime, argparse

DB = "/root/empire_os/empire_os.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def q(sql, args=()):
    return c.execute(sql, args).fetchall()

def show(rows, cols):
    if not rows:
        print("(none)")
        return
    widths = []
    for col in cols:
        w = len(col)
        for r in rows:
            v = r[col]
            if v is not None:
                w = max(w, len(str(v)))
        widths.append(w)
    hdr = "  ".join(col.ljust(widths[i]) for i, col in enumerate(cols))
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print("  ".join(str(r[col] if r[col] is not None else "").ljust(widths[i]) for i, col in enumerate(cols)))

def cmd_summary():
    print("=== CONTACTS BY STAGE ===")
    show(q("SELECT stage, COUNT(*) c FROM crm_contacts GROUP BY stage ORDER BY c DESC"),
         ["stage", "c"])
    print("\n=== CONTACTS BY TIER ===")
    show(q("SELECT tier, COUNT(*) c FROM crm_contacts GROUP BY tier ORDER BY c DESC"),
         ["tier", "c"])
    print("\n=== DEALS BY STAGE ===")
    show(q("SELECT stage, COUNT(*) c, ROUND(SUM(amount_usdc),2) usdc FROM crm_deals GROUP BY stage ORDER BY c DESC"),
         ["stage", "c", "usdc"])
    print("\n=== TOP NICHE LANES (contacts) ===")
    show(q("SELECT niche, COUNT(*) c FROM crm_contacts GROUP BY niche ORDER BY c DESC LIMIT 10"),
         ["niche", "c"])

def cmd_stuck(days=7):
    print(f"=== STUCK: contacted but no application in {days}d ===")
    rows = q("""
        SELECT email, name, niche, metro, stage, updated_at FROM crm_contacts
        WHERE stage IN ('prospect','contacted')
          AND updated_at < datetime('now', ?)
        ORDER BY updated_at ASC LIMIT 30
    """, (f"-{days} days",))
    show(rows, ["email", "name", "niche", "metro", "stage", "updated_at"])
    print(f"\n=== STUCK DEALS: awaiting_payment > {days}d (no USDC) ===")
    rows = q("""
        SELECT contact_email, tenant_id, niche, metro, amount_usdc, created_at FROM crm_deals
        WHERE stage='awaiting_payment' AND created_at < datetime('now', ?)
        ORDER BY created_at ASC LIMIT 30
    """, (f"-{days} days",))
    show(rows, ["contact_email", "tenant_id", "niche", "metro", "amount_usdc", "created_at"])

def cmd_segment(niche=None, tier=None):
    w, a = [], []
    if niche:
        w.append("niche=?"); a.append(niche)
    if tier:
        w.append("tier=?"); a.append(tier)
    where = (" WHERE " + " AND ".join(w)) if w else ""
    rows = q(f"SELECT email, name, company, niche, metro, tier, stage, status, owner FROM crm_contacts{where} ORDER BY niche, stage LIMIT 100", a)
    show(rows, ["email", "name", "niche", "metro", "tier", "stage", "status", "owner"])

def cmd_contact(email):
    r = q("SELECT * FROM crm_contacts WHERE email=?", (email,))
    if not r:
        print("not found"); return
    for k, v in r[0].items():
        print(f"  {k}: {v}")
    deals = q("SELECT * FROM crm_deals WHERE contact_email=?", (email,))
    if deals:
        print("  DEALS:")
        for d in deals:
            print(f"    {d['subscription_id']} {d['stage']} {d['amount_usdc']}usdc {d['niche']}/{d['metro']}")

def cmd_update(email, **kw):
    sets, a = [], []
    for k in ("stage", "status", "owner", "tier"):
        if kw.get(k):
            sets.append(f"{k}=?"); a.append(kw[k])
    if kw.get("note"):
        sets.append("notes=notes||'\\n'||?")
        a.append(f"[{now()[:10]}] {kw['note']}")
    if not sets:
        print("nothing to update"); return
    sets.append("updated_at=?"); a.append(now())
    a.append(email)
    c.execute(f"UPDATE crm_contacts SET {','.join(sets)} WHERE email=?", a)
    c.commit()
    print(f"updated {email}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("summary")
    p = sub.add_parser("stuck"); p.add_argument("--days", type=int, default=7)
    p = sub.add_parser("segment"); p.add_argument("--niche"); p.add_argument("--tier")
    p = sub.add_parser("contact"); p.add_argument("email")
    p = sub.add_parser("update"); p.add_argument("email")
    p.add_argument("--stage"); p.add_argument("--status"); p.add_argument("--owner"); p.add_argument("--tier"); p.add_argument("--note")
    args = ap.parse_args()
    if args.cmd == "summary":
        cmd_summary()
    elif args.cmd == "stuck":
        cmd_stuck(args.days)
    elif args.cmd == "segment":
        cmd_segment(args.niche, args.tier)
    elif args.cmd == "contact":
        cmd_contact(args.email)
    elif args.cmd == "update":
        cmd_update(args.email, stage=args.stage, status=args.status, owner=args.owner, tier=args.tier, note=args.note)
    else:
        ap.print_help()
    c.close()
