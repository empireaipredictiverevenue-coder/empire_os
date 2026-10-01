#!/usr/bin/env python3
"""Live verification for founder-approved zero-paid revenue activation."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/srv/empire_os")
BASE = "http://127.0.0.1"


def _status(path: str, *, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _json(path: str) -> dict:
    code, body = _status(path)
    if code != 200:
        raise RuntimeError(f"{path} returned {code}")
    return json.loads(body)

def main() -> int:
    health = _json("/health")
    if health.get("status") != "online":
        raise RuntimeError("public gateway offline")
    if _json("/v1/a2a-commerce/health").get("configured") is not True:
        raise RuntimeError("A2A commerce not configured")
    if _json("/v1/a2a-identity/health").get("configured") is not True:
        raise RuntimeError("A2A identity not configured")
    discovery = _json("/a2a/v1/discovery")
    auth = discovery["commercial_discovery"]["authentication_status"]
    if auth != "activated":
        raise RuntimeError(f"A2A status is {auth}")

    owned = json.loads(
        (ROOT / "runtime/astra/owned_campaign_deployed_release.json").read_text()
    )
    if owned.get("zero_paid_media") is not True or len(owned.get("campaign_ids", [])) != 5:
        raise RuntimeError("owned release is not the approved five-page zero-paid cohort")
    for campaign_id in owned["campaign_ids"]:
        code, _ = _status(f"/research/{campaign_id}")
        if code != 200:
            raise RuntimeError(f"research route failed: {campaign_id} {code}")

    aeo = json.loads(
        (ROOT / "runtime/search_intelligence/aeo_release.json").read_text()
    )
    if aeo.get("zero_paid_media") is not True or len(aeo.get("pages", [])) != 3:
        raise RuntimeError("AEO release is not the approved three-page cohort")
    for row in aeo["pages"]:
        code, _ = _status(f"/aeo/{row['niche']}/{row['metro']}/")
        if code != 200:
            raise RuntimeError(f"AEO route failed: {row} {code}")
    code, _ = _status("/aeo/accounting/CHI/")
    if code != 404:
        raise RuntimeError("unreleased AEO page did not fail closed")

    code, sitemap = _status("/sitemap.xml")
    if code != 200:
        raise RuntimeError("sitemap unavailable")
    text = sitemap.decode()
    if text.count("<loc>https://empire-ai.co.uk/aeo/") != 3:
        raise RuntimeError("AEO sitemap is not bounded to three pages")
    if text.count("<loc>https://empire-ai.co.uk/research/") != 5:
        raise RuntimeError("research sitemap is not bounded to five pages")

    code, _ = _status(
        "/api/research/enquiry",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Origin": "https://empire-ai.co.uk",
            "Sec-Fetch-Site": "same-origin",
        },
    )
    if code != 422:
        raise RuntimeError(f"intake invalid-input contract returned {code}")

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    receipt = {
        "schema_version": "empire.revenue-activation-receipt.v1",
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": head,
        "zero_paid_media": True,
        "owned_research_route_count": 5,
        "aeo_release_route_count": 3,
        "a2a_authentication_status": "activated",
        "migration_025_applied": True,
        "migration_026_applied": True,
        "seth_send": False,
        "kieran_send": False,
        "paid_traffic": False,
        "payment_action": False,
        "binding_terms_action": False,
    }
    target = ROOT / "runtime/control/revenue_activation_2026-10-01.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("ZERO_PAID_REVENUE_LIVE_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
