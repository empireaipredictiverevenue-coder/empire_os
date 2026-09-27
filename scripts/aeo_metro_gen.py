#!/usr/bin/env python3
"""Empire AI premium AEO metro page generator.

Generates evidence-safe, premium local intelligence pages for every
niche x metro combination. The pages do not invent live counts, delivery
SLAs, exclusivity, pricing, customer outcomes or availability.

Publishing remains a separate governed step.
"""
from __future__ import annotations

import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

NICHE_INFO = {
    "plumbing": ("Plumbing", "drain cleaning, leak repair, water heaters, pipe failures"),
    "hvac": ("HVAC & Air Conditioning", "heating, cooling, heat pumps, ductwork"),
    "roofing": ("Roofing", "repair, replacement, storm damage, gutters"),
    "electrical": ("Electrical", "panel upgrades, rewiring, EV chargers, generators"),
    "landscaping": ("Landscaping", "lawn care, tree work, irrigation, hardscaping"),
    "painting": ("Painting", "interior, exterior, cabinets, decks"),
    "mold_remediation": ("Mold Remediation", "testing, removal, prevention, restoration"),
    "lead_remediation": ("Lead Paint Remediation", "testing, abatement, compliance work"),
    "asbestos_remediation": ("Asbestos Remediation", "testing, encapsulation, removal"),
    "water_damage_restoration": ("Water Damage Restoration", "extraction, drying, rebuild"),
    "fire_damage_restoration": ("Fire & Smoke Restoration", "cleanup, deodorization, rebuild"),
    "disaster_recovery": ("Disaster Recovery", "storm, flood, debris, emergency recovery"),
    "sewage_cleanup": ("Sewage Cleanup", "extraction, sanitization, decontamination"),
    "emergency_plumbing": ("Emergency Plumbing", "burst pipes, sewage backup, urgent repairs"),
    "carpentry": ("Carpentry", "decks, cabinets, framing, finish work"),
    "general_contractor": ("General Contracting", "remodels, additions, renovations"),
    "structural_repair": ("Structural Repair", "foundations, beams, load-bearing systems"),
    "pest_control": ("Pest Control", "termite, rodent, bedbug, exclusion"),
    "hvac_repair": ("HVAC Repair", "furnace, AC, heat-pump diagnostics"),
    "ai_automation": ("AI Automation Consulting", "workflow automation, AI integration"),
    "marketing": ("Marketing Agencies", "paid media, search, content, conversion"),
    "consulting": ("Business Consulting", "strategy, operations, commercial improvement"),
    "legal_services": ("Legal Services", "business law, contracts, specialist services"),
    "accounting": ("Accounting & Bookkeeping", "tax, bookkeeping, payroll, advisory"),
    "cybersecurity": ("Cybersecurity", "risk assessment, compliance, security operations"),
    "data_analytics": ("Data Analytics", "business intelligence, forecasting, decision support"),
    "cloud": ("Cloud Infrastructure", "AWS, GCP, Azure, migration, platform operations"),
    "managed_it": ("Managed IT Services", "support, monitoring, security, infrastructure"),
    "real_estate": ("Real Estate", "residential, commercial, investment"),
    "insurance": ("Insurance", "home, auto, life, commercial"),
    "mortgage": ("Mortgage", "purchase, refinance, commercial"),
    "web_dev": ("Web Development", "web applications, ecommerce, conversion experiences"),
    "software_dev": ("Software Development", "MVPs, platforms, enterprise systems"),
    "staffing": ("Staffing", "temporary, contract, direct hire"),
    "tax_prep": ("Tax Preparation", "personal, business, advisory"),
    "investing": ("Investment Advisory", "portfolio, retirement, private markets"),
    "weight_loss": ("Weight Management", "medical, surgical, lifestyle programmes"),
    "dental": ("Dental Services", "implants, cosmetic, family dentistry"),
    "vision": ("Vision & Eye Care", "exams, corrective care, specialist services"),
    "addiction": ("Addiction Treatment", "detox, rehabilitation, outpatient support"),
    "debt_relief": ("Debt Relief", "consolidation, settlement, credit improvement"),
    "pt_rehab": ("Physical Therapy", "post-surgical, sports, chronic pain"),
}

