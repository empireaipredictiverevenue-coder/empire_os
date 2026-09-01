"""
gsc_verify.py — one-time Google Search Console verification + sitemap handoff.

No API key needed. Two verification methods supported:
  1. HTML file method (default): writes google<CODE>.html to /srv/aeo and
     syncs to the hub so https://empire-ai.co.uk/google<CODE>.html resolves.
  2. Meta-tag method: injects the verification <meta> into every AEO page.

After running, paste the sitemap URL into GSC:
  https://empire-ai.co.uk/aeo/sitemap.xml

Usage:
  python3 gsc_verify.py <VERIFICATION_CODE>
  python3 gsc_verify.py <VERIFICATION_CODE> --meta   # also inject meta tags
"""
from __future__ import annotations
import sys, subprocess
from pathlib import Path

AEO_DIR = Path("/srv/aeo")
HUB_CT = "empire-hub"
SITEMAP_URL = "https://empire-ai.co.uk/aeo/sitemap.xml"


def write_verify_file(code: str) -> str:
    fn = f"google{code}.html"
    path = AEO_DIR / fn
    path.write_text(
        f"google-site-verification: google{code}.html\n"
    )
    return fn


def inject_meta(code: str) -> int:
    tag = f'<meta name="google-site-verification" content="{code}">'
    n = 0
    for idx in AEO_DIR.glob("*/index.html"):
        html = idx.read_text()
        if "google-site-verification" in html:
            continue
        html = html.replace("<head>", f"<head>\n  {tag}", 1)
        idx.write_text(html)
        n += 1
    return n


def sync_to_hub():
    # push verification file + all AEO pages into the hub container
    for f in AEO_DIR.glob("google*.html"):
        subprocess.run(["incus", "file", "push", str(f),
                        f"{HUB_CT}/srv/aeo/{f.name}"],
                       capture_output=True, timeout=30)
    for idx in AEO_DIR.glob("*/index.html"):
        subprocess.run(["incus", "file", "push", str(idx),
                        f"{HUB_CT}/srv/aeo/{idx.parent.name}/index.html"],
                       capture_output=True, timeout=30)


def main():
    if len(sys.argv) < 2:
        print("usage: gsc_verify.py <CODE> [--meta]")
        sys.exit(1)
    code = sys.argv[1]
    meta = "--meta" in sys.argv
    fn = write_verify_file(code)
    print(f"[gsc] wrote verification file: /srv/aeo/{fn}")
    print(f"[gsc] live at: https://empire-ai.co.uk/{fn}")
    n = 0
    if meta:
        n = inject_meta(code)
        print(f"[gsc] injected meta tag into {n} AEO pages")
    sync_to_hub()
    print(f"[gsc] synced to hub.")
    print(f"\nNEXT STEPS in Google Search Console:")
    print(f"  1. Add property: https://empire-ai.co.uk")
    print(f"  2. Choose 'HTML file' verification -> upload is already live at the URL above")
    print(f"  3. After verified, submit sitemap: {SITEMAP_URL}")
    print(f"  4. Request indexing on: https://empire-ai.co.uk/aeo/hvac/")


if __name__ == "__main__":
    main()
