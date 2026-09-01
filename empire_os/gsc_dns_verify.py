"""
gsc_dns_verify.py — verify Google Search Console via Cloudflare DNS TXT (no UI clicks).

GSC now defaults to DNS verification. This script adds the required TXT record
to empire-ai.co.uk using your Cloudflare dns-edit token (no manual dashboard
work, no API key for GSC itself).

Usage:
  python3 gsc_dns_verify.py <GSC_VERIFICATION_TXT>

where <GSC_VERIFICATION_TXT> is the full value GSC shows, e.g.
  google-site-verification=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

After running, go back to GSC and click "Verify" — it reads the TXT record
automatically. Then submit: https://empire-ai.co.uk/aeo/sitemap.xml
"""
from __future__ import annotations
import os, sys, json, urllib.request, urllib.error

TOKEN = open("/root/empire_secrets/cloudflare_dns_token").read().strip()
ZONE = "159cf82e43bf37d12012c878b7df3745"
API = f"https://api.cloudflare.com/client/v4/zones/{ZONE}/dns_records"


def _req(method: str, body: dict | None = None):
    headers = {"Authorization": f"Bearer {TOKEN}",
               "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(API, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def add_txt(value: str) -> dict:
    # GSC TXT record: name = @ (root), content = the full google-site-verification=...
    return _req("POST", {
        "type": "TXT",
        "name": "empire-ai.co.uk",
        "content": value,
        "ttl": 60,
    })


def main():
    if len(sys.argv) < 2:
        print("usage: gsc_dns_verify.py <GSC_VERIFICATION_TXT>")
        print("  e.g. gsc_dns_verify.py 'google-site-verification=abc123...'")
        sys.exit(1)
    value = sys.argv[1].strip()
    if not value.startswith("google-site-verification="):
        print("ERROR: value must look like 'google-site-verification=XXXX'")
        sys.exit(1)
    try:
        res = add_txt(value)
    except urllib.error.HTTPError as e:
        print(f"Cloudflare API error {e.code}: {e.read().decode()[:300]}")
        sys.exit(1)
    if res.get("success"):
        print("[gsc] TXT record added to empire-ai.co.uk")
        print(f"[gsc] content: {value}")
        print("[gsc] Go to GSC -> click 'Verify'. Then submit sitemap:")
        print("      https://empire-ai.co.uk/aeo/sitemap.xml")
    else:
        print("[gsc] FAILED:", res.get("errors", res))


if __name__ == "__main__":
    main()
