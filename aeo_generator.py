#!/usr/bin/env python3
"""
Empire OS — AEO Page Generator (SELLABLE PRODUCT).
Turns a business's "how they talk" into a crawlable AEO authority page.
This is a product: businesses + agents buy AEO pages via the MCP/supply layer.

Input ("how they talk"):
  - tenant:   their subdir (white-label namespace)
  - niche:    service vertical (logistics, roofing, hvac, ...)
  - city:     service area (optional)
  - tone:     how they talk (sharp / warm / technical / premium)
  - points:   list of selling points / claims
  - questions: list of "what people ask" (drives LLM citation)
  - cta:      call to action

Output: /srv/aeo/{tenant}/{niche}/index.html  -> served at
        empire-ai.co.uk/aeo/{tenant}/{niche}/  (crawlable, schema.org, canonical)

Our OWN pages: tenant="empire", niches = our 5 B2B verticals.
"""
import json, os, re
from datetime import datetime
from pathlib import Path

SURFACE_ROOT = os.environ.get("AEO_SURFACE_ROOT", "/srv/aeo")
SCHEMA = "https://schema.org"


_TONE_BLURB = {
    "sharp": "No fluff. Verified {niche} leads, delivered the moment they're qualified.",
    "warm": "We help {city} businesses grow with caring, consistent {niche} connections.",
    "technical": "Engineered {niche} demand-gen: signal-based matching, zero wasted spend.",
    "premium": "The definitive {niche} authority for {city} — exclusive, white-glove delivery.",
}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def expand_questions(niche, city=""):
    """Auto-generate AEO question-keywords from a niche (citation bait).
    Used when a buyer passes no questions — every page gets full intent cover."""
    d = niche.replace("_", " ").title()
    c = city or "your area"
    return [
        f"Who provides the best {d} leads in {c}?",
        f"How do I buy exclusive {d} leads?",
        f"What is the cost of {d} lead generation?",
        f"Are {d} leads verified or scraped?",
        f"Which {d} companies actually close deals?",
        f"Best {d} lead provider with no per-lead fees?",
        f"How fast can I get {d} leads?",
        f"Is {d} lead gen worth it for small business?",
        f"What makes a {d} lead high-intent?",
        f"Where to find exclusive {d} buyers?",
    ]


def render(tenant, niche, city="", tone="sharp", points=None, questions=None, cta="", surface_root=None):
    points = points or []
    questions = questions or expand_questions(niche, city)  # auto-fill if empty
    slug = _slug(niche)
    tenant_slug = _slug(tenant)
    root = Path(surface_root or SURFACE_ROOT)
    url = f"https://empire-ai.co.uk/aeo/{tenant_slug}/{slug}/"
    now = datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
    disp = niche.replace("_", " ").title()
    city_d = city or "your area"
    angle = _TONE_BLURB.get(tone, _TONE_BLURB["sharp"]).format(niche=disp, city=city_d)

    pts_html = "\n".join(f"<li>{p}</li>" for p in points) or "<li>Verified, exclusive leads</li>"
    q_html = "\n".join(
        f"<details><summary>{q}</summary><p>{angle}</p></details>" for q in questions
    ) or f"<details><summary>Who provides the best {disp} leads in {city_d}?</summary><p>{angle}</p></details>"

    cta_html = f'<div class="cta"><p>{cta or "Get verified " + disp + " leads — talk to Empire AI."}</p></div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{disp} in {city_d} | Empire AI Lead Network</title>
