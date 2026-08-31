#!/usr/bin/env python3
"""Buyer blast — enqueue priced buyers to the outbox (Brevo rail).

Professional branded HTML + plain-text via empire_os.email_templates.
One ask per email: reply "sample". No price wall, no raw vault address,
no list-buying language. CAN-SPAM: postal address + unsub link in every
body, List-Unsubscribe header added by mail_sender.
Sends via hub /v1/outbox/enqueue -> mail-sender daemon -> Brevo.
"""
import json, sqlite3, urllib.request

HUB = "http://127.0.0.1:8081"
DB = "/root/empire_os/empire_os.db"
SOURCE = "buyer_blast_v2"

from empire_os.email_templates import blast_subject, blast_text, blast_html


def enqueue(to_email, subject, body, html, lead_id):
    payload = json.dumps({
        "to_email": to_email,
        "subject": subject,
        "body": body[:7900],
        "html_body": html,
        "lane": "buyer_acquisition",
        "tier": "buyer",
        "lead_id": lead_id,
        "source": SOURCE,
    }).encode()
    req = urllib.request.Request(
        f"{HUB}/v1/outbox/enqueue", data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("""
        SELECT prospect_id, business_name, email, niche, metro, niches, metros, payout_per_lead
        FROM si_buyer_outreach
        WHERE email IS NOT NULL AND email != '' AND payout_per_lead > 0
    """).fetchall()
    c.close()
    print(f"Buyers to blast: {len(rows)}")
    ok = fail = 0
    for b in rows:
        niche = (b["niche"] or b["niches"] or "contractor").split(",")[0].strip()
        metro = (b["metro"] or b["metros"] or "your area").split(",")[0].strip()
        payout = float(b["payout_per_lead"] or 0)
        name = (b["business_name"] or "").strip()
        subject = blast_subject(niche, metro, payout)
        body = blast_text(name, niche, metro, payout)
        html = blast_html(name, niche, metro, payout)
        try:
            res = enqueue(b["email"], subject, body, html, b["prospect_id"])
            if res.get("ok"):
                ok += 1
            else:
                fail += 1
                if fail <= 3:
                    print("FAIL", b["email"], res)
        except Exception as e:
            fail += 1
            if fail <= 3:
                print("ERR", b["email"], e)
        if (ok + fail) % 50 == 0:
            print(f"  progress {ok+fail}/{len(rows)} (ok={ok} fail={fail})")
    print(f"DONE enqueue: ok={ok} fail={fail} total={len(rows)}")
    print("mail-sender daemon drains via Brevo (2000/day cap).")


if __name__ == "__main__":
    main()
