import csv, urllib.request, json
HUB = "http://10.118.155.218:8081"
SRC = "/root/supabase_lead_backup/prospects.csv"
n_in = n_ok = n_err = 0
def reg(p):
    req = urllib.request.Request(HUB + "/v1/outreach/prospect/register",
        data=json.dumps(p).encode(), headers={"Content-Type":"application/json"},
        method="POST")
    try:
        urllib.request.urlopen(req, timeout=10); return True
    except Exception:
        return False
with open(SRC) as f:
    for row in csv.DictReader(f):
        n_in += 1
        p = {
            "prospect_id": "gm:" + (row.get("id") or str(n_in)),
            "business_name": row.get("business_name",""),
            "email": "",
            "metro": row.get("metro",""),
            "niche": row.get("niche",""),
            "phone": row.get("phone",""),
            "source": "goldmine_prospects",
            "score": int(row.get("buy_signal_score") or 0),
            "url": row.get("website",""),
        }
        if reg(p): n_ok += 1
        else: n_err += 1
        if n_in % 5000 == 0:
            print(f"  loaded {n_in} ok={n_ok} err={n_err}", flush=True)
print(f"DONE in={n_in} ok={n_ok} err={n_err}")
