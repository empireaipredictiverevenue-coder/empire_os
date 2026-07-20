#!/usr/bin/env python3
"""Generate sitemap.xml + robots.txt for the AEO surface from published pages.
Run inside the container: python3 /root/empire_os/_gen_sitemap.py
"""
import os, json, urllib.request
ROOT = "/srv/aeo"
BASE = "https://empire-ai.co.uk/aeo"

# gather every published page (niche/ AND niche/metro/) — dirs with index.html.
# The old version only walked the top level, so metro subpages were never in the
# sitemap and never got crawled. Recurse one level deep to include /{niche}/{metro}/.
paths = []
for niche in sorted(os.listdir(ROOT)):
    ndir = os.path.join(ROOT, niche)
    if not os.path.isdir(ndir):
        continue
    if os.path.isfile(os.path.join(ndir, "index.html")):
        paths.append(f"{niche}/")
    for metro in sorted(os.listdir(ndir)):
        if os.path.isfile(os.path.join(ndir, metro, "index.html")):
            paths.append(f"{niche}/{metro}/")

urls = "\n".join(f"  <url><loc>{BASE}/{p}</loc></url>" for p in paths)
sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
"""
with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
    f.write(sitemap)

robots = f"""User-agent: *
Allow: /aeo/
Allow: /buy-leads
Sitemap: {BASE}/sitemap.xml
"""
with open(os.path.join(ROOT, "robots.txt"), "w") as f:
    f.write(robots)

print(f"wrote sitemap.xml with {len(paths)} urls + robots.txt")