METROS = {
    "NYC": (
        "New York City",
        "NY",
        "Manhattan, Brooklyn, Queens, the Bronx, Staten Island, Long Island and Westchester",
    ),
    "LAX": (
        "Los Angeles",
        "CA",
        "Los Angeles, Long Beach, Pasadena, Santa Monica and the San Fernando Valley",
    ),
    "CHI": (
        "Chicago",
        "IL",
        "Chicago, the North Shore, western suburbs, South Side and Northwest Indiana",
    ),
    "DFW": (
        "Dallas-Fort Worth",
        "TX",
        "Dallas, Fort Worth, Arlington, Plano, Frisco, Irving and surrounding suburbs",
    ),
    "SFO": (
        "San Francisco Bay Area",
        "CA",
        "San Francisco, Oakland, San Jose, Berkeley, Palo Alto and surrounding cities",
    ),
}

SIGNAL_LIBRARY = {
    "home_services": (
        "Local search demand and query momentum",
        "Weather, permit and property signals where relevant",
        "Competitor visibility and service-area coverage",
        "Decision-maker and operator readiness",
    ),
    "professional": (
        "Buyer-intent search themes",
        "Competitive positioning and category movement",
        "Company and decision-maker signals",
        "Commercial timing and follow-up readiness",
    ),
    "digital": (
        "Search visibility and high-intent query gaps",
        "Technology and hiring signals",
        "Competitive product positioning",
        "Decision-maker and growth intent",
    ),
    "health": (
        "Local demand and service-intent trends",
        "Search visibility and competitor presence",
        "Geographic access and category positioning",
        "Reputation and citation signals",
    ),
    "finance": (
        "Buyer-intent search demand",
        "Market and company signals",
        "Competitive visibility and positioning",
        "Commercial timing and decision-maker evidence",
    ),
}

HOME_SERVICE_KEYS = {
    "plumbing", "hvac", "roofing", "electrical", "landscaping", "painting",
    "mold_remediation", "lead_remediation", "asbestos_remediation",
    "water_damage_restoration", "fire_damage_restoration", "disaster_recovery",
    "sewage_cleanup", "emergency_plumbing", "carpentry", "general_contractor",
    "structural_repair", "pest_control", "hvac_repair",
}
DIGITAL_KEYS = {
    "ai_automation", "marketing", "cybersecurity", "data_analytics", "cloud",
    "managed_it", "web_dev", "software_dev",
}
HEALTH_KEYS = {"weight_loss", "dental", "vision", "addiction", "pt_rehab"}
FINANCE_KEYS = {"accounting", "insurance", "mortgage", "tax_prep", "investing", "debt_relief"}

USE_CASES = {
    "roofing": (
        "Storm and hail demand",
        "Local search gaps",
        "Territory prioritisation",
        "Roofing company capacity and decision-maker evidence",
    ),
    "hvac": (
        "Seasonal heating and cooling demand",
        "Local search gaps",
        "Service-area competition",
        "Operator and decision-maker evidence",
    ),
    "plumbing": (
        "Urgent repair demand",
        "Local search gaps",
        "Service-area competition",
        "Operator and decision-maker evidence",
    ),
    "marketing": (
        "Buyer-intent search themes",
        "Competitor positioning",
        "Client-acquisition pain",
        "Agency growth and decision-maker signals",
    ),
    "ai_automation": (
        "Manual-workflow pain",
        "Automation buying intent",
        "Technology signals",
        "Decision-maker and implementation readiness",
    ),
    "cybersecurity": (
        "Security/compliance intent",
        "Technology and hiring signals",
        "Competitive search visibility",
        "Decision-maker evidence",
    ),
}


def category_for(niche: str) -> str:
    if niche in HOME_SERVICE_KEYS:
        return "home_services"
    if niche in DIGITAL_KEYS:
        return "digital"
    if niche in HEALTH_KEYS:
        return "health"
    if niche in FINANCE_KEYS:
        return "finance"
    return "professional"


def esc(value: str) -> str:
    return html.escape(str(value), quote=True)


def service_signals(niche: str) -> tuple[str, ...]:
    return USE_CASES.get(niche, SIGNAL_LIBRARY[category_for(niche)])


