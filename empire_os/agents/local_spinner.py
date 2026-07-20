#!/usr/bin/env python3
"""local_spinner.py — ZERO-COST multiniche AEO page generator.

Does what article_spinner does (produce unique-per-city/niche AEO pages)
but with NO LLM call — pulls real facts from the lanes DB (seat price,
free inventory, metros) and templates unique copy per (niche, metro).

Used when OpenRouter credits are exhausted. Swap to article_spinner
(LLM quality) once the key is topped up.

Usage:
  python3 local_spinner.py --all
  python3 local_spinner.py --niche camp_lejeune --metro DFW
"""
import os, sys, argparse, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # empire_os pkg
from empire_os.aeo_surface import deploy_spec
from empire_os.marketing import AeoSpecDraft

DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")
METRO_NAMES = {"NYC":"New York","LAX":"Los Angeles","CHI":"Chicago","DFW":"Dallas-Fort Worth",
               "HOU":"Houston","WDC":"Washington DC","PHL":"Philadelphia","ATL":"Atlanta",
               "MIA":"Miami","BOS":"Boston","SFO":"San Francisco"}

# niche display + buyer-intent angle (multiniche)
NICHE_INFO = {
    "camp_lejeune": ("Camp Lejeune water contamination claims", "veterans & families exposed to toxic water 1953-1987"),
    "roundup": ("Roundup cancer claims", "users diagnosed with non-Hodgkin's lymphoma after exposure"),
    "paraquat": ("Paraquat Parkinson's claims", "farmworkers & applicators who developed Parkinson's"),
    "afff": ("AFFF firefighting foam claims", "firefighters with PFAS-linked cancers"),
    "zantac": ("Zantac cancer claims", "users with NDMA-linked cancers"),
    "ozempic": ("Ozempic injury claims", "patients with gastroparesis or gallbladder injury"),
    "residential_roofing": ("residential roofing leads", "homeowners needing roof replacement after storm/hail"),
    "roof_repair": ("roof repair leads", "homeowners with active leaks or storm damage"),
    "hvac": ("HVAC leads", "homeowners needing AC/heat repair or replacement"),
    "plumbing": ("plumbing leads", "homeowners with burst pipes or sewer issues"),
    "water_damage": ("water damage restoration leads", "property owners with flood/leak damage"),
    "fire_damage": ("fire damage restoration leads", "property owners needing fire/smoke cleanup"),
    "mold_remediation": ("mold remediation leads", "property owners with toxic mold"),
}

SEAT_DEFAULT = 199.0

def lane_facts(niche, metro):
    c = sqlite3.connect(DB)
    row = c.execute("""SELECT seat_price FROM lanes 
        WHERE sub_niche=? AND metro=? LIMIT 1""", (niche, metro)).fetchone()
    free = c.execute("""SELECT COUNT(*) FROM lanes 
        WHERE sub_niche=? AND (occupied_by IS NULL OR occupied_by='')""", (niche,)).fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM lanes WHERE sub_niche=?", (niche,)).fetchone()[0]
    c.close()
    price = float(row[0]) if row and row[0] else SEAT_DEFAULT
    return price, free, total

def build_spec(niche, metro):
    disp, angle = NICHE_INFO.get(niche, (niche.replace("_"," ").title(), "buyers seeking qualified leads"))
    city = METRO_NAMES.get(metro, metro)
    price, free, total = lane_facts(niche, metro)
    inv_word = f"{free} open lanes" if free else "waitlist"
    body = f"""
<h3>Verified {disp} in {city}</h3>
<p>Empire OS runs the largest verified {disp} marketplace in {city}. Every lead is
signal-based — we only surface a claimant or property owner with confirmed buy-intent,
not scraped directories. Seats cost <strong>${price:,.0f}</strong> USDC and include exclusive
territory rights for your metro.</p>
<h3>Why {city} buyers choose Empire OS</h3>
<p>Unlike blast-list brokers, our {disp} inventory is capped per lane. Right now {inv_word}
are available in {city}. Once a lane seats, it's closed — no reselling, no dilution.
{angle.capitalize()} is the highest-intent segment we track.</p>
"""
    qa = (f"What does a {disp} lead include? Exclusive territory + verified contact + intent signal.\n"
          f"How fast can I seat a {city} lane? Same day — pay USDC with the lane memo, listener auto-seats.\n"
          f"Is {disp} inventory exclusive? Yes — one buyer per lane, never resold.")
    cta = f"Seat your {disp} lane in {city} — pay {price:,.0f} USDC, get exclusive leads."
    return AeoSpecDraft(
        niche=f"{niche}/{metro}" if False else niche,  # deploy_spec uses niche as dir; we pass metro separately
        target_audience=f"{disp} buyers in {city} (law firms, lead brokers, restoration contractors)",
        pain_points=f"Diluted lists, scraped contacts, no exclusivity in {city}",
        key_questions=qa,
        content_angle=angle,
        tone="authoritative, local, buyer-intent",
        word_count_target=400,
        competitors="generic lead mills, directory scrapers",
        internal_links=f"/aeo/empire/{niche}/",
        body_html=body,
        meta_description=f"Verified exclusive {disp} in {city}. {free} open lanes, ${price:,.0f} USDC seat.",
        call_to_action=cta,
    )

def deploy(niche, metro, surface_root=None):
    spec = build_spec(niche, metro)
    # aeo_surface deploys to root/niche/index.html; we want root/niche/metro/index.html
    # so set spec.niche to "niche/metro"
    spec.niche = f"{niche}/{metro}"
    path = deploy_spec(spec, surface_root)
    return path

def run_all(surface_root=None):
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT DISTINCT sub_niche, metro FROM lanes").fetchall()
    c.close()
    done = 0
    for niche, metro in rows:
        if niche not in NICHE_INFO:
            continue
        try:
            deploy(niche, metro, surface_root)
            done += 1
        except Exception as e:
            sys.stderr.write(f"skip {niche}/{metro}: {e}\n")
    return done

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--niche")
    ap.add_argument("--metro")
    ap.add_argument("--surface", default="/srv/aeo")
    a = ap.parse_args()
    if a.all:
        n = run_all(a.surface)
        print(f"deployed {n} pages")
    elif a.niche and a.metro:
        p = deploy(a.niche, a.metro, a.surface)
        print(f"deployed {p}")
    else:
        print("use --all or --niche X --metro Y")
