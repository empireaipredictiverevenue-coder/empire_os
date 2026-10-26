#!/usr/bin/env python3
"""Two-page, GET-only original website owner preflight. NO deployment path."""
from pathlib import Path
from hashlib import sha256
import json
import requests

ORIGINAL=Path("/srv/empire_os/apps/empire-public-site/out")
REBUILT=Path("/home/ubuntu/empire_worktrees/website_solar_commercial_premium_20261026/apps/empire-public-site/out")
PACKET=Path("/home/ubuntu/empire_releases/website_solar_commercial_premium_20261026_candidate")
TARGETS={"commercial.html":"/commercial","industries/solar.html":"/industries/solar"}

def sha(p):return sha256(p.read_bytes()).hexdigest()
def files(root):
    return {str(p.relative_to(root)):sha(p) for p in root.rglob("*")
            if p.is_file() and not p.is_symlink()}
def review():
    old,new=files(ORIGINAL),files(REBUILT)
    manifest=json.loads((PACKET/"release_candidate.json").read_text())
    if not PACKET.is_dir() or PACKET.is_symlink() or set(TARGETS)-set(old) or set(TARGETS)-set(new):
        raise ValueError("EXACT_TARGET_SOURCE_MISSING")
    added=sorted(set(new)-set(old))
    old_asset_drift=[k for k in (set(old)&set(new))
                     if not k.endswith(".html") and old[k]!=new[k]]
    if old_asset_drift or any(k.endswith(".html") for k in added):
        raise ValueError("SHARED_ASSET_COLLISION_OR_NEW_HTML_FOUND")
    if (manifest.get("schema_version")!="empire.website.solar_commercial_premium_candidate.v1"
        or manifest.get("targets")!={rel:{
            "route":route,"live_before_sha256":old[rel],"proposed_sha256":new[rel]}
            for rel,route in TARGETS.items()}
        or manifest.get("added_assets_sha256")!={rel:new[rel] for rel in added}
        or manifest.get("publication_authorized_now") is not False):
        raise ValueError("MANIFEST_NOT_EXACT_CANDIDATE")
    for rel,route in TARGETS.items():
        if sha(PACKET/"before"/rel)!=old[rel] or sha(PACKET/"proposed_site"/rel)!=new[rel]:
            raise ValueError("ORIGINAL_OR_PROPOSED_HTML_HASH_MISMATCH")
        r=requests.get("https://empire-ai.co.uk"+route,timeout=15)
        if r.status_code!=200 or sha256(r.content).hexdigest()!=old[rel]:
            raise ValueError("LIVE_PUBLIC_HTML_CHANGED")
    for rel in added:
        if sha(PACKET/"proposed_site"/rel)!=new[rel]:
            raise ValueError("IMMUTABLE_ADDITIVE_ASSET_CHANGED")
    return {"status":"SOLAR_COMMERCIAL_TWO_PAGE_CANDIDATE_VERIFIED",
            "pages_proposed":len(TARGETS),"new_immutable_assets":len(added),
            "other_live_html_changes":0,"existing_shared_asset_overwrites":0,
            "public_site_changed":False,"payments_activated":False,
            "database_writes":False,"outbound_sent":False}
if __name__=="__main__":
    print(json.dumps(review(),sort_keys=True))
