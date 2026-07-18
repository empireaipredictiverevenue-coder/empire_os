#!/usr/bin/env python3
"""Clean re-sync: fix corrupt niche in existing crm_leads from Supabase source.

The 6,476 leads were synced with address leaked into niche column.
Their lead_uid = Supabase prospect id. Pull real niche+address from Supabase,
reclassify niche -> lane sub_niche, update row, then route_lead.

Does NOT delete or wipe. Only updates mislabeled rows + routes them.
"""
import re, urllib.request, json, sqlite3, datetime, sys
sys.path.insert(0, "/root/empire_os")
from empire_os.lane_router import STATE_METRO, route_lead

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
    "general contractor": "general_contractor", "general_contractor": "general_contractor",
}

CITY_METRO = {
    "new york": "NYC", "los angeles": "LAX", "dallas": "DFW",
    "dallas-fort worth": "DFW", "fort worth": "DFW", "houston": "HOU",
    "chicago": "CHI", "washington": "WDC", "philadelphia": "PHL",
    "atlanta": "ATL", "miami": "MIA", "boston": "BOS", "san francisco": "SFO",
    "phoenix": "PHX", "las vegas": "LAX", "seattle": "LAX", "denver": "DFW",
    "austin": "DFW", "san antonio": "DFW", "orlando": "MIA", "tampa": "MIA",
    "new orleans": "HOU", "kansas city": "CHI", "wichita": "CHI",
    "memphis": "ATL", "nashville": "ATL", "charlotte": "ATL", "raleigh": "ATL",
    "detroit": "CHI", "cleveland": "CHI", "columbus": "CHI", "minneapolis": "CHI",
}

def classify(text):
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
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")

    # rows needing fix: empty niche OR niche looks like an address
    rows = con.execute(
        "SELECT lead_uid FROM crm_leads WHERE niche='' OR niche LIKE '%,%USA'").fetchall()
    print(f"rows to fix: {len(rows)}")

    fixed = 0; rerouted = 0; fetched = 0
    for (lid,) in rows:
        try:
            q = f"{url}/rest/v1/prospects?id=eq.{lid}&select=niche,address,metro,phone,website,buy_signal_score&limit=1"
            recs = json.load(urllib.request.urlopen(
                urllib.request.Request(q, headers=H), timeout=20))
        except Exception as ex:
            continue
        if not recs:
            continue
        r = recs[0]; fetched += 1
        nic = classify(r.get("niche") or "")
        addr = r.get("address") or ""
        state = parse_state(addr)
        metro_city = (r.get("metro") or "").strip().lower()
        metro = CITY_METRO.get(metro_city, "")
        if not metro and state in STATE_METRO:
            metro = STATE_METRO[state][0]
        # update the row in place (NO delete)
        con.execute(
            "UPDATE crm_leads SET niche=?, metro=?, state=?, street=? WHERE lead_uid=?",
            (nic, metro, state, addr, lid))
        fixed += 1
        # route if it now has a lane-matching niche
        if nic:
            try:
                route_lead(con, lid, f"niche={nic}|metro={metro}", state=state)
                rerouted += 1
            except Exception:
                pass
        if fetched % 500 == 0:
            con.commit()
            print(f"  fetched {fetched}, fixed {fixed}, rerouted {rerouted}")
    con.commit()
    print(f"DONE fetched={fetched} fixed={fixed} rerouted_to_lanes={rerouted}")

if __name__ == "__main__":
    main()
