"""Enterprise pilot activation — sends branded pay-link emails to ready buyers.

Ready = endpoint_url + wallet + hmac set, not yet paid. Email links to the
separate /pay/<memo> page (never raw vault in body). Outbound via Brevo only.
"""
import sqlite3, sys, json, time, sys as _s
sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

from empire_os.templates.email.email_helpers import wrap, pay_link, cloak, FROM

VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"

conn = sqlite3.connect("/root/empire_os/empire_os.db")
conn.execute("PRAGMA busy_timeout=30000")

ready = conn.execute(
    """SELECT prospect_id, business_name, email, niche, metro, payout_per_lead, wallet
       FROM si_buyer_outreach
       WHERE endpoint_url IS NOT NULL AND wallet IS NOT NULL AND hmac_secret IS NOT NULL
         AND email IS NOT NULL AND email != '' AND email NOT LIKE '%@example.%'
         AND email NOT LIKE '%test%'"""
).fetchall()
print("ready buyers:", len(ready))

done = set(r[0] for r in conn.execute(
    "SELECT to_email FROM si_outbox WHERE source='enterprise_pilot' AND status='pending'"))
print("already queued:", len(done))

q = 0
for b in ready:
    pid, name, email, niche, metro, payout, wallet = b
    if email in done:
        continue
    amount = payout if payout and payout > 0 else 4.0
    memo = f"pilot:{pid}"
    plink = pay_link(memo, amount)
    claim = cloak("https://empire-ai.co.uk/claim", "pilot")
    subject = f"Empire OS — your lane is ready, {name.split()[0] if name else 'partner'}"
    body = (
        f"<p>Hi {name.split()[0] if name else 'there'},</p>"
        f"<p>We reserved a dedicated lead lane for <b>{niche or 'home-services'}</b> "
        f"in <b>{metro or 'your metro'}</b>. Other operators are already pulling "
        f"Omega-scored leads from it.</p>"
        f"<p>You're set up to receive leads automatically the moment you activate — "
        f"they'll POST straight to your endpoint, HMAC-signed, no manual exports.</p>"
        f"<p style='margin:18px 0'><a href='{plink}' "
        f"style='background:{ '#39ff88' };color:#050810;padding:12px 20px;"
        f"border-radius:10px;font-weight:700;text-decoration:none'>View your activation &amp; pricing</a></p>"
        f"<p style='color:{ '#9bb0c9' };font-size:13px'>Per-lead: ${amount:.2f}. "
        f"Settled in USDT on BSC. No monthly minimums.</p>"
        f"<p style='margin-top:14px'><a href='{claim}' style='color:{ '#22e3ff' }'>"
        f"See a sample lead</a></p>"
    )
    html = wrap(subject, "Your Empire OS lead lane is reserved", body, email)
    conn.execute(
        """INSERT INTO si_outbox (to_email, subject, body, html_body, lane, tier,
           lead_id, source, status, recipient_kind, meta_json)
           VALUES (?,?,?,?,'general','GOLD',?,'enterprise_pilot','pending','buyer',?)""",
        (email, subject, body, html, pid,
         json.dumps({"wallet": wallet, "payout_per_lead": amount, "vault": VAULT,
                     "memo": memo, "pay_url": plink})),
    )
    q += 1
    done.add(email)

conn.commit()
conn.close()
print(f"queued {q} pilot emails (branded, /pay/ link, no raw vault in body)")
