#!/usr/bin/env python3
"""
Empire OS — Product Data Enrichment Pipeline.
Step 1: fetch raw HTML of each live product page
Step 2: extract fields (name, tagline, description, tech, specs, tiers)
Step 3: parse into a structured doc (json)
Step 4: extract that doc data + ENRICH (CRM lead counts, scraper prospects, citation rate)
Output: /root/feedback/product_docs/{sku}.enriched.json  +  updated .md
"""
import sys, os, re, json, urllib.request, subprocess
sys.path.insert(0, "/root/empire_os")

PRODUCTS = ["vertical_feed","aeo_monitor","aeo_refresh","business_dir",
            "verify_business","settlement_gateway","synthetic_service","agent_copilot"]
BASE = "https://empire-ai.co.uk/aeo/products"

def fetch_raw(sku):
    try:
        return urllib.request.urlopen(f"{BASE}/{sku}/", timeout=10).read().decode("utf-8","ignore")
    except Exception as e:
        return ""

def extract(html):
    """Step 2: pull fields from raw HTML."""
    title = re.search(r"<h1>(.*?)</h1>", html)
    tag = re.search(r'color:var\(--accent\)">([^<]+)<', html)
    desc = re.search(r"<h2>What it does</h2><p>(.*?)</p>", html, re.S)
    tech = re.search(r"<h2>Technology</h2><p>(.*?)</p>", html, re.S)
    # tiers from tags
    tiers = re.findall(r"(\w+):\s*\$(\d+)/mo", html)
    specs = re.findall(r"<dt>(.*?)</dt><dd>(.*?)</dd>", html, re.S)
    return {
        "name": title.group(1).strip() if title else "",
        "tagline": tag.group(1).strip() if tag else "",
        "description": re.sub(r"<[^>]+>","",desc.group(1)).strip() if desc else "",
        "tech": re.sub(r"<[^>]+>","",tech.group(1)).strip() if tech else "",
        "tiers": {k:int(v) for k,v in tiers},
        "specs": {re.sub(r"<[^>]+>","",k).strip():re.sub(r"<[^>]+>","",v).strip() for k,v in specs},
    }

def enrich(sku, base):
    """Step 4: add live signal to the extracted doc."""
    e = dict(base)
    e["sku"] = sku
    # CRM real lead count for the vertical (if product maps to a vertical)
    try:
        import vertical_feed as vf
        if sku == "vertical_feed":
            rows = vf.feed("logistics", 100)
            e["live_signal"] = {"crm_leads_sample": rows.get("count",0),
                                "source": "container CRM 29k+"}
    except Exception:
        pass
    # scraper prospects count for the niche
    try:
        n = 0
        if os.path.exists("/root/feedback/prospects.jsonl"):
            for line in open("/root/feedback/prospects.jsonl"):
                n += 1
        e["prospects_available"] = n
    except Exception:
        pass
    # aeo citation if monitor product
    if sku == "aeo_monitor":
        try:
            import aeo_monitor as am
            r = am.run_check("logistics")
            e["citation_rate"] = r.get("citation_rate", 0.0) if isinstance(r,dict) else 0.0
        except Exception:
            e["citation_rate"] = 0.0
    e["enriched"] = True
    return e

def main():
    os.makedirs("/root/feedback/product_docs", exist_ok=True)
    out = {}
    for sku in PRODUCTS:
        raw = fetch_raw(sku)
        if not raw:
            print(f"  SKIP {sku}: page not reachable")
            continue
        base = extract(raw)            # step 2-3: parsed doc
        enriched = enrich(sku, base)   # step 4: enrich
        # write enriched json
        jp = f"/root/feedback/product_docs/{sku}.enriched.json"
        json.dump(enriched, open(jp,"w"), indent=2)
        # update markdown with enriched section
        md = open(f"/root/feedback/product_docs/{sku}.md").read()
        md += f"\n## Live Enrichment\n- Prospects available: {enriched.get('prospects_available',0)}\n"
        if "live_signal" in enriched:
            md += f"- CRM signal: {enriched['live_signal']}\n"
        if "citation_rate" in enriched:
            md += f"- Citation rate: {enriched['citation_rate']}\n"
        open(f"/root/feedback/product_docs/{sku}.md","w").write(md)
        out[sku] = enriched
        print(f"  OK {sku}: extracted + enriched ({len(base)} fields, prospects={enriched.get('prospects_available',0)})")
    print(f"enriched {len(out)}/{len(PRODUCTS)} products")
    return out

if __name__ == "__main__":
    main()
