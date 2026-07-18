#!/usr/bin/env python3
"""Re-sync Supabase prospects -> crm_leads with correct field mapping.

Fixes earlier bad sync (address leaked into niche column).
Maps Supabase niche -> lane sub_niche, metro city -> airport code.
"""
import re, urllib.request, json, sqlite3, datetime, sys
sys.path.insert(0, "/root/empire_os")
from empire_os.lane_router import STATE_METRO

NICHE_MAP = {
    "roofing": "residential_roofing", "roof": "residential_roofing",
    "roofer": "residential_roofing", "commercial roofing": "commercial_roofing",
    "commercial_roof": "commercial_roofing", "roof repair": "roof_repair",
    "storm damage": "storm_damage", "water mitigation": "water_damage",
    "water damage": "water_damage", "water": "water_damage",
    "fire damage": "fire_damage", "fire": "fire_damage",
    "mold": "mold_remediation", "sewage": "sewage_cleanup",
    "disaster": "disaster_restoration", "restoration": "disaster_restoration",
    "hvac": "hvac", "plumb": "plumbing", "electric": "electrical",
    "solar": "solar", "legal": "legal_services", "attorney": "legal_services",
    "law": "legal_services", "mass tort": "legal_services",
    "medicare": "insurance", "life insurance": "insurance", "insurance": "insurance",
    "debt": "debt_relief", "weight": "weight_loss", "ozempic": "ozempic",
    "hormone": "hormone_therapy", "dental": "dental", "vision": "vision",
    "medical": "medical_health", "health": "medical_health",
    "real estate": "real_estate", "mortgage": "mortgage",
    "accounting": "accounting", "tax": "tax_prep",
    "managed it": "managed_it", "it ": "managed_it", "cyber": "cybersecurity",
    "software": "software_dev", "web": "web_dev", "marketing": "marketing",
    "consult": "consulting", "staffing": "staffing", "cloud": "cloud",
    "ai": "ai_automation", "data": "data_analytics", "pt": "pt_rehab",
    "physical therapy": "pt_rehab", "nursing": "medical_health",
    "tree": "disaster_restoration", "gutter": "residential_roofing",
}

CITY_METRO = {
    "new york": "NYC", "los angeles": "LAX", "dallas": "DFW", "dallas-fort worth": "DFW",
    "fort worth": "DFW", "houston": "HOU", "chicago": "CHI", "washington": "WDC",
    "philadelphia": "PHL", "atlanta": "ATL", "miami": "MIA", "boston": "BOS",
    "san francisco": "SFO", "phoenix": "PHX", "las vegas": "LAX", "seattle": "LAX",
    "denver": "DFW", "austin": "DFW", "san antonio": "DFW", "orlando": "MIA",
    "tampa": "MIA", "new orleans": "HOU", "kansas city": "CHI", "wichita": "CHI",
    "memphis": "ATL", "nashville": "ATL", "charlotte": "ATL", "raleigh": "ATL",
    "detroit": "CHI", "cleveland": "CHI", "columbus": "CHI", "minneapolis": "CHI",
}

def classify_niche(text):
    t = (text or "").lower()
    for k, v in NICHE_MAP.items():
        if k in t:
            return v
    return ""

def parse_state(addr):
    m = re.search(r",\s*([A-Z]{2})\s*\d{5}", addr or "")
    return m.group(1) if m else ""

def main():
    e = open("/root/empire_os/.env").read()
    def gk(k):
        m = re.search(r"^"+k+r"=(.*)$", e, re.M); return m.group(1).strip() if m else ""
    url = gk("SUPABASE_URL"); key = gk("SUPABASE_SERVICE_KEY")
    H = {"apikey": key, "Authorization": f"Bearer {key}"}
    con = sqlite3.connect("/root/empire_os/empire_os.db")

    # wipe bad earlier sync
    con.execute("DELETE FROM crm_leads WHERE source='supabase_prospects'")
    con.execute("DELETE FROM lane_leads WHERE prospect_id IN (SELECT lead_uid FROM crm_leads WHERE source='supabase_prospects')")
    con.commit()

    existing = set(r[0] for r in con.execute("SELECT lead_uid FROM crm_leads"))
    ins = 0; OFF = 0
    while True:
        q = f"{url}/rest/v1/prospects?status=eq.new&select=id,business_name,niche,metro,phone,website,address,rating,buy_signal_score&limit=1000&offset={OFF}"
        rows = json.load(urllib.request.urlopen(urllib.request.Request(q, headers=H), timeout=20))
        if not rows: break
        for r in rows:
            lid = r.get("id")
            if not lid or lid in existing:
                continue
            bn = (r.get("business_name") or "").strip()
            nic = classify_niche(r.get("niche") or "")
            addr = r.get("address") or ""
            state = parse_state(addr)
            metro_city = (r.get("metro") or "").strip().lower()
            metro = CITY_METRO.get(metro_city, "")
            if not metro and state in STATE_METRO:
                metro = STATE_METRO[state][0]
            if not bn:
                continue
            try: score = float(r.get("buy_signal_score") or 0)
            except: score = 0
            con.execute("""INSERT OR IGNORE INTO crm_leads
              (lead_uid,source,business_name,contact_name,email,phone,metro,niche,street,city,state,zip,website,status,icp_tier,icp_score,enriched,created_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (r["id"],"supabase_prospects",bn,"",r.get("phone") or "",metro,nic,
               addr,"","",state,"",r.get("website") or "","raw","unscored",score,1,
               datetime.datetime.now(datetime.timezone.utc).isoformat()))
            if ins < 5:
                print(f"  DBG ins name={bn[:25]!r} raw={r.get('niche')!r} nic={nic!r} metro={metro!r}")
            ins += 1; existing.add(lid)
        OFF += 1000
        if OFF > 20000: break
    con.commit()
    empty = con.execute("SELECT COUNT(*) FROM crm_leads WHERE source='supabase_prospects' AND niche=''").fetchone()[0]
    filled = con.execute("SELECT COUNT(*) FROM crm_leads WHERE source='supabase_prospects' AND niche!=''").fetchone()[0]
    print(f"inserted {ins} clean leads | niche filled:{filled} empty:{empty}")
    con.close()

if __name__ == "__main__":
    main()