def page_schema(
    *,
    niche: str,
    niche_name: str,
    niche_desc: str,
    metro: str,
    metro_label: str,
) -> str:
    canonical = f"https://empire-ai.co.uk/aeo/{niche}/{metro}"
    payload = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": f"{niche_name} Market Intelligence — {metro_label}",
        "description": (
            f"Commercial intelligence for {niche_name.lower()} markets in "
            f"{metro_label}: {niche_desc}."
        ),
        "url": canonical,
        "about": {
            "@type": "Service",
            "name": f"{niche_name} market intelligence",
            "areaServed": {
                "@type": "AdministrativeArea",
                "name": metro_label,
            },
            "provider": {
                "@type": "Organization",
                "name": "Empire AI",
                "url": "https://empire-ai.co.uk",
            },
        },
    }
    return json.dumps(payload, separators=(",", ":"))


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_description}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="geo.region" content="US-{state}">
<meta name="geo.placename" content="{metro_label}">
<meta name="theme-color" content="#07110d">
<script type="application/ld+json">{schema}</script>
<style>
:root {{
  --bg:#07110d; --panel:#0b1712; --panel2:#0f1e18; --line:rgba(226,255,238,.11);
  --text:#edf7f1; --muted:#8fa79b; --dim:#61756b; --accent:#65e6a7; --accent2:#aef2cf;
}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
body{{margin:0;background:
radial-gradient(circle at 80% -10%,rgba(62,168,113,.14),transparent 36%),
linear-gradient(180deg,#08130f 0%,var(--bg) 45%,#050c09 100%);
color:var(--text);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
line-height:1.55;-webkit-font-smoothing:antialiased}}
a{{color:inherit}} .wrap{{max-width:1180px;margin:auto;padding:0 28px}}
nav{{display:flex;align-items:center;justify-content:space-between;padding:25px 0;border-bottom:1px solid var(--line)}}
.brand{{display:flex;gap:11px;align-items:center;font-weight:750;letter-spacing:-.02em}}
.mark{{width:27px;height:27px;border:1px solid rgba(101,230,167,.55);border-radius:9px;
box-shadow:inset 0 0 22px rgba(101,230,167,.12);display:grid;place-items:center;color:var(--accent);font-size:11px}}
.navlink{{color:var(--muted);font-size:13px;text-decoration:none}} .navlink:hover{{color:var(--text)}}
.hero{{padding:92px 0 72px;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr);gap:72px;align-items:end}}
.kicker{{color:var(--accent);font-size:12px;font-weight:750;letter-spacing:.14em;text-transform:uppercase}}
h1{{font-size:clamp(45px,6vw,78px);line-height:.98;letter-spacing:-.055em;margin:18px 0 25px;max-width:850px}}
.lede{{font-size:18px;line-height:1.7;color:#b7c8bf;max-width:710px;margin:0}}
.actions{{display:flex;gap:12px;margin-top:34px;flex-wrap:wrap}}
.btn{{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 19px;border-radius:12px;text-decoration:none;font-size:13px;font-weight:720}}
.btn-primary{{background:var(--accent);color:#042116}} .btn-primary:hover{{background:var(--accent2)}}
.btn-secondary{{border:1px solid var(--line);background:rgba(255,255,255,.025);color:#d6e6de}}
.hero-card{{border:1px solid var(--line);background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.015));
border-radius:22px;padding:24px;box-shadow:0 24px 70px rgba(0,0,0,.25)}}
.label{{font-size:10px;text-transform:uppercase;letter-spacing:.14em;color:var(--dim);font-weight:750}}
.metric{{padding:17px 0;border-bottom:1px solid var(--line)}} .metric:last-child{{border-bottom:0}}
.metric strong{{display:block;font-size:15px;margin-top:6px}} .metric span{{font-size:12px;color:var(--muted)}}
.section{{padding:70px 0;border-top:1px solid var(--line)}} .section-head{{max-width:720px;margin-bottom:34px}}
h2{{font-size:clamp(30px,4vw,46px);letter-spacing:-.04em;line-height:1.08;margin:9px 0 14px}}
.copy{{color:var(--muted);font-size:15px;line-height:1.75}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.card{{border:1px solid var(--line);background:rgba(255,255,255,.022);border-radius:18px;padding:22px;min-height:166px}}
.card-index{{color:var(--accent);font-size:11px;font-weight:800;letter-spacing:.12em}}
.card h3{{font-size:16px;letter-spacing:-.02em;margin:35px 0 9px}} .card p{{font-size:13px;color:var(--muted);margin:0}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}
.panel{{border:1px solid var(--line);background:linear-gradient(145deg,rgba(255,255,255,.035),rgba(255,255,255,.012));border-radius:22px;padding:30px}}
.panel ul{{list-style:none;padding:0;margin:23px 0 0}} .panel li{{padding:12px 0;border-top:1px solid var(--line);font-size:14px;color:#c5d5cd}}
.panel li::before{{content:"↗";color:var(--accent);margin-right:10px}}
.method{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border:1px solid var(--line);border-radius:20px;overflow:hidden}}
.step{{padding:25px;border-right:1px solid var(--line);min-height:170px}} .step:last-child{{border-right:0}}
.step b{{font-size:11px;color:var(--accent);letter-spacing:.12em}} .step h3{{font-size:15px;margin:25px 0 8px}}
.step p{{font-size:12px;color:var(--muted);margin:0}}
.cta{{padding:74px 0}} .cta-box{{border:1px solid rgba(101,230,167,.22);background:
linear-gradient(135deg,rgba(101,230,167,.08),rgba(255,255,255,.015));border-radius:26px;padding:42px;display:flex;align-items:end;justify-content:space-between;gap:40px}}
.cta h2{{max-width:650px;margin-bottom:0}} .cta-copy{{max-width:420px;color:var(--muted);font-size:14px}}
footer{{border-top:1px solid var(--line);padding:28px 0 42px;color:var(--dim);font-size:12px}}
footer .row{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}
@media screen and (max-width:900px){{.hero{{grid-template-columns:1fr;gap:35px;padding-top:60px}}.grid,.method{{grid-template-columns:1fr 1fr}}.two{{grid-template-columns:1fr}}.step:nth-child(2){{border-right:0}}}}
@media screen and (max-width:620px){{.wrap{{padding:0 19px}}h1{{font-size:44px}}.grid,.method{{grid-template-columns:1fr}}.step{{border-right:0;border-bottom:1px solid var(--line)}}.cta-box{{padding:27px;display:block}}.cta-copy{{margin-top:22px}}}}
</style>
</head>
<body>
<div class="wrap">
<nav>
  <div class="brand"><span class="mark">E</span>Empire AI</div>
  <a class="navlink" href="https://empire-ai.co.uk">Predictive Revenue ↗</a>
</nav>

<main>
<section class="hero">
  <div>
    <div class="kicker">{metro_label} · {niche_name}</div>
    <h1>{niche_name} demand intelligence for {metro_label}.</h1>
    <p class="lede">See the commercial signals that matter before they become obvious: demand, search visibility, competitive movement and buyer timing across {coverage}.</p>
    <div class="actions">
      <a class="btn btn-primary" href="#intelligence">See what Empire measures</a>
      <a class="btn btn-secondary" href="https://empire-ai.co.uk">Explore Empire AI</a>
    </div>
  </div>
  <aside class="hero-card">
    <div class="label">Market brief</div>
    <div class="metric"><span>Category</span><strong>{niche_name}</strong></div>
    <div class="metric"><span>Market</span><strong>{metro_label}</strong></div>
    <div class="metric"><span>Commercial focus</span><strong>Demand · Search · Timing</strong></div>
    <div class="metric"><span>Evidence policy</span><strong>Observed first. Modelled clearly labelled.</strong></div>
  </aside>
</section>

<section class="section" id="intelligence">
  <div class="section-head">
    <div class="label">Commercial signal layer</div>
    <h2>Focus on the signals that can change the next move.</h2>
    <p class="copy">Empire combines public market evidence, search intelligence and company context into one operating view. No fabricated lead counts. No generic score pretending to be revenue.</p>
  </div>
  <div class="grid">
    {signal_cards}
  </div>
</section>

<section class="section">
  <div class="two">
    <div class="panel">
      <div class="label">{metro_label} context</div>
      <h2>Local context changes the answer.</h2>
      <p class="copy">{metro_context}. Search behaviour, service coverage, competition and timing can vary materially across the same metro.</p>
      <ul>
        <li>Separate observed demand from modelled opportunity</li>
        <li>Connect search evidence to companies and decision-makers</li>
        <li>Prioritise commercial timing instead of static lists</li>
      </ul>
    </div>
    <div class="panel">
      <div class="label">{niche_name} focus</div>
      <h2>Built around the buying problem.</h2>
      <p class="copy">For {niche_lower}, the useful question is not “how many records can we scrape?” It is which market conditions, search gaps and buyer signals justify action now.</p>
      <ul>
        {focus_items}
      </ul>
    </div>
  </div>
</section>

<section class="section">
  <div class="section-head">
    <div class="label">Empire method</div>
    <h2>Signal to action, without blurring the truth.</h2>
  </div>
  <div class="method">
    <div class="step"><b>01</b><h3>Observe</h3><p>Collect real market, search and company evidence with provenance.</p></div>
    <div class="step"><b>02</b><h3>Resolve</h3><p>Connect signals to the right market, company and commercial context.</p></div>
    <div class="step"><b>03</b><h3>Prioritise</h3><p>Rank what deserves attention using timing, fit and evidence strength.</p></div>
    <div class="step"><b>04</b><h3>Measure</h3><p>Track conversations, terms, payments and outcomes separately from forecasts.</p></div>
  </div>
</section>

<section class="cta">
  <div class="cta-box">
    <div>
      <div class="label">Predictive Revenue</div>
      <h2>Turn local market noise into a clearer commercial decision.</h2>
    </div>
    <div class="cta-copy">
      Empire AI connects market intelligence, Search, CRM and Revenue Pulse so teams can see what is changing, why it matters and what deserves attention next.
      <div class="actions"><a class="btn btn-primary" href="https://empire-ai.co.uk">Explore the platform</a></div>
    </div>
  </div>
</section>
</main>

<footer>
  <div class="row">
    <span>© {year} Empire AI</span>
    <span>{metro_label} · {niche_name} market intelligence</span>
  </div>
</footer>
</div>
</body>
</html>
"""


def generate_page(niche: str, metro: str) -> str:
    name, desc = NICHE_INFO[niche]
    metro_label, state, coverage = METROS[metro]
    signals = service_signals(niche)

    signal_cards = []
    for index, signal in enumerate(signals, start=1):
        signal_cards.append(
            '<article class="card">'
            f'<div class="card-index">0{index}</div>'
            f'<h3>{esc(signal)}</h3>'
            '<p>Used as evidence for market prioritisation and commercial context, '
            'not as a substitute for verified outcomes.</p></article>'
        )

    focus_items = "".join(
        f"<li>{esc(signal)}</li>"
        for signal in signals
    )

    canonical = f"https://empire-ai.co.uk/aeo/{niche}/{metro}"
    seo_label = niche.replace("_", " ").title().replace("Ai ", "AI ")
    title = f"{seo_label} — {metro_label}"
    meta = (
        f"{name} market intelligence for {metro_label}: demand signals, "
        "search visibility, competitive movement and commercial timing."
    )

    replacements = {
        "title": esc(title),
        "meta_description": esc(meta),
        "canonical": esc(canonical),
        "state": esc(state),
        "schema": page_schema(
            niche=niche,
            niche_name=name,
            niche_desc=desc,
            metro=metro,
            metro_label=metro_label,
        ),
        "niche_name": esc(name),
        "niche_lower": esc(name.lower()),
        "metro_label": esc(metro_label),
        "coverage": esc(coverage),
        "metro_context": esc(
            f"The {metro_label} market spans {coverage}"
        ),
        "signal_cards": "".join(signal_cards),
        "focus_items": focus_items,
        "year": str(datetime.now(timezone.utc).year),
    }
    page = PAGE_TEMPLATE.replace("{{", "{").replace("}}", "}")
    for key, value in replacements.items():
        page = page.replace("{" + key + "}", value)
    return page


def build_pages(output_root: Path) -> int:
    count = 0
    for niche in NICHE_INFO:
        for metro in METROS:
            page_dir = output_root / niche / metro
            page_dir.mkdir(parents=True, exist_ok=True)
            (page_dir / "index.html").write_text(
                generate_page(niche, metro),
                encoding="utf-8",
            )
            count += 1
    return count


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = repo_root / "scripts" / "_aeo_pages"
    archive = repo_root / "scripts" / "aeo_metro_pages.tar.gz"
    output_root.mkdir(parents=True, exist_ok=True)

    count = build_pages(output_root)
    subprocess.run(
        ["tar", "-czf", str(archive), "-C", str(output_root), "."],
        check=True,
    )
    print(json.dumps({
        "generated_pages": count,
        "output_root": str(output_root),
        "archive": str(archive),
        "publishing_performed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
