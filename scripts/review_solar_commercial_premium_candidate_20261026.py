#!/usr/bin/env python3
"""Read-only, exact two-page + scoped Next data sidecar release preflight."""
from pathlib import Path
from hashlib import sha256
import json
import subprocess
import requests

ORIGINAL=Path("/srv/empire_os/apps/empire-public-site/out")
REBUILT=Path("/home/ubuntu/empire_worktrees/website_solar_commercial_premium_20261026/apps/empire-public-site/out")
PACKET=Path("/home/ubuntu/empire_releases/website_solar_commercial_premium_20261026_candidate_v2")
WORKTREE=Path("/home/ubuntu/empire_worktrees/website_solar_commercial_premium_20261026")
SOURCE_PATHS=(
 "apps/empire-public-site/src/app/industries/[slug]/page.tsx",
 "apps/empire-public-site/src/app/commercial/page.tsx",
 "apps/empire-public-site/src/components/SolarIntelligenceExperience.tsx",
)
SCREENSHOTS=("solar-desktop.png","solar-mobile.png",
             "commercial-desktop.png","commercial-mobile.png")
TARGETS={"commercial.html":"/commercial","industries/solar.html":"/industries/solar"}
ROUTE_DATA=(
 "commercial.txt",
 "commercial/__next._full.txt",
 "commercial/__next._tree.txt",
 "commercial/__next.commercial.__PAGE__.txt",
 "industries/solar.txt",
 "industries/solar/__next._full.txt",
 "industries/solar/__next._tree.txt",
 "industries/solar/__next.industries.$d$slug.__PAGE__.txt",
)

def sha(p):return sha256(p.read_bytes()).hexdigest()
def files(root):
    return {str(p.relative_to(root)):sha(p) for p in root.rglob("*")
            if p.is_file() and not p.is_symlink()}

def review():
    old,new=files(ORIGINAL),files(REBUILT)
    manifest=json.loads((PACKET/"release_candidate.json").read_text())
    reviewed=set(TARGETS)|set(ROUTE_DATA)
    if not PACKET.is_dir() or PACKET.is_symlink() or reviewed-set(old) or reviewed-set(new):
        raise ValueError("EXACT_TARGET_PAGE_OR_NEXT_ROUTE_DATA_MISSING")
    added=sorted(set(new)-set(old))
    shared_asset_drift=[k for k in (set(old)&set(new))
                        if not k.endswith((".html",".txt")) and old[k]!=new[k]]
    if shared_asset_drift or any(not k.startswith("_next/static/") for k in added):
        raise ValueError("SHARED_ASSET_COLLISION_OR_UNSCOPED_ADDITION")
    if not all(old[k]!=new[k] for k in reviewed):
        raise ValueError("EXACT_TWO_ROUTE_DATA_AND_HTML_UPDATE_REQUIRED")
    if (manifest.get("schema_version")!="empire.website.solar_commercial_premium_candidate.v2"
        or manifest.get("targets")!={rel:{
            "route":route,"live_before_sha256":old[rel],"proposed_sha256":new[rel]}
            for rel,route in TARGETS.items()}
        or manifest.get("route_data_sidecars")!={rel:{
            "before_sha256":old[rel],"proposed_sha256":new[rel]}
            for rel in ROUTE_DATA}
        or manifest.get("added_assets_sha256")!={rel:new[rel] for rel in added}
        or manifest.get("publication_authorized_now") is not False
        or manifest.get("unrelated_html_and_route_data_excluded") is not True):
        raise ValueError("MANIFEST_NOT_EXACT_TWO_PAGE_SCOPE")
    revision=subprocess.check_output(["git","-C",str(WORKTREE),"rev-parse","--short","HEAD"],text=True).strip()
    if manifest.get("source_commit")!=revision:
        raise ValueError("UNPINNED_OR_CHANGED_SOURCE_REVISION")
    if manifest.get("source_sha256")!={rel:sha(WORKTREE/rel) for rel in SOURCE_PATHS}:
        raise ValueError("OWNER_REVIEWED_APPLICATION_SOURCE_DRIFT")
    visual=PACKET/"browser_qa"/"qa_receipt.json"
    if not visual.is_file() or visual.is_symlink() or sha(visual)!=manifest.get("browser_qa_receipt_sha256"):
        raise ValueError("ISOLATED_CHROME_QA_RECEIPT_UNTRUSTED")
    try:
        qa=json.loads(visual.read_text())
    except Exception as exc:
        raise ValueError("INVALID_PRIVATE_CHROME_QA") from exc
    if (qa.get("status")!="ORIGINAL_TWO_PAGE_PRIVATE_DESKTOP_MOBILE_BROWSER_PASS"
        or qa.get("real_customer_post_count")!=0
        or qa.get("public_website_modified") is not False
        or len(qa.get("screens",[]))!=4):
        raise ValueError("OWNER_CHROME_ACCEPTANCE_NOT_VERIFIED")
    if manifest.get("browser_review_screenshots_sha256")!={name:sha(PACKET/"browser_qa"/name) for name in SCREENSHOTS}:
        raise ValueError("EXACT_VISUAL_REVIEW_SCREENSHOTS_CHANGED")
    for rel,route in TARGETS.items():
        r=requests.get("https://empire-ai.co.uk"+route,timeout=15)
        if r.status_code!=200 or sha256(r.content).hexdigest()!=old[rel]:
            raise ValueError("LIVE_PUBLIC_HTML_CHANGED")
    for rel in reviewed:
        if sha(PACKET/"before"/rel)!=old[rel] or sha(PACKET/"proposed_site"/rel)!=new[rel]:
            raise ValueError("HTML_OR_ROUTE_DATA_ORIGINAL_CANDIDATE_HASH_MISMATCH")
    for rel in added:
        if sha(PACKET/"proposed_site"/rel)!=new[rel]:
            raise ValueError("NEW_ADDITIVE_ASSET_CHANGED")
    return {"status":"SOLAR_COMMERCIAL_TWO_PAGE_AND_ROUTE_DATA_CANDIDATE_VERIFIED",
            "pages_proposed":len(TARGETS),
            "scoped_next_route_data_files":len(ROUTE_DATA),
            "new_immutable_assets":len(added),
            "other_live_html_and_route_data_overwrites":0,
            "existing_shared_asset_overwrites":0,
            "public_site_changed":False,
            "other_website_owner_signoff_required":True,
            "payments_activated":False,"database_writes":False,"outbound_sent":False}

if __name__=="__main__":
    print(json.dumps(review(),sort_keys=True))
