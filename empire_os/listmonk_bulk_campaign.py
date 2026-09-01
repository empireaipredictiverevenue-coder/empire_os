"""
listmonk_bulk_campaign.py — fire a nurture blast to Listmonk subscribers
via the self-hosted SMTP->Brevo relay (no Listmonk internal SMTP, which is
broken with the dial :0 bug).

Flow:
  1. Pull enabled subscribers from a Listmonk list via API.
  2. For each, send a nurture email through the local relay (127.0.0.1:2525)
     which forwards to Brevo's API.

Safety:
  - DRY RUN by default (prints count + sample). Pass --send to actually send.
  - Rate-limited (--rate sec between sends) to respect Brevo throughput.
  - --limit N caps recipients (use for staged launches).
  - --test-email ADDR sends ONE test to that address instead of the list.

Listmonk admin auth = HTTP Basic (admin_username:admin_password from config.toml).
"""
import sys, json, time, smtplib, argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request, urllib.error
from urllib.error import HTTPError

LISTMONK_IP = "10.118.155.153"
LM_USER = "listmonk"
LM_PASS = "Jaykub20*"
RELAY_HOST = "127.0.0.1"
RELAY_PORT = 2525
FROM_ADDR = "growth@empire-ai.co.uk"
FROM_NAME = "Empire AI"

# Nurture copy — reply-to-buy style, zero-friction.
SUBJECT = "Your buyers are already searching — we found them"
HTML = """<div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto">
  <h2 style="color:#0aa">Empire AI — done-for-you buyer leads</h2>
  <p>We scrape, enrich and score in-market buyers across 115 niches, then deliver
  verified leads straight to your inbox with a one-click pay link.</p>
  <p>No calls. No card processor up front. You reply <b>"yes"</b> and the leads are yours.</p>
  <p style="margin:24px 0">
    <a href="https://empire-ai.co.uk/buy" style="background:#0aa;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none">See live buyer leads</a>
  </p>
  <p style="font-size:12px;color:#888">You're receiving this because you opted in via a lead form.
  Reply STOP to opt out.</p>
</div>"""
TEXT = ("Empire AI — done-for-you buyer leads. We scrape, enrich and score "
        "in-market buyers across 115 niches and deliver verified leads with a "
        "one-click pay link. No calls, no card up front. Reply 'yes' to claim. "
        "Stop to opt out. https://empire-ai.co.uk/buy")


def _b64(s):
    import base64
    return base64.b64encode(s.encode()).decode()


def api_get(path):
    req = urllib.request.Request(
        f"http://{LISTMONK_IP}:9000{path}",
        headers={"Authorization": "Basic " + _b64(f"{LM_USER}:{LM_PASS}")},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def pull_subscribers(list_id, status="enabled", limit=None):
    out, page = [], 1
    while True:
        try:
            d = api_get(f"/api/subscribers?list_id={list_id}&status={status}&page={page}&per_page=500")
        except HTTPError as e:
            print("API error:", e.read().decode()[:200]); break
        rows = d.get("data", {}).get("results", [])
        if not rows:
            break
        for r in rows:
            out.append(r["email"])
            if limit and len(out) >= limit:
                return out
        # keep paging until a short page (don't trust total_pages)
        if len(rows) < 500:
            break
        page += 1
    return out


def send_one(email):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"] = f"{FROM_NAME} <{FROM_ADDR}>"
    msg["To"] = email
    msg.attach(MIMEText(TEXT, "plain"))
    msg.attach(MIMEText(HTML, "html"))
    s = smtplib.SMTP(RELAY_HOST, RELAY_PORT, timeout=15)
    s.sendmail(FROM_ADDR, [email], msg.as_string())
    s.quit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("list_id", type=int, help="Listmonk list id (e.g. 3)")
    ap.add_argument("--send", action="store_true", help="actually send (default: dry run)")
    ap.add_argument("--limit", type=int, default=None, help="cap recipients")
    ap.add_argument("--rate", type=float, default=1.0, help="sec between sends")
    ap.add_argument("--test-email", default=None, help="send one test instead of list")
    a = ap.parse_args()

    if a.test_email:
        print(f"TEST send -> {a.test_email}")
        if a.send:
            send_one(a.test_email)
            print("test sent via relay")
        else:
            print("(dry run) would send test to", a.test_email)
        return

    emails = pull_subscribers(a.list_id, limit=a.limit)
    print(f"list {a.list_id}: {len(emails)} enabled subscribers"
          + (f" (capped at {a.limit})" if a.limit else ""))
    if not emails:
        return
    print("sample:", emails[:3])

    if not a.send:
        print("DRY RUN — pass --send to fire the blast.")
        return

    ok = err = 0
    for e in emails:
        try:
            send_one(e); ok += 1
        except Exception as ex:
            err += 1
            print(f"  ERR {e}: {ex}")
        time.sleep(a.rate)
    print(f"BLAST done: sent={ok} errors={err}")


if __name__ == "__main__":
    main()
