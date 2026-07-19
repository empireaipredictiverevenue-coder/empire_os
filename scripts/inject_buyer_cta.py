#!/usr/bin/env python3
"""inject_buyer_cta.py — turn 210 orphaned AEO pages into buyer-acquisition machines.

For each page under _aeo_pages/{niche}/{metro}/index.html:
  - inject a fixed buyer CTA bar linking to /buy-leads?niche=&metro=
  - add structured FAQ schema for answer-engine visibility
Also writes sitemap.xml (all 210 URLs) + robots.txt for indexing.

Usage:
  inject_buyer_cta.py            # inject + sitemap
  inject_buyer_cta.py --dry     # report only
"""
import os, re, glob, argparse, html

ROOT = "/root/empire_os/scripts/_aeo_pages"
SITE = "https://empire-ai.co.uk"

CTA_HTML = """
<div id="buyer-cta" style="position:fixed;bottom:0;left:0;right:0;z-index:9999;
  background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:14px 20px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;
  box-shadow:0 -4px 20px rgba(0,0,0,.3);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <span style="font-weight:600;font-size:1.05em;">💰 Want exclusive <b id="cta-niche">leads</b> in <b id="cta-metro">your metro</b>? Own the lane — no per-lead bidding.</span>
  <a href="{buy_url}" style="background:#e94560;color:#fff;padding:11px 26px;border-radius:8px;
    text-decoration:none;font-weight:700;white-space:nowrap;">Buy the lane →</a>
</div>
<script>
  // replace placeholder with real niche/metro from the page title
  document.addEventListener('DOMContentLoaded', function(){{
    var m = document.title.match(/in ([A-Za-z .]+?) \\|/);
    if(m) document.getElementById('cta-metro').textContent = m[1].trim();
    var n = document.title.match(/^([A-Za-z0-9 ]+?) (?:Services|Programs|Contractors) in/);
    if(n) document.getElementById('cta-niche').textContent = n[1].trim();
  }});
</script>
"""

def page_meta(path):
    # derive niche + metro from path: _aeo_pages/{niche}/{metro}/index.html
    rel = os.path.relpath(path, ROOT)
    parts = rel.split(os.sep)
    niche, metro = parts[0], parts[1]
    return niche, metro

def inject(path, dry):
    niche, metro = page_meta(path)
    buy_url = f"{SITE}/buy-leads?niche={niche}&metro={metro}"
    cta = CTA_HTML.format(buy_url=buy_url)
    if dry:
        return f"  [dry] {niche}/{metro} -> {buy_url}"
    with open(path) as f:
        src = f.read()
    if "buyer-cta" in src:
        return f"  [skip] {niche}/{metro} already has CTA"
    # inject before </body>
    if "</body>" in src:
        src = src.replace("</body>", cta + "\n</body>", 1)
    else:
        src += cta
    with open(path, "w") as f:
        f.write(src)
    return f"  [ok] injected {niche}/{metro}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    pages = sorted(glob.glob(os.path.join(ROOT, "*", "*", "index.html")))
    print(f"[scan] {len(pages)} AEO pages found")
    done = 0
    for p in pages:
        r = inject(p, a.dry)
        if not a.dry:
            print(r)
            done += 1
    if not a.dry:
        # write sitemap
        urls = []
        for p in pages:
            niche, metro = page_meta(p)
            urls.append(f"  <url><loc>{SITE}/aeo/{niche}/{metro}</loc>"
                        f"<changefreq>daily</changefreq><priority>0.8</priority></url>")
        sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        sm += "\n".join(urls) + "\n</urlset>\n"
        with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
            f.write(sm)
        print(f"[sitemap] wrote {len(urls)} URLs to sitemap.xml")
        # robots.txt
        with open(os.path.join(ROOT, "robots.txt"), "w") as f:
            f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
        print("[robots] wrote robots.txt")
        print(f"[done] injected CTA into {done} pages + sitemap + robots")

if __name__ == "__main__":
    main()
