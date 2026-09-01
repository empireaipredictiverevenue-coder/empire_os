"""
listmonk_import_leads.py — bulk-import Empire buyer leads into Listmonk (no UI needed).

Listmonk admin auth = HTTP Basic (listmonk:Jaykub20*), NOT the JSON login.
API base: http://10.118.155.153:9000  (configurable via LISTMONK_URL / LISTMONK_AUTH).
Target list: "Empire Leads" (id from --list-id, default 3).

Pulls real emails from si_buyer_outreach (669 buyer-intent leads) and pushes as
subscribers. Used for zero-friction bulk nurture beyond Brevo quota.
"""
import os, sys, json, sqlite3, urllib.request, base64

LISTMONK_URL = os.getenv("LISTMONK_URL", "http://10.118.155.153:9000")
LISTMONK_AUTH = os.getenv("LISTMONK_AUTH", "listmonk:Jaykub20*")
DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
LIST_ID = int(os.getenv("LIST_ID", "3"))


def _req(method, path, body=None):
    url = f"{LISTMONK_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    token = base64.b64encode(LISTMONK_AUTH.encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def get_emails(limit=None):
    c = sqlite3.connect(DB)
    q = """SELECT email, business_name, niche, metro
           FROM si_buyer_outreach
           WHERE email IS NOT NULL AND email != '' AND email LIKE '%@%'"""
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = c.execute(q).fetchall()
    c.close()
    out = []
    for email, name, niche, metro in rows:
        attribs = {}
        if niche: attribs["niche"] = niche
        if metro: attribs["metro"] = metro
        out.append({"email": email, "name": name or "", "lists": [LIST_ID],
                    "status": "enabled", "attribs": attribs})
    return out


def run(limit=None, dry=False):
    subs = get_emails(limit)
    print(f"[listmonk-import] {len(subs)} leads to import (list {LIST_ID})")
    added = skipped = 0
    for s in subs:
        if dry:
            print("  DRY", s["email"]); continue
        try:
            _req("POST", "/api/subscribers", s)
            added += 1
        except urllib.error.HTTPError as e:
            if e.code == 409:  # already exists
                skipped += 1
            else:
                print(f"  ERR {s['email']}: {e.code}")
    print(f"[listmonk-import] done: added={added} skipped={skipped}")
    return {"added": added, "skipped": skipped, "total": len(subs)}


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    dry = "--dry" in sys.argv
    run(limit=lim, dry=dry)
