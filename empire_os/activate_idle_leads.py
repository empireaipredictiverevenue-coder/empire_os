"""Activate idle leads into active Empire OS flow via PostgREST.

Maps the three idle Supabase tables into their natural active consumer tables:
  - enriched_leads  (6,828) -> campaign_leads   (campaign/lead-delivery funnel)
  - b2b_leads       (775)   -> prospects         (buyer-outreach surface)
  - contractors     (7,355) -> contractor_outreach (dispatch/sequence consumer)

Idempotent: skips rows whose source id is already present in the target.
Batch <=1000 per PostgREST request. No deletes.
"""
from __future__ import annotations
import sys, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
import empire_os.sb as sb
import urllib.request, json

BATCH = 1000

def count(table, filt=None):
    q = f"{sb.SUPABASE_URL}/rest/v1/{table}?select=id&limit=1"
    if filt:
        for k, v in filt.items():
            q += f"&{k}=eq.{v}"
    req = urllib.request.Request(q, headers=sb._headers({"Prefer": "count=exact"}))
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = r.headers.get("content-range", "*/0")
        return int(cr.split("/")[-1])

def existing_ids(table, idcol, filt=None):
    ids = set(); off = 0
    while True:
        rows = sb.select(table, columns=idcol, limit=1000, offset=off,
                         filters=filt)
        if not rows: break
        for r in rows: ids.add(r[idcol])
        if len(rows) < 1000: break
        off += 1000
    return ids

def batch_insert(table, rows):
    url = f"{sb.SUPABASE_URL}/rest/v1/{table}"
    headers = sb._headers({"Prefer": "return=minimal"})
    req = urllib.request.Request(url, data=json.dumps(rows).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        # fall back to per-row inserts so one bad row doesn't abort the batch
        body = e.read().decode()[:200]
        print(f"  BATCH FAIL {table}: {e.code} {body}", flush=True)
        ok = 0
        for row in rows:
            try:
                sb.insert(table, row, return_repr=False)
                ok += 1
            except Exception as e2:
                print(f"    row fail {row.get('id') or row.get('contractor_id') or row.get('enriched_lead_id')}: {str(e2)[:160]}", flush=True)
        return ok

def activate_enriched():
    tgt = "campaign_leads"
    have = existing_ids(tgt, "enriched_lead_id")
    print(f"[enriched] target {tgt} already has {len(have)} enriched_lead_id", flush=True)
    rows = sb.select("enriched_leads", limit=1000)
    off = 0; done = 0
    while True:
        if not rows: break
        chunk = []
        for r in rows:
            eid = r["id"]
            if eid in have: continue
            try: score = float(r.get("score") or 0)
            except: score = 0
            temp = "hot" if score >= 70 else ("warm" if score >= 40 else "cold")
            chunk.append({
                "enriched_lead_id": eid,
                "warehouse_name": r.get("warehouse_name"),
                "address": r.get("address"),
                "city": r.get("city"),
                "state": r.get("state"),
                "phone": r.get("phone"),
                "email": r.get("email"),
                "enrichment_score": score,
                "temperature": temp,
                "source": r.get("source") or "enriched_leads",
                "campaign": (r.get("niche") or "default"),
                "status": "active",
            })
        if chunk:
            for i in range(0, len(chunk), BATCH):
                batch_insert(tgt, chunk[i:i+BATCH]); done += len(chunk[i:i+BATCH])
            print(f"  inserted {len(chunk)} (offset {off}) total {done}", flush=True)
        off += 1000
        rows = sb.select("enriched_leads", limit=1000, offset=off)
    print(f"[enriched] DONE inserted {done}", flush=True)

def activate_b2b():
    tgt = "prospects"
    have = existing_ids(tgt, "id")  # prospects id is uuid; b2b id is uuid
    print(f"[b2b] target {tgt} existing ids {len(have)}", flush=True)
    rows = sb.select("b2b_leads", limit=1000); off = 0; done = 0
    while True:
        if not rows: break
        chunk = []
        for r in rows:
            bid = r["id"]
            if bid in have: continue
            try: score = int(float(r.get("lead_score") or 0))
            except: score = 0
            chunk.append({
                "id": bid,
                "business_name": r.get("company_name"),
                "niche": r.get("niche"),
                "metro": r.get("metro"),
                "phone": r.get("phone"),
                "website": r.get("website"),
                "address": r.get("address"),
                "buy_signal_score": score,
                "contact_source": "b2b_leads",
                "status": "activated",
            })
        if chunk:
            for i in range(0, len(chunk), BATCH):
                batch_insert(tgt, chunk[i:i+BATCH]); done += len(chunk[i:i+BATCH])
            print(f"  inserted {len(chunk)} (offset {off}) total {done}", flush=True)
        off += 1000
        rows = sb.select("b2b_leads", limit=1000, offset=off)
    print(f"[b2b] DONE inserted {done}", flush=True)

def activate_contractors():
    tgt = "contractor_outreach"
    have = existing_ids(tgt, "contractor_id")
    print(f"[contractors] target {tgt} already has {len(have)} contractor_id", flush=True)
    rows = sb.select("contractors", limit=1000); off = 0; done = 0
    while True:
        if not rows: break
        chunk = []
        for r in rows:
            cid = r["id"]
            if cid in have: continue
            chunk.append({
                "contractor_id": cid,
                "sequence": "dispatch_onboarding",
                "step": 1,
                "status": "pending",
            })
        if chunk:
            for i in range(0, len(chunk), BATCH):
                batch_insert(tgt, chunk[i:i+BATCH]); done += len(chunk[i:i+BATCH])
            print(f"  inserted {len(chunk)} (offset {off}) total {done}", flush=True)
        off += 1000
        rows = sb.select("contractors", limit=1000, offset=off)
    print(f"[contractors] DONE inserted {done}", flush=True)

if __name__ == "__main__":
    print(f"=== ACTIVATE IDLE LEADS @ {datetime.now(timezone.utc).isoformat()} ===", flush=True)
    print("BEFORE counts:", flush=True)
    for t in ["campaign_leads","prospects","contractor_outreach"]:
        print(f"  {t}: {count(t)}", flush=True)
    activate_enriched()
    activate_b2b()
    activate_contractors()
    print("AFTER counts:", flush=True)
    for t in ["campaign_leads","prospects","contractor_outreach"]:
        print(f"  {t}: {count(t)}", flush=True)
    print("=== DONE ===", flush=True)
