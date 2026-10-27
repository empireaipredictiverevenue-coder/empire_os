"""Exact-scope Solar + Commercial V2 publication for ORIGINAL ASTRA website owner.

Default action: read-only preflight. Live action requires root, a separately
attested original-owner approval receipt, an independently verified protected
700-file founder backup, matching source/release payload hashes, protected
serialization, and existing atomic scoped publication with rollback. This file
does not create or grant approval and must not be treated as the owner itself.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Any
from urllib.request import Request, urlopen

# Reuse the existing, individually reversible, exact-scoped owner transaction.
from scripts.release_predictive_roofing_two_page_20261022 import (
    apply_four_pages_and_eight_assets,
)

ROOT = Path("/srv/empire_os")
LIVE = ROOT / "apps/empire-public-site/out"
PACKET = Path("/home/ubuntu/empire_releases/website_solar_commercial_premium_20261026_candidate_v2")
MANIFEST = PACKET / "release_candidate.json"
SOURCE_INVENTORY = PACKET / "root_backup_source_inventory_20261027.json"
BACKUP_DIR = Path("/var/backups/empire-website")
BACKUP = BACKUP_DIR / "solar-commercial-v2-before-20261027.tar.gz"
OWNER_APPROVAL = BACKUP_DIR / "solar-commercial-v2-astra-owner-approval.json"
ROOT_RECEIPT = BACKUP_DIR / "solar-commercial-v2-published.json"
LOCK = BACKUP_DIR / ".solar-commercial-v2-exact-owner-release.lock"
# Exact SHA-256 from separately executed founder-backed root verification.
EXPECTED_BACKUP_SHA = "4e7bb1ea2c8fbb81d99ff59e8debdff3b28f20826e1738278af452494f9b3bff"
EXPECTED_MANIFEST_SHA = "14b65c040e398d74ac637f0845d2fd62046e7e0db9bb2eefdc348dabf1919f39"
EXPECTED_INVENTORY_SHA = "60fe7228a5583ce37c4754c2390d35a5c8f6609b527ecb1e4ad03986546ab8e5"
SOURCE_COMMIT = "d7229c635"
FOUNDER_RECEIPT = ROOT / "docs/website/release_candidates/SOLAR_COMMERCIAL_V2_FOUNDER_FINAL_VISUAL_APPROVAL_20261027.json"
EXPECTED_FOUNDER_RECEIPT_SHA = "21ef90007ab15a08a91a0b48109fb0640032010249d7ed900971d026d6b23ee1"
PUBLISH_FLAG = "--apply-exact-owner-approved-solar-commercial-v2"
ROUTES = ("/commercial", "/industries/solar")
NEIGHBOURS = ("/", "/buy", "/industries", "/industries/hvac", "/predictive-revenue", "/trust")


class OwnerReleaseHold(ValueError):
    pass


# Founder explicitly REJECTED the old visual brand after seeing full-page QA.
# The supersession is historical and immutable; do not use a previous V2 visual
# receipt to infer new brand approval. Old live/publication modes fail closed.
BRAND_SUPERSESSION = ROOT / "docs/website/release_candidates/SOLAR_COMMERCIAL_V2_BRAND_SUPERSESSION_HOLD_20261027.json"
EXPECTED_BRAND_SUPERSESSION_SHA = "b09c23e6c204b061dccc8362f44747dc407f9bc1bfacb8a260d689ce8010e3d9"


def _require_original_v2_brand_still_approved() -> None:
    if not BRAND_SUPERSESSION.is_file() or BRAND_SUPERSESSION.is_symlink():
        raise OwnerReleaseHold("FOUNDER_BRAND_SUPERSESSION_RECORD_MISSING_RELEASE_HELD")
    if sha(BRAND_SUPERSESSION) != EXPECTED_BRAND_SUPERSESSION_SHA:
        raise OwnerReleaseHold("FOUNDER_BRAND_SUPERSESSION_RECORD_CHANGED_RELEASE_HELD")
    record = read_json(BRAND_SUPERSESSION)
    if (record.get("previous_candidate_manifest_sha256") != EXPECTED_MANIFEST_SHA
        or record.get("previous_candidate_publisher_must_fail_closed") is not True):
        raise OwnerReleaseHold("INVALID_FOUNDER_BRAND_SUPERSESSION_HOLD")
    raise OwnerReleaseHold("FOUNDER_REJECTED_PREVIOUS_V2_BRANDING_RELEASE_SUPERSEDED")


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 120000:
        raise OwnerReleaseHold("UNTRUSTED_MANIFEST_OR_APPROVAL")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise OwnerReleaseHold("MANIFEST_NOT_AN_OBJECT")
    return result


def site_inventory(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise OwnerReleaseHold("LIVE_TREE_NOT_SAFE")
    index: dict[str, str] = {}
    for p in root.rglob("*"):
        if p.is_symlink():
            raise OwnerReleaseHold("SYMLINK_PRESENT_IN_LIVE_SITE")
        if p.is_file():
            name = p.relative_to(root).as_posix()
            index[name] = sha(p)
            if len(index) > 2000:
                raise OwnerReleaseHold("EXCESSIVE_LIVE_SITE_FILES")
    return index


def candidate(*, live: Path = LIVE, packet: Path = PACKET) -> dict[str, Any]:
    # This is an exact production generation; no opportunistic rebuilds.
    if packet != PACKET:
        raise OwnerReleaseHold("UNEXPECTED_OWNER_PACKET")
    if sha(MANIFEST) != EXPECTED_MANIFEST_SHA or sha(SOURCE_INVENTORY) != EXPECTED_INVENTORY_SHA:
        raise OwnerReleaseHold("PINNED_SOURCE_MANIFEST_CHANGED")
    m = read_json(MANIFEST)
    source = read_json(SOURCE_INVENTORY)
    if (m.get("schema_version") != "empire.website.solar_commercial_premium_candidate.v2"
        or m.get("source_commit") != SOURCE_COMMIT
        or m.get("publication_authorized_now") is not False
        or source.get("candidate_manifest_sha256") != EXPECTED_MANIFEST_SHA
        or source.get("expected_count") != 700):
        raise OwnerReleaseHold("CANDIDATE_IDENTITY_OR_AUTHORITY_MISMATCH")
    if sha(FOUNDER_RECEIPT) != EXPECTED_FOUNDER_RECEIPT_SHA:
        raise OwnerReleaseHold("EXACT_FOUNDER_VISUAL_APPROVAL_RECEIPT_CHANGED")
    founder = read_json(FOUNDER_RECEIPT)
    if (founder.get("schema_version") != "empire.website.solar_commercial_v2_founder_final_visual_approval.v1"
        or founder.get("source_commit") != SOURCE_COMMIT
        or founder.get("candidate_manifest_sha256") != EXPECTED_MANIFEST_SHA
        or founder.get("browser_qa_receipt_sha256") != m.get("browser_qa_receipt_sha256")
        or founder.get("screenshot_sha256") != m.get("browser_review_screenshots_sha256")
        or founder.get("founder_approval_for_exact_visual_copy_pricing") is not True
        or founder.get("original_website_owner_independent_approval_verified") is not False
        or founder.get("publication_authorized_now") is not False):
        raise OwnerReleaseHold("FOUNDER_APPROVAL_BOUND_TO_DIFFERENT_RELEASE")
    baseline = site_inventory(live)
    if len(baseline) != 700 or baseline != source.get("baseline_sha256"):
        raise OwnerReleaseHold("COMPLETE_700_FILE_BASELINE_CHANGED")

    targets = m.get("targets") or {}
    sidecars = m.get("route_data_sidecars") or {}
    additions = m.get("added_assets_sha256") or {}
    if (set(targets) != {"commercial.html", "industries/solar.html"}
        or len(sidecars) != 8 or len(additions) != 10):
        raise OwnerReleaseHold("V2_SCOPE_NOT_2_HTML_8_ROUTE_DATA_10_ASSETS")
    replace = {}
    for rel, row in {**targets, **sidecars}.items():
        if rel not in baseline or not isinstance(row, dict):
            raise OwnerReleaseHold("REPLACEMENT_NOT_ORIGINAL_ROUTE")
        old_sha = row.get("live_before_sha256", row.get("before_sha256"))
        new_sha = row.get("proposed_sha256")
        if (baseline[rel] != old_sha
            or sha(packet / "before" / rel) != old_sha
            or sha(packet / "proposed_site" / rel) != new_sha):
            raise OwnerReleaseHold("EXACT_V2_REPLACEMENT_BYTES_CHANGED:" + rel)
        replace[rel] = new_sha
    if len(replace) != 10:
        raise OwnerReleaseHold("REPLACEMENT_COUNT_INCONSISTENT")

    for rel, expected in additions.items():
        if (not rel.startswith("_next/static/")
            or rel in baseline
            or sha(packet / "proposed_site" / rel) != expected):
            raise OwnerReleaseHold("HASHED_ASSET_COLLISION_OR_DRIFT:" + rel)
    # Browser evidence cannot be swapped after the owner originally reviewed it.
    qa = packet / "browser_qa/qa_receipt.json"
    if sha(qa) != m.get("browser_qa_receipt_sha256"):
        raise OwnerReleaseHold("PINNED_VISUAL_ACCEPTANCE_DRIFT")
    for name, expected in m.get("browser_review_screenshots_sha256", {}).items():
        if sha(packet / "browser_qa" / name) != expected:
            raise OwnerReleaseHold("REVIEW_SCREENSHOT_CHANGED:" + name)
    if len(m.get("browser_review_screenshots_sha256") or {}) != 4:
        raise OwnerReleaseHold("FOUR_VIEWPORT_SCREENSHOTS_REQUIRED")

    return {
        "manifest": m, "baseline": baseline,
        "replacements": replace, "additions": additions,
        "after": baseline | replace | additions,
        "source": source,
    }


def _root_file(path: Path) -> None:
    if (path.is_symlink() or not path.is_file()
        or path.stat().st_uid != 0
        or stat.S_IMODE(path.stat().st_mode) != 0o600
        or path.stat().st_nlink != 1):
        raise OwnerReleaseHold("ROOT_OWNED_0600_SINGLE_LINK_FILE_REQUIRED:" + path.name)


def verify_protected_backup(release: dict[str, Any],
                            *, archive: Path = BACKUP,
                            backup_dir: Path = BACKUP_DIR) -> dict:
    """Direct root-only, read-only custody audit; NEVER grants owner approval."""
    if os.geteuid() != 0:
        raise OwnerReleaseHold("ORIGINAL_ROOT_OWNER_SESSION_REQUIRED")
    if (backup_dir.is_symlink() or not backup_dir.is_dir()
        or backup_dir.stat().st_uid != 0
        or stat.S_IMODE(backup_dir.stat().st_mode) != 0o700):
        raise OwnerReleaseHold("ROOT_PRIVATE_SITE_RELEASE_DIRECTORY_REQUIRED")
    _root_file(archive)
    if sha(archive) != EXPECTED_BACKUP_SHA:
        raise OwnerReleaseHold("FOUNDER_ROOT_ARCHIVE_SHA_MISMATCH")
    seen = set()
    limit = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if (not member.isfile() or member.name not in release["baseline"]
                or member.name in seen or member.size > 20000000):
                raise OwnerReleaseHold("PROTECTED_ROLLBACK_MEMBER_UNSAFE")
            content = tar.extractfile(member)
            if content is None or sha256(content.read()).hexdigest() != release["baseline"][member.name]:
                raise OwnerReleaseHold("ROOT_BACKUP_MEMBER_SHA_MISMATCH")
            seen.add(member.name)
            limit += member.size
            if limit > 60000000:
                raise OwnerReleaseHold("ROOT_BACKUP_UNBOUNDED")
    if seen != set(release["baseline"]):
        raise OwnerReleaseHold("ROOT_BACKUP_INCOMPLETE")
    return {"status":"ORIGINAL_700_FILE_ROOT_BACKUP_INDEPENDENT_READBACK_VERIFIED",
            "archive_sha256":sha(archive),"members_verified":len(seen),
            "owner_publication_approval_verified":False,
            "publication_authorized":False,
            "public_site_changed":False}


def verify_owner_and_archive(release: dict[str, Any],
                             *, archive: Path = BACKUP,
                             approval: Path = OWNER_APPROVAL,
                             backup_dir: Path = BACKUP_DIR) -> dict:
    evidence=verify_protected_backup(release,archive=archive,backup_dir=backup_dir)
    _root_file(approval)
    d = read_json(approval)
    required = {
        "schema_version": "empire.website.solar_commercial_owner_approval.v1",
        "original_owner": "EXISTING_ASTRA_WEBSITE_RELEASE_OWNER",
        "independent_visual_and_commercial_copy_review_complete": True,
        "final_founder_visual_acceptance_confirmed": True,
        "approved_founder_visual_receipt_sha256": EXPECTED_FOUNDER_RECEIPT_SHA,
        "approved_manifest_sha256": EXPECTED_MANIFEST_SHA,
        "approved_root_backup_sha256": EXPECTED_BACKUP_SHA,
        "approved_source_commit": SOURCE_COMMIT,
        "approved_replacement_count": 10,
        "approved_new_hashed_asset_count": 10,
        "publication_previously_performed": False,
    }
    for key, value in required.items():
        if d.get(key) != value or type(d.get(key)) is not type(value):
            raise OwnerReleaseHold("INDEPENDENT_ASTRA_OWNER_APPROVAL_NOT_ATTESTED:" + key)
    return {"owner_receipt_sha256":sha(approval),
            "archive_sha256":evidence["archive_sha256"],
            "members_verified":evidence["members_verified"]}


def _origin_get(route: str) -> bytes:
    req = Request("http://127.0.0.1" + route, headers={
        "Host": "empire-ai.co.uk",
        "User-Agent": "Empire-Original-ASTRA-SolarCommercial-GET-Only/1.0",
    }, method="GET")
    with urlopen(req, timeout=12) as resp:
        if resp.status != 200:
            raise OwnerReleaseHold("PUBLIC_ORIGIN_GET_NON_200:" + route)
        body = resp.read(21000001)
        if not body or len(body) > 21000000:
            raise OwnerReleaseHold("PUBLIC_ORIGIN_GET_INVALID_BYTES:" + route)
        return body


def _public_get(route: str) -> bytes:
    # Public customer-facing HTTPS, distinct from localhost origin.
    # No POST or form submission is ever performed here.
    req = Request("https://empire-ai.co.uk" + route, headers={
        "User-Agent": "Empire-ASTRA-PostRelease-PublicReadback/1.0",
    }, method="GET")
    with urlopen(req, timeout=18) as response:
        if response.status != 200 or response.geturl().split("?")[0] != "https://empire-ai.co.uk" + route:
            raise OwnerReleaseHold("PUBLIC_HTTPS_ROUTE_NOT_EXACT_200:" + route)
        body = response.read(21000001)
        if not body or len(body) > 21000000:
            raise OwnerReleaseHold("PUBLIC_HTTPS_INVALID_RESPONSE:" + route)
        return body


def public_readback(*, fetch=None, live: Path = LIVE) -> dict:
    """Verify public HTTPS only AFTER an owner-authorised release.

    This performs GETs, never grants release authority, and deliberately
    refuses to report a success for the currently live old pages.
    """
    _require_original_v2_brand_still_approved()
    get = _public_get if fetch is None else fetch
    source = read_json(SOURCE_INVENTORY)
    m = read_json(MANIFEST)
    if sha(MANIFEST) != EXPECTED_MANIFEST_SHA or sha(SOURCE_INVENTORY) != EXPECTED_INVENTORY_SHA:
        raise OwnerReleaseHold("PUBLIC_READBACK_PINNED_SOURCE_CHANGED")
    if m.get("source_commit") != SOURCE_COMMIT:
        raise OwnerReleaseHold("PUBLIC_READBACK_SOURCE_IDENTITY_CHANGED")
    existing = source["baseline_sha256"]
    replace = {
        path: row["proposed_sha256"]
        for path,row in (m["targets"] | m["route_data_sidecars"]).items()
    }
    additions = m["added_assets_sha256"]
    if len(existing)!=700 or len(replace)!=10 or len(additions)!=10:
        raise OwnerReleaseHold("PUBLIC_READBACK_SCOPE_CHANGED")
    expected = existing | replace | additions
    if site_inventory(live) != expected:
        raise OwnerReleaseHold("PUBLIC_READBACK_ORIGINAL_SITE_NOT_PUBLISHED_EXACT_710")
    routes = (("/commercial","commercial.html"),
              ("/industries/solar","industries/solar.html"))
    adjacent = (
        ("/","index.html"),
        ("/buy","buy.html"),
        ("/industries","industries.html"),
        ("/industries/hvac","industries/hvac.html"),
        ("/predictive-revenue","predictive-revenue.html"),
        ("/trust","trust.html"),
    )
    checked = []
    for route, file in routes:
        if sha256(get(route)).hexdigest() != replace[file]:
            raise OwnerReleaseHold("PUBLIC_HTTPS_NEW_HTML_MISMATCH:" + route)
        checked.append(route)
    for route, file in adjacent:
        if sha256(get(route)).hexdigest() != existing[file]:
            raise OwnerReleaseHold("PUBLIC_HTTPS_NEIGHBOUR_CHANGED:" + route)
        checked.append(route)
    for path, digest in additions.items():
        if sha256(get("/"+path)).hexdigest() != digest:
            raise OwnerReleaseHold("PUBLIC_HTTPS_HASHED_ASSET_MISMATCH:"+path)
        checked.append("/"+path)
    return {
        "status":"PUBLIC_HTTPS_EXACT_SOLAR_COMMERCIAL_V2_18_GET_READBACK_PASS",
        "public_html_routes":2,
        "unchanged_neighbour_routes":6,
        "new_immutable_assets":10,
        "matched_live_site_file_count":710,
        "http_gets":len(checked),
        "public_gets_only":True,
        "form_submissions":0,
        "payments_activated":False,
        "owner_authority_granted_by_this_probe":False,
        "publication_action_performed_by_this_probe":False,
    }


def preflight(*, live: Path = LIVE) -> dict:
    _require_original_v2_brand_still_approved()
    r = candidate(live=live)
    return {
        "status":"TWO_PAGE_SCOPE_VERIFIED_ORIGINAL_OWNER_APPROVAL_REQUIRED",
        "source_commit":SOURCE_COMMIT,
        "site_files_before":len(r["baseline"]),
        "site_files_proposed":len(r["after"]),
        "old_pages_replaced":len(r["replacements"]),
        "new_assets":len(r["additions"]),
        "founder_root_backup_sha256_pinned":EXPECTED_BACKUP_SHA,
        "founder_exact_visual_copy_pricing_approved":True,
        "founder_approval_receipt_sha256":EXPECTED_FOUNDER_RECEIPT_SHA,
        "owner_approval_verified":False,
        "root_backup_verified_in_this_nonroot_session":False,
        "publication_performed":False,
        "production_writes":False,
    }


def _publish_locked() -> dict:
    _require_original_v2_brand_still_approved()
    if os.geteuid() != 0:
        raise OwnerReleaseHold("ROOT_OPERATOR_REQUIRED")
    if ROOT_RECEIPT.exists() or ROOT_RECEIPT.is_symlink():
        raise OwnerReleaseHold("ALREADY_PUBLISHED_NO_SECOND_APPLY")
    release = candidate()
    approved = verify_owner_and_archive(release)
    # Fail if a concurrent original-site release took place before the write.
    if site_inventory(LIVE) != release["baseline"]:
        raise OwnerReleaseHold("LIVE_CHANGED_AFTER_OWNER_APPROVAL")
    adjacent = {route:sha256(_origin_get(route)).hexdigest() for route in NEIGHBOURS}
    for route in ROUTES:
        file = route.lstrip("/") + ".html"
        if sha256(_origin_get(route)).hexdigest() != release["baseline"][file]:
            raise OwnerReleaseHold("ORIGINAL_PUBLIC_HTML_NOT_CURRENT:" + route)

    def check_and_receipt():
        if site_inventory(LIVE) != release["after"]:
            raise OwnerReleaseHold("COMPLETE_SITE_AFTER_RELEASE_SHA_MISMATCH")
        for route in ROUTES:
            name = route.lstrip("/") + ".html"
            if sha256(_origin_get(route)).hexdigest() != release["replacements"][name]:
                raise OwnerReleaseHold("NEW_PUBLIC_HTML_NOT_SERVING:" + route)
        for route, old_hash in adjacent.items():
            if sha256(_origin_get(route)).hexdigest() != old_hash:
                raise OwnerReleaseHold("NEIGHBOUR_SITE_CHANGED:" + route)
        for name, digest in release["additions"].items():
            if sha256(_origin_get("/" + name)).hexdigest() != digest:
                raise OwnerReleaseHold("NEW_PUBLIC_IMMUTABLE_ASSET_NOT_SERVING:" + name)
        receipt = {
            "schema_version": "empire.website.solar_commercial_v2_root_published.v1",
            "status": "EXACT_SOLAR_COMMERCIAL_V2_PUBLISHED_ORIGIN_GET_AND_BYTES_VERIFIED",
            "source_commit": SOURCE_COMMIT,
            "manifest_sha256": EXPECTED_MANIFEST_SHA,
            "founder_approval_receipt_sha256": EXPECTED_FOUNDER_RECEIPT_SHA,
            "root_backup_sha256": approved["archive_sha256"],
            "original_owner_receipt_sha256": approved["owner_receipt_sha256"],
            "before_file_count": len(release["baseline"]),
            "after_file_count": len(release["after"]),
            "replaced_files": sorted(release["replacements"]),
            "new_immutable_assets": sorted(release["additions"]),
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "real_enquiry_submitted": False,
            "outbound_sent": False,
            "money_moved": False,
        }
        temp = ROOT_RECEIPT.with_name(".solar-commercial-v2-receipt.tmp")
        if temp.exists() or temp.is_symlink():
            raise OwnerReleaseHold("UNEXPECTED_OWNER_TEMP_RECEIPT")
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf8") as out:
                json.dump(receipt,out,sort_keys=True,indent=2);out.write("\n")
                out.flush();os.fsync(out.fileno())
            os.link(temp, ROOT_RECEIPT)
        finally:
            temp.unlink(missing_ok=True)
    return apply_four_pages_and_eight_assets(
        live=LIVE, stage=PACKET / "proposed_site",
        baseline=release["baseline"],
        replacements=release["replacements"],
        additions=release["additions"], final_probe=check_and_receipt,
    )


def apply() -> dict:
    _require_original_v2_brand_still_approved()
    if os.geteuid() != 0:
        raise OwnerReleaseHold("ROOT_OPERATOR_ONLY_NO_BUILDER_APPLY")
    if (BACKUP_DIR.is_symlink() or not BACKUP_DIR.is_dir()
        or BACKUP_DIR.stat().st_uid != 0
        or stat.S_IMODE(BACKUP_DIR.stat().st_mode) != 0o700):
        raise OwnerReleaseHold("PRIVATE_ROOT_BACKUP_DIRECTORY_REQUIRED")
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "rb") as lock:
        meta = os.fstat(lock.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1:
            raise OwnerReleaseHold("UNTRUSTED_RELEASE_LOCK")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OwnerReleaseHold("ANOTHER_SITE_OWNER_RELEASE_ALREADY_ACTIVE") from exc
        return _publish_locked()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--preflight",action="store_true")
    choice.add_argument("--audit-protected-backup",action="store_true")
    choice.add_argument("--public-readback",action="store_true")
    choice.add_argument(PUBLISH_FLAG,action="store_true")
    a = parser.parse_args()
    try:
        if a.preflight:
            result=preflight()
        elif a.audit_protected_backup:
            result=verify_protected_backup(candidate())
        elif a.public_readback:
            result=public_readback()
        else:
            result=apply()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,tarfile.TarError) as e:
        print(json.dumps({"status":"SOLAR_COMMERCIAL_OWNER_RELEASE_HELD",
                          "reason": str(e)[:260], "publication_performed":False,
                          "money_moved":False, "outbound_sent":False},sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
