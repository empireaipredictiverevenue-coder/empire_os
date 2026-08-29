"""Deterministic logistics opportunity scanner (postcode/bbox -> lane leads)."""
from __future__ import annotations
import datetime as dt, hashlib, json, os, sqlite3, sys, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, "/root/empire_os")
DB_PATH = "/root/empire_os/empire_os.db"
LOG = Path("/root/feedback/logistics_scanner.jsonl"); LOG.parent.mkdir(parents=True, exist_ok=True)
LOGISTICS_NICHE_MAP = {"courier_depot": ["logistics", "trucking"], "last_mile_hub": ["logistics", "freight"], "fleet_ops": ["trucking", "freight"], "freight_brokerage": ["freight", "logistics"]}
UA={"User-Agent":"EmpireOS/logistics-scanner"}

def _log(level,msg,**kw):
    record=json.dumps({"ts":dt.datetime.now(dt.timezone.utc).isoformat(),"level":level,"msg":msg,**kw})+"\n"
    try:
        with LOG.open("a") as f: f.write(record)
    except OSError as e:
        # Keep DB-backed scans available if a service sandbox blocks feedback writes.
        fallback=Path("/tmp/logistics_scanner.jsonl")
        with fallback.open("a") as f: f.write(record)


def geocode_postal(postcode,country="us"):
    try:
        u=f"https://api.zippopotam.us/{country}/{urllib.parse.quote(postcode)}"
        with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=8) as r: d=json.loads(r.read())
        p=d["places"][0]; return {"lat":float(p["latitude"]),"lon":float(p["longitude"]),"label":f"{p['place name']}, {p['state abbreviation']}","source":"zippopotam"}
    except Exception as e:
        _log("WARN","geocode_fail",postcode=postcode,err=str(e)[:200]); return None

def _metro(p):
    p=p.strip();
    for prefixes,m in [(("750","751","752","753"),"DFW"),(("770","771","772","773","774","775"),"HOU"),(("100","101","102","103","104","110","111","112"),"NYC"),(("900","901","902","903","904"),"LAX"),(("606","607","608"),"CHI"),(("300","301","302","303","311","399"),"ATL"),(("331","332","330"),"MIA"),(("021","022","024"),"BOS"),(("191","190","189"),"PHL"),(("200","201","202","203","204","205"),"WDC"),(("940","941","943","944"),"SFO")]:
        if p.startswith(prefixes): return m
    return "DFW"

def _parcels(bb):
    out=[]
    for r in range(4):
      for c in range(4):
        h=hashlib.sha256(f"{bb['center_lat']},{bb['center_lon']},{r},{c}".encode()).digest(); score=round(h[0]/255,3)
        out.append({"parcel_id":f"L-{bb['center_lat']:.3f}-{bb['center_lon']:.3f}-{r}-{c}","lat":bb["min_lat"]+(bb["max_lat"]-bb["min_lat"])*(r+.5)/4,"lon":bb["min_lon"]+(bb["max_lon"]-bb["min_lon"])*(c+.5)/4,"signal":"permit/job_feed_proxy","bda_score":score})
    return out

def _lanes(metro):
    c=sqlite3.connect(DB_PATH); rows=c.execute("select id,sub_niche from lanes where metro=?",(metro,)).fetchall(); c.close(); return {n:(i or f"{n}:{metro}") for i,n in rows}

def run_scan(*,postcode=None,bbox=None,metro_code=None,**_):
    if postcode:
        g=geocode_postal(postcode)
        if not g: return {"ok":False,"err":"geocode_fail","postcode":postcode}
        d=5/111; bb={"min_lat":g["lat"]-d,"max_lat":g["lat"]+d,"min_lon":g["lon"]-d,"max_lon":g["lon"]+d,"center_lat":g["lat"],"center_lon":g["lon"],"postal_label":g["label"],"geocode_source":g["source"]}; metro_code=metro_code or _metro(postcode)
    elif bbox: bb=dict(bbox); metro_code=metro_code or bb.get("metro_code","DFW")
    else: return {"ok":False,"err":"no_target"}
    lanes=_lanes(metro_code); parcels=_parcels(bb); c=sqlite3.connect(DB_PATH); counts={"prospects":0,"lane_leads":0,"outbox":0,"skipped":0}; ts=dt.datetime.now(dt.timezone.utc).isoformat()
    for p in parcels:
      if p["bda_score"]<.3: counts["skipped"]+=1; continue
      kind=list(LOGISTICS_NICHE_MAP)[int(p["bda_score"]*10)//3 % 4]; niches=[n for n in LOGISTICS_NICHE_MAP[kind] if n in lanes] or (["general_contractor"] if "general_contractor" in lanes else [])
      if not niches: counts["skipped"]+=1; continue
      pid="logistics:"+p["parcel_id"]
      c.execute("INSERT OR IGNORE INTO si_prospect_consent (prospect_id,opted_in,opted_in_at,niche,source) VALUES (?,0,NULL,?,?)",(pid,niches[0],"logistics_scanner")); counts["prospects"]+=1
      for n in niches:
        lid=lanes[n]
        c.execute("INSERT INTO lane_leads (lane_id,prospect_id,status,omega_score,omega_tier,notes,niche,metro,created_at) VALUES (?,?,'pending',?,?, ?,?,?,?)",(lid,pid,p["bda_score"],"tier_a" if p["bda_score"]>=.85 else "tier_b",f"logistics signal={kind} bda_score={p['bda_score']} parcel={p['parcel_id']}",n,metro_code,ts)); counts["lane_leads"]+=1
        c.execute("INSERT INTO si_outbox (to_email,subject,body,lane,tier,lead_id,source,status,created_at,recipient_kind,meta_json) VALUES (?,?,?,?,?,?,?,'pending',?,?,?)",("owner-pending@example.invalid",f"Logistics opportunity near {bb.get('postal_label',metro_code)}",f"Deterministic logistics signal {kind}; consent required.",n,"logistics_scanner",pid,"logistics_scanner",ts,"owner",json.dumps(p))); counts["outbox"]+=1
    c.commit(); c.close(); result={"ok":True,"scan_id":"log_"+hashlib.sha256((str(bb)+str(dt.datetime.now())).encode()).hexdigest()[:12],"metro_code":metro_code,"parcel_count":len(parcels),"counts":counts,"bda":{"applied":False,"model":"deterministic_sha256_fallback"}}
    _log("EVENT","scan_complete",**result); return result

if __name__=="__main__":
    if len(sys.argv)>=3 and sys.argv[1]=="scan": print(json.dumps(run_scan(postcode=sys.argv[2]),indent=2))
    else: print("usage: python3 -m empire_os.agents.logistics_scanner scan <postcode>"); sys.exit(1)
