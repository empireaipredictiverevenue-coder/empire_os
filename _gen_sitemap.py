#!/usr/bin/env python3
"""Generate sitemap.xml + robots.txt for the AEO surface from published pages.
Run inside the container: python3 /root/empire_os/_gen_sitemap.py
"""
import os, json, urllib.request
ROOT = "/srv/aeo"
BASE = "https://empire-ai.co.uk/aeo"

# gather published niches (dirs with index.html)
niches = []
for name in sorted(os.listdir(ROOT)):
    p = os.path.join(ROOT, name, "index.html")
    if os.path.isfile(p):
        niches.append(name)

urls = "\n".join(f"  <url><loc>{BASE}/{n}/</loc></url>" for n in niches)
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

print(f"wrote sitemap.xml with {len(niches)} urls + robots.txt")
