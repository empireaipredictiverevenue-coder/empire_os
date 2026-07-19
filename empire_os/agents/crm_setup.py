#!/usr/bin/env python3
"""crm_setup.py — build the CRM layer on top of the live Empire OS DB.

- Creates crm_contacts + crm_deals (segmentation backbone).
- Backfills from si_buyer_outreach (prospects) + si_subscription (buyer seats).
- Cleans junk emails leaked from the prospect table (url-encoded,
  @sentry, @calendar.google, @example, invalid, owner-pending).
- Idempotent: safe to re-run.

Run inside the container (where the live DB lives).
"""
import sqlite3, re, datetime

DB = "/root/empire_os/empire_os.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

print("=== 0. drop existing CRM tables for clean re-run ===")
c.execute("DROP TABLE IF EXISTS crm_contacts")
c.execute("DROP TABLE IF EXISTS crm_deals")
c.commit()

print("=== 1. create CRM tables ===")
c.execute("""
CREATE TABLE IF NOT EXISTS crm_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    company TEXT,
    niche TEXT,
    metro TEXT,
    tier TEXT DEFAULT 'unknown',
    stage TEXT DEFAULT 'prospect',   -- prospect|contacted|applied|paid|active|churned
    status TEXT DEFAULT 'new',        -- new|hot|warm|cold|responded|no_response
    owner TEXT DEFAULT 'unassigned',
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    source TEXT,
    created_at TEXT,
    updated_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS crm_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_email TEXT NOT NULL,
    tenant_id TEXT,
    subscription_id TEXT,
    niche TEXT,
    metro TEXT,
    tier TEXT DEFAULT 'unknown',
    amount_usdc REAL DEFAULT 0,
    stage TEXT DEFAULT 'applied',
    close_date TEXT,
    touch_1_sent INTEGER DEFAULT 0,
    touch_2_sent INTEGER DEFAULT 0,
    touch_3_sent INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
)
""")
c.commit()

print("=== 2. junk-email cleanup (from prospect table contamination) ===")
# Patterns that are NOT real buyer emails
JUNK = re.compile(
    r'(%[0-9A-Fa-f]{2})'          # url-encoded
    r'|sentry'                     # sentry noise (incl. ingest.us.sentry.io)
    r'|calendar\.google'           # calendar bots
    r'|@example'                   # placeholders
    r'|invalid'                    # invalid
    r'|owner-pending'              # placeholder owner
    r'|@domain\.com$'              # fake domain
    r'|noreply|no-reply'           # no-reply
    r'|postmaster|mailer-daemon'   # system
    , re.I)
def is_junk(e):
    if not e:
        return True
    e = e.strip()
    if '@' not in e or '.' not in e.split('@')[-1]:
        return True
    return bool(JUNK.search(e))

# clean crm_contacts if already partially backfilled
c.execute("DELETE FROM crm_contacts WHERE email IN (SELECT email FROM crm_contacts WHERE 0)")
# we clean by NOT inserting junk in the backfill below; also purge any existing junk
cur = c.execute("SELECT id, email FROM crm_contacts").fetchall()
purged = 0
for r in cur:
    if is_junk(r["email"]):
        c.execute("DELETE FROM crm_contacts WHERE id=?", (r["id"],))
        purged += 1
print(f"  purged {purged} junk contacts already present")

print("=== 3. backfill crm_contacts from si_buyer_outreach (real prospects only) ===")
prospects = c.execute(
    "SELECT business_name, email, niche, metro, source, last_touch_at "
    "FROM si_buyer_outreach WHERE email IS NOT NULL AND email != ''"
).fetchall()
ins = 0
for p in prospects:
    email = (p["email"] or "").strip()
    if is_junk(email):
        continue
    name = (p["business_name"] or "").split("|")[0].split(" - ")[0].strip()
    company = p["business_name"] or ""
    c.execute(
        "INSERT OR IGNORE INTO crm_contacts "
        "(email, name, company, niche, metro, tier, stage, status, source, created_at, updated_at) "
        "VALUES (?,?,?,?,?, 'unknown','prospect','new',?,?,?)",
        (email, name, company, p["niche"], p["metro"], p["source"], p["last_touch_at"] or now(), now())
    )
    ins += 1
c.commit()
print(f"  backfilled {ins} real prospect contacts")

print("=== 4. backfill crm_deals from si_subscription (buyer seats) ===")
subs = c.execute(
    "SELECT tenant_id, subscription_id, niche, plan, price_cents, status, created_at "
    "FROM si_subscription"
).fetchall()
dins = 0
for s in subs:
    email_row = c.execute("SELECT email FROM si_tenant WHERE tenant_id=?", (s["tenant_id"],)).fetchone()
    email = email_row["email"] if email_row else None
    if not email or is_junk(email):
        # still record the deal keyed by tenant even without clean email
        email = email or f"tenant:{s['tenant_id']}"
    stage_map = {"awaiting_payment": "awaiting_payment", "active": "active",
                 "cancelled": "churned", "churned": "churned"}
    stage = stage_map.get(s["status"], "applied")
    amt = (s["price_cents"] or 0) / 100.0
    c.execute(
        "INSERT OR IGNORE INTO crm_deals "
        "(contact_email, tenant_id, subscription_id, niche, metro, tier, amount_usdc, stage, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (email, s["tenant_id"], s["subscription_id"], s["niche"], "", 
         s["plan"], amt, stage, s["created_at"] or now(), now())
    )
    dins += 1
c.commit()
print(f"  backfilled {dins} deals")

print("=== 5. mark stage by outreach activity (contacted if email sent) ===")
sent = c.execute(
    "SELECT DISTINCT to_email FROM si_outbox WHERE status='sent' AND source='founder_outreach'"
).fetchall()
for r in sent:
    c.execute("UPDATE crm_contacts SET stage='contacted', updated_at=? WHERE email=? AND stage='prospect'",
              (now(), r["to_email"]))
c.commit()
print(f"  marked {len(sent)} contacts as contacted")

print("=== 6. segment counts ===")
for label, sql in [
    ("total contacts", "SELECT COUNT(*) FROM crm_contacts"),
    ("by stage", "SELECT stage, COUNT(*) FROM crm_contacts GROUP BY stage"),
    ("by tier", "SELECT tier, COUNT(*) FROM crm_contacts GROUP BY tier"),
    ("by niche (top5)", "SELECT niche, COUNT(*) c FROM crm_contacts GROUP BY niche ORDER BY c DESC LIMIT 5"),
    ("deals total", "SELECT COUNT(*) FROM crm_deals"),
    ("deals by stage", "SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage"),
]:
    if "GROUP" in sql:
        rows = c.execute(sql).fetchall()
        print(f"  {label}: " + ", ".join(f"{r[0]}={r[1]}" for r in rows))
    else:
        print(f"  {label}: {c.execute(sql).fetchone()[0]}")

c.close()
print("\nCRM setup complete.")