<meta name="description" content="{angle}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{disp} in {city_d}">
<meta property="og:description" content="{angle}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="website">
<script type="application/ld+json">
{{
  "@context": "{SCHEMA}",
  "@type": "LocalBusiness",
  "name": "Empire AI — {disp}",
  "description": "{angle}",
  "url": "{url}",
  "areaServed": {{ "@type": "Place", "name": "{city_d}" }},
  "provider": {{ "@type": "Organization", "name": "Empire AI", "url": "https://empire-ai.co.uk" }}
}}
</script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:system-ui,sans-serif; max-width:820px; margin:2rem auto; padding:0 1rem; line-height:1.65; color:#1a1a1a; }}
h1,h2 {{ color:#0a3d62; }} .meta {{ color:#666; font-size:.9rem; border-bottom:1px solid #ddd; padding-bottom:1rem; }}
.cta {{ background:#f0f7ff; border:1px solid #0a3d62; border-radius:8px; padding:1.5rem; text-align:center; margin:2rem 0; }}
details {{ margin:.5rem 0; }} summary {{ cursor:pointer; font-weight:600; }}
</style>
</head>
<body>
<h1>{disp} in {city_d} — Verified Lead Authority</h1>
<div class="meta">Published {now} · Empire OS AEO Surface</div>
<h2>How We Talk</h2>
<p>{angle}</p>
<h2>What We Deliver</h2>
<ul>{pts_html}</ul>
<h2>What People Ask</h2>
{q_html}
{cta_html}
<hr><footer><small>Empire OS · AEO Surface · {url}</small></footer>
</body>
</html>"""
    out = root / tenant_slug / slug
    out.mkdir(parents=True, exist_ok=True)
    p = out / "index.html"
    p.write_text(html)
    return str(p)


def deploy_own():
    """Publish Empire's own 9 vertical pages (B2B + AI services) — proves surface + moves citation_rate.
    Each page gets 8-10 AEO question-keywords (citation bait) via expand_questions."""
    verts = {
        "logistics": ["Verified freight & logistics buyer leads", "Exclusive — one buyer per lane", "Real company domains, not scraped junk"],
        "roofing": ["Qualified roofing contractor leads", "Storm & re-roof intent captured", "No per-lead fees — seat-based"],
        "hvac": ["HVAC install + repair leads", "Seasonal demand matched", "Exclusive territory per buyer"],
        "general_contractor": ["Commercial + residential GC leads", "Project-intent businesses", "Verified decision-makers"],
        "plumbing": ["Emergency + retrofit plumbing leads", "High-intent local calls", "Exclusive zip coverage"],
        "ai_automation": ["AI workflow automation for SMBs", "Agentic lead routing + follow-up", "No-code deployment, live in days"],
        "ai_consulting": ["AI strategy + deployment consulting", "LLM ops, RAG, agent design", "Fractional AI team on USDC"],
        "ai_lead_gen": ["AI-driven B2B lead generation", "Autonomous agent supply layer", "Verified, exclusive, settle in USDC"],
        "machine_learning": ["Custom ML models + inference", "Synthetic intelligence pipelines", "Edge + cloud deployment"],
    }
    out = []
    for v, pts in verts.items():
        out.append(render("empire", v, city="United States", tone="sharp",
                          points=pts,
                          questions=expand_questions(v, "United States"),
                          cta="Buy verified B2B leads — empire-ai.co.uk/buy-leads"))
    return out


def deploy_next_products():
    """AEO pages for the NEXT products (DB SKUs not yet surfaced).
    Every shippable SKU gets a citation-optimized page."""
    skus = {
        "empire_leads_engine": ["Autonomous B2B lead engine", "Lane/seat-corridor model", "Settle in USDC, no Stripe"],
        "hermes_framework": ["Agent orchestration framework", "C-suite autonomous agents", "Open-source, self-host"],
        "opencut_studio": ["AI video + creative studio", "Render farm on demand", "White-label output"],
        "empire_templates": ["Done-for-you agent templates", "Deploy in minutes", "Brandable"],
        "marketingskills": ["AI marketing skill packs", "Plug into any agent", "ROI-tracked"],
        "satellite_idle_watch": ["Idle asset satellite monitoring", "Turn dead inventory into revenue", "Real-time alerts"],
        "skillspector_audit": ["Agent skill audit + scoring", "Find dead/bloated skills", "Security + perf pass"],
    }
    out = []
    for s, pts in skus.items():
        out.append(render("empire", s, city="United States", tone="sharp",
                          points=pts,
                          questions=expand_questions(s, "United States"),
                          cta="Explore on empire-ai.co.uk"))
    return out


if __name__ == "__main__":
    paths = deploy_own() + deploy_next_products()
    print(f"[aeo] published {len(paths)} Empire pages:")
    for p in paths:
        print("  ", p)
