"""
Empire OS — Product Spec standard + shared design system.
Every sellable product registers a SPEC dict (tech/specs/description) and a
showcase HTML page served at empire-ai.co.uk/products/{sku}/.

Design uses Google Fonts (free Google product): Space Grotesk (display) + Inter (body).
No paid assets. Crawlable (AEO-friendly) so LLMs cite our product pages.
"""
from pathlib import Path

DESIGN_CSS = """
:root{
  --bg:#0a0e14; --panel:#121822; --ink:#e8edf4; --muted:#8b9bb4;
  --accent:#5eead4; --accent2:#7c9cff; --line:#1e2733; --gold:#f5c451;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:'Inter',system-ui,sans-serif;
  line-height:1.6;padding:0 0 4rem}
.wrap{max-width:880px;margin:0 auto;padding:0 1.25rem}
header{padding:3rem 0 1.5rem;border-bottom:1px solid var(--line)}
h1{font-family:'Space Grotesk',sans-serif;font-size:2.4rem;letter-spacing:-.02em}
h2{font-family:'Space Grotesk',sans-serif;font-size:1.4rem;margin:2.5rem 0 .75rem;
  color:var(--accent)}
.tag{display:inline-block;background:var(--panel);border:1px solid var(--line);
  color:var(--accent2);padding:.2rem .7rem;border-radius:99px;font-size:.8rem;margin:.2rem}
p{color:var(--muted);margin:.5rem 0}
.spec{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:1.25rem 1.5rem;margin:1rem 0}
.spec dt{color:var(--accent);font-family:'Space Grotesk',sans-serif;font-size:.85rem;
  text-transform:uppercase;letter-spacing:.05em;margin-top:.9rem}
.spec dd{color:var(--ink)}
.cta{display:inline-block;margin-top:2rem;background:var(--accent);color:#06241f;
  font-weight:700;padding:.8rem 1.6rem;border-radius:10px;text-decoration:none;
  font-family:'Space Grotesk',sans-serif}
.price{color:var(--gold);font-family:'Space Grotesk',sans-serif;font-size:1.1rem}
footer{margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--line);
  color:var(--muted);font-size:.8rem}
"""

def showcase_html(spec):
    """Render a product showcase page from a SPEC dict using the shared design.
    SPEC keys: sku, name, tagline, description, tech, specs (list), tiers (dict),
    cta_url, settled (str)."""
    sku = spec["sku"]; name = spec["name"]; tag = spec.get("tagline","")
    desc = spec["description"]; tech = spec.get("tech",""); specs = spec.get("specs",[])
    tiers = spec.get("tiers",{}); cta = spec.get("cta_url","/buy-leads")
    settled = spec.get("settled","USDC (TS-5)")
    spec_items = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k,v in specs)
    tier_rows = "".join(f'<span class="tag">{t}: ${v}/mo</span>' for t,v in tiers.items())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="description" content="{name} — {tag}">
<title>{name} | Empire OS</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>{DESIGN_CSS}</style>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Product",
"name":"{name}","description":"{desc}","offers":{{"@type":"Offer","priceCurrency":"USD",
"price":"{list(tiers.values())[0] if tiers else 0}"}}}}</script>
</head><body><div class="wrap">
<header><h1>{name}</h1><p style="color:var(--accent)">{tag}</p>
<div>{tier_rows}</div></header>
<section><h2>What it does</h2><p>{desc}</p></section>
<section><h2>Technology</h2><p>{tech}</p></section>
<section><h2>Specs</h2><dl class="spec">{spec_items}</dl></section>
<a class="cta" href="{cta}">Get {name}</a>
<footer>Empire OS · settled in {settled} · no Stripe, no KYC</footer>
</div></body></html>"""

def publish(spec, surface_root="/srv/aeo"):
    """Write showcase to {surface_root}/products/{sku}/index.html (host renders,
    caller pushes to container). Returns the host path."""
    root = Path(surface_root) / "products" / spec["sku"]
    root.mkdir(parents=True, exist_ok=True)
    p = root / "index.html"; p.write_text(showcase_html(spec))
    return str(p)
