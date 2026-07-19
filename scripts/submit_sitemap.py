#!/usr/bin/env python3
"""Submit empire-ai.co.uk sitemap to Google Search Console via service account.
Also lists sites to confirm Owner + API-enable were done right.
Ad-hoc operational script (not a test suite)."""
import json, sys
from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDS = "/root/.gsc-creds.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters"]
SITE = "sc-domain:empire-ai.co.uk"
SITEMAP = "https://empire-ai.co.uk/sitemap.xml"

try:
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
except Exception as e:
    print("CREDS_LOAD_FAIL:", e); sys.exit(1)

svc = build("searchconsole", "v1", credentials=creds)

print("=== listing sites the service account can see (proves Owner + API work) ===")
try:
    sites = svc.sites().list().execute()
    for s in sites.get("siteEntry", []):
        print("  site:", s.get("siteUrl"), "perm:", s.get("permissionLevel"))
    if not sites.get("siteEntry"):
        print("  (no sites -> service account is NOT an owner yet, or API not enabled)")
except Exception as e:
    print("SITES_LIST_FAIL:", repr(e)[:300])
    sys.exit(1)

print("=== submitting sitemap ===")
try:
    svc.sitemaps().submit(siteUrl=SITE, feedpath=SITEMAP).execute()
    print("SUBMIT_OK:", SITEMAP)
except Exception as e:
    print("SUBMIT_FAIL:", repr(e)[:300])
    sys.exit(1)

print("=== fetching sitemap status ===")
try:
    sm = svc.sitemaps().list(siteUrl=SITE).execute()
    for s in sm.get("sitemap", []):
        print("  ", s.get("path"), "status:", s.get("errors") or "none",
              "submitted:", s.get("lastSubmitted"))
except Exception as e:
    print("STATUS_FAIL:", repr(e)[:200])
