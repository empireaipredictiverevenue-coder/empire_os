#!/usr/bin/env python3
"""
Empire OS — CRM lead pool extractor.
Pulls real businesses from the container CRM DB (crm_leads) into a local
cache so outreach/sniper work even when Overpass is rate-limited.
Runs the query INSIDE the container (sqlite3 via python3), returns JSON.

Usage:
  python crm_pool.py --cache /root/feedback/crm_pool.jsonl --limit 200
"""
import sys, json, subprocess, argparse

CT = "empire-hub"
DB = "/root/empire_os/empire_os.db"

EXTRACT = r'''
import sqlite3, json
db=sqlite3.connect("/root/empire_os/empire_os.db"); db.row_factory=sqlite3.Row
c=db.cursor()
want=["business_name","email","phone","metro","niche","sub_niche","website","city","state","zip","icp_tier"]
c.execute("SELECT * FROM crm_leads")
rows=c.fetchall()
out=[]
for r in rows:
    d={k:r[k] for k in want if k in r.keys()}
    out.append(d)
print(json.dumps(out))
'''

def extract(limit=500):
    # write extractor into container, run, capture JSON
    subprocess.run(["incus","file","push","/dev/stdin",f"{CT}/root/_crm_extract.py"],
                   input=EXTRACT.encode(), check=True)
    res = subprocess.run(["incus","exec",CT,"--","python3","/root/_crm_extract.py"],
                         capture_output=True, text=True, timeout=60)
    try:
        data = json.loads(res.stdout.strip().splitlines()[-1])
    except Exception as e:
        print("parse err:", e, res.stdout[-300:], res.stderr[-300:]); return []
    return data[:limit]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="/root/feedback/crm_pool.jsonl")
    ap.add_argument("--limit", type=int, default=500)
    a = ap.parse_args()
    data = extract(a.limit)
    with open(a.cache, "w") as f:
        for d in data:
            f.write(json.dumps(d) + "\n")
    print(f"[crm_pool] {len(data)} real leads cached -> {a.cache}")

if __name__ == "__main__":
    main()
