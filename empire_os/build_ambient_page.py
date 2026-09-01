#!/usr/bin/env python3
"""Generate the Empire Ambient AI product landing page with live price/description
from PRODUCT_CATALOG, plus a pay-link to /v1/pay/prod:AMBIENT-AI."""
import sys, html, json
sys.path.insert(0, "/root/empire_os")
from empire_os.empire_intelligence_product import PRODUCT_CATALOG

OUT = "/srv/aeo/empire_ambient_ai/index.html"

ambient = PRODUCT_CATALOG["AMBIENT-AI"]
whale = PRODUCT_CATALOG["AMBIENT-AI-WHALE"]

def page(p):
    price = f"${p.price_usd:,.0f}"
    desc = html.escape(p.description)
    meta_desc = html.escape(p.meta_description or p.description[:155])
    seo_title = html.escape(p.seo_title or p.name)
    keywords = html.escape(p.keywords)
    # JSON-LD Product schema (rich result: price + availability)
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Product",
        "name": p.name,
        "description": p.description,
        "brand": {"@type": "Brand", "name": "Empire AI"},
        "offers": {
            "@type": "Offer",
            "price": p.price_usd,
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
            "url": f"https://empire-ai.co.uk/v1/pay/prod:{p.sku}",
        },
    })
    kw_list = "".join(f"<span class='kw'>{k.strip()}</span>" for k in p.keywords.split(",")[:12])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{seo_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{keywords}">
<meta property="og:title" content="{seo_title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="product">
<script type="application/ld+json">{jsonld}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a12;color:#e6f1ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6}}
.wrap{{max-width:760px;margin:0 auto;padding:60px 24px}}
.logo{{font-size:20px;font-weight:800;letter-spacing:-.5px;margin-bottom:30px}}
.logo .b{{color:#00BFFF}}.logo .g{{color:#39FF14}}
h1{{font-size:38px;font-weight:800;line-height:1.15;margin-bottom:16px;
   background:linear-gradient(90deg,#00BFFF,#39FF14);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.price{{font-size:54px;font-weight:800;color:#39FF14;margin:24px 0 4px}}
.price small{{font-size:18px;color:#7fa8c9;font-weight:500}}
.billing{{color:#7fa8c9;font-size:14px;margin-bottom:28px}}
.desc{{color:#9fb6cc;font-size:16px;margin-bottom:32px}}
.cta{{display:inline-block;background:#39FF14;color:#0a0a12;font-weight:800;font-size:17px;
     padding:16px 38px;border-radius:12px;text-decoration:none;transition:all .2s}}
.cta:hover{{background:#2ee67a;box-shadow:0 8px 28px rgba(57,255,20,.3)}}
.tag{{display:inline-block;border:1px solid rgba(0,191,255,.3);color:#00BFFF;
     font-size:11px;letter-spacing:2px;text-transform:uppercase;padding:5px 12px;border-radius:20px;margin-bottom:22px}}
ul{{margin:24px 0 32px;padding-left:20px;color:#9fb6cc}}
li{{margin-bottom:8px}}
.feat{{color:#cfe0f0;font-weight:600}}
.kwbox{{margin:28px 0;display:flex;flex-wrap:wrap;gap:8px}}
.kw{{background:rgba(0,191,255,.08);border:1px solid rgba(0,191,255,.2);color:#7fb8e0;
    font-size:12px;padding:5px 11px;border-radius:20px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo">Empire <span class="b">AI</span> <span class="g">AMBIENT</span></div>
  <span class="tag">Ambient Intelligence Layer · Powered by Layer 23 Brain</span>
  <h1>{html.escape(p.name)}</h1>
  <div class="price">{price}<small> /month</small></div>
  <div class="billing">Billed monthly · Cancel anytime · Settled in USDT (BSC)</div>
  <p class="desc">{desc}</p>
  <ul>
    <li><span class="feat">Silent operation</span> — no dashboards to babysit, no prompts to type</li>
    <li><span class="feat">Omega scoring</span> on every contact, continuously</li>
    <li><span class="feat">Auto-trigger</span> the right agent action on buying signals</li>
    <li><span class="feat">50+ agent fleet</span> executes across your revenue stack</li>
    <li><span class="feat">Layer 23 Predictive Cloud brain</span> included</li>
  </ul>
  <a class="cta" href="https://empire-ai.co.uk/v1/pay/prod:{p.sku}" target="_blank" rel="noopener">⚡ Buy with USDT (BSC)</a>
  <div class="kwbox">{kw_list}</div>
</div>
</body>
</html>"""

if __name__ == "__main__":
    import os
    os.makedirs("/srv/aeo/empire_ambient_ai", exist_ok=True)
    open(OUT, "w").write(page(ambient))
    # also write whale tier page
    open("/srv/aeo/empire_ambient_ai_whale/index.html".replace("ambient_ai_whale", "ambient_ai/whale"), "w") if False else None
    os.makedirs("/srv/aeo/empire_ambient_ai_whale", exist_ok=True)
    open("/srv/aeo/empire_ambient_ai_whale/index.html", "w").write(page(whale))
    print("wrote ambient page + whale page")
