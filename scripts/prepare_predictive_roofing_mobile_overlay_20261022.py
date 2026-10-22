"""Private two-page static-site overlay for EmpireOS's mixed-generation flagship.

NEVER edits /srv/empire_os/apps/empire-public-site/out. Never publishes,
sends emails, takes payment, updates DNS or restarts services. Requires an
independent browser/mobile check and exact separate founder release approval.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
from pathlib import PurePosixPath
import shutil
from typing import Any

from scripts.verify_public_seo_pilot_candidate_20261022 import verify

LIVE=Path("/srv/empire_os/apps/empire-public-site/out")
SOURCE_RELEASE=Path("/home/ubuntu/empire_releases/seo_predictive_roofing_public_pilot_20261022/candidate-79dd421bb")
SRC=SOURCE_RELEASE/"export"
SRC_MANIFEST=SOURCE_RELEASE/"candidate-manifest.json"
OUT=Path("/home/ubuntu/empire_releases/seo_predictive_roofing_public_pilot_20261022/overlay-79dd421bb")
EXPECTED_SRC_MANIFEST="22aec3e4aaf3e85e38c6e8a614e940e76088f680a55ef99aa2a858c12019aaef"
REPLACE=(
    "predictive-revenue.html",
    "predictive-revenue.txt",
    "industries/roofing.html",
    "industries/roofing.txt",
)
LIVE_SHA={
    "predictive-revenue.html":"6465d2ec9aa3e1b71fba1847a795e37eff34b6913d7b2283f9c93b21c5f457e7",
    "predictive-revenue.txt":"993725af13f0f5ca8d586ea9154c3c1286ccbc02fddefe2c4577b9bb9886b9ce",
    "industries/roofing.html":"e46e031832f41262ae8abfcccf95b6e1132924bebd2a3d1f386ccd8105fd065b",
    "industries/roofing.txt":"749b9df2e69ce4ce017c045c93a2d5b7b9a352043c0bcc13f67b65e3f62e9bb0",
}
NEW_SHA={
    "predictive-revenue.html":"07720ee4c64dba55bb50cb2e45b1da3473e8b7c721a11f847485ee8e00858e5e",
    "predictive-revenue.txt":"7e00a86cc34ce9e03127fd95968ea5acf714244f84ebb738198d45655a5be185",
    "industries/roofing.html":"8124bd1df1829207d45d0cbddd97ea1f26fb12a289690576a8f68f820351d794",
    "industries/roofing.txt":"b3e46a536989c29bbb078289e498493f0c3b802975f0ea8549369adfbfb1a631",
}
EXPECTED_LIVE_FILES=645
EXPECTED_SOURCE_FILES=154
EXPECTED_NEW_STATIC=8
MAX_FILES=1000
MAX_BYTES=140_000_000


class ScopedOverlayHeld(ValueError):
    pass


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def inventory(root: Path) -> dict[str, tuple[str,int]]:
    if root.is_symlink() or not root.is_dir():
        raise ScopedOverlayHeld("UNSAFE_STATIC_SOURCE_ROOT")
    result={}
    total=0
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ScopedOverlayHeld("STATIC_SYMLINK_NOT_ALLOWED")
        if file.is_dir():
            continue
        if not file.is_file():
            raise ScopedOverlayHeld("NON_REGULAR_STATIC_FILE")
        rel=file.relative_to(root).as_posix()
        if rel.startswith(".") or ".." in PurePosixPath(rel).parts:
            raise ScopedOverlayHeld("STATIC_UNSAFE_PATH")
        content=file.read_bytes()
        total+=len(content)
        if len(result)>=MAX_FILES or total>MAX_BYTES:
            raise ScopedOverlayHeld("STATIC_FILE_BUDGET_EXCEEDED")
        result[rel]=(digest(content),len(content))
    return result


class LocalRefs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.local_assets=set()
        self.remote_scripts=set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str,str|None]]) -> None:
        meta=dict(attrs)
        if tag=="script" and str(meta.get("src","")).startswith(("http://","https://")):
            self.remote_scripts.add(meta["src"])
        for key in ("src","href"):
            raw=meta.get(key)
            if not isinstance(raw,str) or not raw.startswith("/") or raw.startswith("//"):
                continue
            rel=raw.split("?",1)[0].split("#",1)[0].lstrip("/")
            if rel.startswith("_next/static/"):
                self.local_assets.add(rel)


def _refs(file: Path) -> LocalRefs:
    p=LocalRefs()
    p.feed(file.read_text(encoding="utf-8"))
    return p


def plan(*, live: Path=LIVE, src: Path=SRC,
         source_manifest: Path=SRC_MANIFEST) -> dict[str,Any]:
    if source_manifest.is_symlink() or not source_manifest.is_file() or digest(source_manifest.read_bytes())!=EXPECTED_SRC_MANIFEST:
        raise ScopedOverlayHeld("PINNED_SOURCE_MANIFEST_CHANGED")
    original=json.loads(source_manifest.read_text(encoding="utf-8"))
    if (original.get("source_commit")!="79dd421bb"
            or original.get("website_publication_authorized") is not False
            or original.get("static_file_count")!=EXPECTED_SOURCE_FILES
            or original.get("execution_authority")!="NONE"):
        raise ScopedOverlayHeld("SOURCE_MOBILE_RELEASE_AUTHORITY_CHANGED")
    before=inventory(live)
    newer=inventory(src)
    if len(before)!=EXPECTED_LIVE_FILES or len(newer)!=EXPECTED_SOURCE_FILES:
        raise ScopedOverlayHeld("LIVE_OR_SOURCE_STATIC_GENERATION_DRIFT")
    if any(newer.get(k)!=(v,(src/k).stat().st_size) for k,v in original["static_file_sha256"].items()):
        raise ScopedOverlayHeld("PINNED_EXPORT_ASSET_MISMATCH")
    for name in REPLACE:
        if before.get(name,(None,))[0]!=LIVE_SHA[name] or newer.get(name,(None,))[0]!=NEW_SHA[name]:
            raise ScopedOverlayHeld("TARGET_HTML_OR_RSC_BASELINE_CHANGED")
    added={}
    for rel,val in newer.items():
        if rel.startswith("_next/static/"):
            if rel in before:
                if before[rel]!=val:
                    raise ScopedOverlayHeld("SHARED_HASHEd_NEXT_ASSET_COLLISION")
            else:
                added[rel]=val
    if len(added)!=EXPECTED_NEW_STATIC or len(before)+len(added)!=653:
        raise ScopedOverlayHeld("NEW_STATIC_BUNDLE_SCOPE_DRIFT")
    if set(added) & set(before):
        raise ScopedOverlayHeld("EXISTING_BUNDLE_PATH_OVERLAP")
    evidence=verify(src)
    if evidence["status"]!="EXPORTED_HTML_CHECKED_NOT_DEPLOYED":
        raise ScopedOverlayHeld("SOURCE_CANDIDATE_HTML_GATE_FAILED")
    all_names=set(before)|set(added)
    for name in ("predictive-revenue.html","industries/roofing.html"):
        newref=_refs(src/name)
        oldref=_refs(live/name)
        if newref.remote_scripts-oldref.remote_scripts:
            raise ScopedOverlayHeld("EXTERNAL_SCRIPT_ADDED")
        if newref.local_assets-all_names:
            raise ScopedOverlayHeld("TARGET_HTML_MISSING_NEXT_ASSET")
    return {
        "schema_version":"empire.search.seo_two_page_static_overlay_plan.v1",
        "status":"PREFLIGHT_ONLY_NO_PUBLIC_WRITE",
        "original_live_file_count":len(before),
        "source_file_count":len(newer),
        "replaced_path_sha256_before":LIVE_SHA,
        "replaced_path_sha256_after":NEW_SHA,
        "added_static_sha256":{k:v[0] for k,v in sorted(added.items())},
        "added_static_bytes":sum(v[1] for v in added.values()),
        "expected_combined_file_count":653,
        "preserved_existing_routes":len(before)-len(REPLACE),
        "existing_other_page_bytes_preserved":True,
        "user_publishing_approval":False,
        "mobile_browser_qa_approved":False,
        "mixed_generation_navigation_browser_qa_required":True,
        "production_current_rollback_snapshot_required":True,
        "public_files_modified":False,
        "execution_authority":"NONE",
    }


def prepare(*, live:Path=LIVE,src:Path=SRC,destination:Path=OUT) -> dict[str,Any]:
    pre=plan(live=live,src=src)
    if destination.exists() or destination.is_symlink():
        raise ScopedOverlayHeld("PRIVATE_RELEASE_ALREADY_EXISTS_NO_OVERWRITE")
    if (destination.resolve().is_relative_to(live.resolve())
            or live.resolve().is_relative_to(destination.resolve())):
        raise ScopedOverlayHeld("CANNOT_WRITE_INSIDE_PUBLIC_WEBSITE")
    destination.mkdir(mode=0o700, parents=True)
    candidate=destination/"out"
    shutil.copytree(live,candidate)
    for rel in REPLACE:
        target=candidate/rel
        shutil.copy2(src/rel,target)
    for rel in pre["added_static_sha256"]:
        target=candidate/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src/rel,target)
    live_after=inventory(live)
    if len(live_after)!=EXPECTED_LIVE_FILES or any(live_after[n][0]!=LIVE_SHA[n] for n in REPLACE):
        raise ScopedOverlayHeld("PUBLIC_WEBSITE_CHANGED_DURING_PRIVATE_STAGE")
    actual=inventory(candidate)
    expected=dict(live_after)
    for rel in REPLACE:
        expected[rel]=inventory(src)[rel]
    for rel in pre["added_static_sha256"]:
        expected[rel]=inventory(src)[rel]
    if actual!=expected:
        raise ScopedOverlayHeld("PRIVATE_OVERLAY_NOT_EXACT")
    receipt={
        **pre,
        "schema_version":"empire.search.seo_two_page_private_overlay_receipt.v1",
        "status":"PRIVATE_TWO_PAGE_OVERLAY_BUILT_NOT_PUBLISHED",
        "private_candidate_path":str(candidate),
        "source_manifest_sha256":EXPECTED_SRC_MANIFEST,
        "public_live_baseline_sha256":{k:v[0] for k,v in sorted(live_after.items())},
        "private_candidate_sha256":{k:v[0] for k,v in sorted(actual.items())},
        "public_files_modified":False,
        "approved_for_public_release":False,
        "mobile_browser_qa_approved":False,
        "rollback_test_performed":False,
        "execution_authority":"NONE",
    }
    target=destination/"RELEASE_CANDIDATE_RECEIPT.json"
    target.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {
        "status":receipt["status"],
        "old_file_count":len(live_after),
        "private_file_count":len(actual),
        "modified_existing_page_payloads":len(REPLACE),
        "added_new_static_assets":len(pre["added_static_sha256"]),
        "receipt_sha256":digest(target.read_bytes()),
        "candidate_path":str(candidate),
        "public_files_modified":False,
        "execution_authority":"NONE",
    }


def review_private(*,target:Path=OUT) -> dict[str,Any]:
    receipt=target/"RELEASE_CANDIDATE_RECEIPT.json"
    if receipt.is_symlink() or not receipt.is_file():
        raise ScopedOverlayHeld("PRIVATE_RECEIPT_MISSING")
    raw=json.loads(receipt.read_text(encoding="utf-8"))
    if (raw.get("schema_version")!="empire.search.seo_two_page_private_overlay_receipt.v1"
            or raw.get("status")!="PRIVATE_TWO_PAGE_OVERLAY_BUILT_NOT_PUBLISHED"
            or raw.get("approved_for_public_release") is not False
            or raw.get("public_files_modified") is not False
            or raw.get("mobile_browser_qa_approved") is not False
            or raw.get("execution_authority")!="NONE"):
        raise ScopedOverlayHeld("PRIVATE_RECEIPT_AUTHORITY_INVALID")
    files=inventory(target/"out")
    expected=raw.get("private_candidate_sha256")
    if not isinstance(expected,dict) or len(expected)!=653 or {k:v[0] for k,v in files.items()}!=expected:
        raise ScopedOverlayHeld("PRIVATE_OVERLAY_FILES_HASH_MISMATCH")
    for name in REPLACE:
        if files[name][0]!=NEW_SHA[name]:
            raise ScopedOverlayHeld("MODIFIED_PAGE_NOT_APPROVED_SOURCE")
    if len(raw["added_static_sha256"])!=EXPECTED_NEW_STATIC:
        raise ScopedOverlayHeld("UNEXPECTED_STATIC_ASSET_ADDITION")
    return {
        "status":"PRIVATE_OVERLAY_INTEGRITY_PASS_NOT_PUBLIC",
        "candidate_file_count":len(files),
        "existing_target_page_payloads_replaced":4,
        "new_only_static_assets":8,
        "mixed_generation_browser_qa_required":True,
        "current_live_fresh_baseline_required_before_release":True,
        "site_publication_authorized":False,
        "execution_authority":"NONE",
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    opts=parser.add_mutually_exclusive_group(required=True)
    opts.add_argument("--read-only",action="store_true")
    opts.add_argument("--prepare-private",action="store_true")
    opts.add_argument("--verify-private",action="store_true")
    args=parser.parse_args()
    try:
        if args.read_only:
            result=plan()
        elif args.prepare_private:
            result=prepare()
        else:
            result=review_private()
        print(json.dumps(result,sort_keys=True))
    except (ScopedOverlayHeld,OSError,ValueError) as exc:
        print(json.dumps({
            "status":"PUBLIC_SEO_OVERLAY_HELD",
            "reason":str(exc) if isinstance(exc,ScopedOverlayHeld)
                       else "SOURCE_OR_FILESYSTEM_ERROR",
            "public_files_modified":False,
            "execution_authority":"NONE",
        },sort_keys=True))
        raise SystemExit(2) from None


if __name__=="__main__":
    main()
