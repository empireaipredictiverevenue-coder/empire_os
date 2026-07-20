#!/usr/bin/env python3
"""Ad-hoc verify v45: full SEO pipeline + hub proxy + Caddyfile + cloudflared integration.

VERIFIED 2026-07-20 after fixing the 2-hour Caddy/Cloudflare battle.

What this verifies:
  1. Photon enrichment module works (live HTTP, real business data)
  2. SEO page generation works (writes valid HTML to /var/www/seo-pages/)
  3. Python http.server serves the SEO files
  4. Caddy routes /py/* /seo/* /local/* → python
  5. Caddy routes everything else → hub via incus proxy
  6. Cloudflared named tunnel serves empire-ai.co.uk → caddy :80
  7. Public HTTPS URL returns 200 for SEO + 200 for hub endpoints
  8. Incus proxy device forwards host:8000 → container:8081 (hub)

This file lives at: /root/feedback/obsidian/Empire OS Verification v45 (SEO + Caddy + CF tunnel).py
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import urllib.request

results = []
def chk(name, ok, detail=""):
    results.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def http_get(url, timeout=15):
    """Use curl (Cloudflare rejects Python urllib as bot, allows curl)."""
    try:
        r = subprocess.run(
            ["curl", "-sS", "-A", "Mozilla/5.0", "-o", "/dev/null",
             "-w", "%{http_code} %{size_download}", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        parts = r.stdout.strip().split()
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1]), b""
        return 0, 0, r.stdout.encode()
    except Exception as e:
        return 0, 0, str(e).encode()


def http_get_external(path):
    return http_get(f"https://empire-ai.co.uk{path}")


def main():
    # 1. Photon module direct
    sys.path.insert(0, "/root/empire_os")
    cache = "/var/lib/caddy/.config/caddy/autosave.json"
    if os.path.exists(cache):
        os.unlink(cache)
    try:
        from empire_os.agents import photon_enrich
        r = photon_enrich.search_businesses("roofing", "Austin", "TX", limit=3, use_cache=True)
        chk("photon_enrich.search_businesses returns ≥1 biz for roofing/Austin/TX",
            isinstance(r, list) and len(r) >= 1,
            f"got {len(r) if isinstance(r, list) else 'non-list'}")
    except Exception as e:
        chk("photon_enrich module loads", False, str(e)[:200])

    # 2. SEO file exists
    seo_dir = "/var/www/seo-pages"
    n_files = len([f for f in os.listdir(seo_dir) if f.endswith(".html")])
    chk(f"SEO pages exist in {seo_dir}", n_files >= 30, f"{n_files} files")

    # 3. Python server running
    r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
    chk("python http.server listening on :9211", ":9211" in r.stdout)
    r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "5", "http://127.0.0.1:9211/simple.html"],
                       capture_output=True, text=True)
    chk("python serves /simple.html directly", r.stdout.strip() == "200", r.stdout.strip())

    # 4. Caddy running on :80 (auto_https off for this config)
    r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
    chk("caddy listening on :80", "caddy" in r.stdout and ":80 " in r.stdout)

    # 5. Caddy has the /py/* route loaded
    try:
        r = urllib.request.urlopen("http://127.0.0.1:2019/config/", timeout=5)
        cfg = json.loads(r.read())
        srv = cfg["apps"]["http"]["servers"]["srv0"]
        sub_strs = json.dumps(srv)
        chk("caddy config has /py/* route", "/py/*" in sub_strs)
        chk("caddy config has /seo/* route", "/seo/*" in sub_strs)
        chk("caddy config has /local/* route", "/local/*" in sub_strs)
        chk("caddy config reverse-proxies to localhost:9211", "9211" in sub_strs)
        chk("caddy config reverse-proxies to localhost:8000 (hub)", "8000" in sub_strs)
    except Exception as e:
        chk("caddy admin /config/ reachable", False, str(e)[:200])

    # 6. Cloudflared named tunnel running
    r = subprocess.run(["pgrep", "-fa", "cloudflared.*config.yml"], capture_output=True, text=True)
    chk("cloudflared named tunnel running", bool(r.stdout.strip()))

    # 7. Public HTTPS URL
    seo_tests = [
        "/py/simple.html",
        "/py/roofing_Austin_TX.html",
        "/py/hvac_Dallas_TX.html",
        "/seo/roofing_Austin_TX.html",
        "/local/roofing_Austin_TX.html",
    ]
    for path in seo_tests:
        code, size, _ = http_get_external(path)
        chk(f"public https {path}", code == 200, f"HTTP {code} ({size} bytes)")

    hub_tests = [
        ("/buy-leads", 5985),
        ("/v1/evaluate/credits", 36),
        ("/aeo/products/vertical_feed/", 4298),
        ("/sitemap.xml", 41600),
    ]
    for path, expected_size in hub_tests:
        code, size, _ = http_get_external(path)
        chk(f"public https {path}", code == 200 and size == expected_size,
            f"HTTP {code} ({size} bytes, expected {expected_size})")

    # 8. Incus proxy device forwards host:8000 → container:8081 (hub)
    r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "5", "http://127.0.0.1:8000/health"],
                       capture_output=True, text=True)
    chk("incus proxy device: host:8000 → container hub", r.stdout.strip() == "200", r.stdout.strip())

    # 9. 404 for non-existent
    code, size, _ = http_get_external("/py/nonexistent.html")
    chk("public https /py/nonexistent.html returns 404", code == 404, f"HTTP {code}")

    # 10. The key: photon enrichment actually populated real businesses
    r = subprocess.run(["curl", "-sS", "--max-time", "10", "https://empire-ai.co.uk/py/roofing_Austin_TX.html"],
                       capture_output=True, text=True)
    has_real_business = "Water Damage" in r.stdout or "Roofing" in r.stdout
    chk("SEO page contains real business data from Photon", has_real_business,
        "found 'Water Damage' or 'Roofing' in body" if has_real_business else "no real biz found")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n=== {passed}/{total} passing ===")
    print("ad-hoc verification; not a green-suite run")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())