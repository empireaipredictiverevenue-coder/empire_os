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

SEAT_DEFAULT = 299.0  # bronze seat floor (niche_map.TIER_SEAT_CENTS)

import re as _re
def _md_to_html(md: str) -> str:
    """Minimal Markdown->HTML (stdlib only): headings, bold, paragraphs.
    Groq returns Markdown; injecting raw into <p> renders literal ### / **.
    Line-based (not block-based) so a `### heading` that Groq emits without a
    preceding blank line is still converted, never leaked as literal text."""
    out, para = [], []
    def flush():
        if para:
            txt = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", " ".join(para))
            out.append(f"<p>{txt}</p>")
            para.clear()
    for line in md.strip().splitlines():
        s = line.strip()
        if not s:
            flush(); continue
        h = _re.match(r"^(#{1,6})\s+(.*)$", s)
        if h:
            flush()
            lvl = 3 if len(h.group(1)) <= 3 else 4  # #/##/### -> h3, deeper -> h4
            txt = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h.group(2))
            out.append(f"<h{lvl}>{txt}</h{lvl}>")
        else:
            para.append(s)
    flush()
    return "".join(out)

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

def build_spec(niche, metro, llm=False):
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
    if llm:
        try:
            import os, sys
            sys.path.insert(0, os.path.dirname(__file__))
            import article_spinner as SP
            if os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
                spun = SP.spin(body, niche, city, n=1)[0]
                if not spun.startswith("# spin error"):
                    body = f"<h3>Verified {disp} in {city}</h3>" + _md_to_html(spun)
        except Exception as e:
            sys.stderr.write(f"llm spin failed, using template: {e}\n")
    signup_form = (
        f'<div class="cta"><p>Seat your {disp} lane in {city} — pay {price:,.0f} USDC, get exclusive leads.</p>'
        f'<p><a class="cta-btn" href="https://empire-ai.co.uk/v1/outreach/prospect/register?niche={niche}&amp;city={city}">'
        f'Get Verified {disp} &rarr;</a></p>'
        f'<form action="/v1/outreach/prospect/register" method="POST" class="signup">'
        f'<input type="hidden" name="niche" value="{niche}">'
        f'<input type="hidden" name="metro" value="{city}">'
        f'<input type="email" name="email" placeholder="you@firm.com" required>'
        f'<button type="submit">Get Leads</button></form></div>'
    )
    return AeoSpecDraft(
        niche=niche,
        target_audience=f"{disp} buyers in {city} (law firms, lead brokers, restoration contractors)",
        pain_points=f"Diluted lists, scraped contacts, no exclusivity in {city}",
        key_questions=(f"What does a {disp} lead include? Exclusive territory + verified contact + intent signal.\n"
          f"How fast can I seat a {city} lane? Same day — pay USDC with the lane memo, listener auto-seats.\n"
          f"Is {disp} inventory exclusive? Yes — one buyer per lane, never resold."),
        content_angle=angle,
        tone="authoritative, local, buyer-intent",
        word_count_target=400,
        competitors="generic lead mills, directory scrapers",
        internal_links=f"/aeo/empire/{niche}/",
        body_html=body + signup_form,
        meta_description=f"Verified exclusive {disp} in {city}. {free} open lanes, ${price:,.0f} USDC seat.",
        call_to_action=f"Seat your {disp} lane in {city} — pay {price:,.0f} USDC, get exclusive leads.",
    )

def deploy(niche, metro, surface_root=None, llm=False):
    spec = build_spec(niche, metro, llm=llm)
    # aeo_surface deploys to root/niche/index.html; we want root/niche/metro/index.html
    # so set spec.niche to "niche/metro"
    spec.niche = f"{niche}/{metro}"
    path = deploy_spec(spec, surface_root)
    return path

def run_all(surface_root=None, llm=False):
    c = sqlite3.connect(DB)
    rows = c.execute("SELECT DISTINCT sub_niche, metro FROM lanes").fetchall()
    c.close()
    done = 0
    for niche, metro in rows:
        if niche not in NICHE_INFO:
            continue
        try:
            deploy(niche, metro, surface_root, llm=llm)
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
    ap.add_argument("--llm", action="store_true",
                    help="spin unique copy via Groq (GROQ_API_KEY) / OpenRouter; falls back to template on error")
    a = ap.parse_args()
    if a.all:
        n = run_all(a.surface, llm=a.llm)
        print(f"deployed {n} pages (llm={a.llm})")
    elif a.niche and a.metro:
        p = deploy(a.niche, a.metro, a.surface, llm=a.llm)
        print(f"deployed {p} (llm={a.llm})")
    else:
        print("use --all or --niche X --metro Y  [--llm]")
