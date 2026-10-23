"""One-time EXISTING Website & Growth owner: exact V2 surgical website publication.

Never full-site sync. Exact 10 route files + 6 collision-free immutable assets.
Requires founder-approved CLI flag, root-protected FRESH 653-file tar backup,
pinned source and staged build, atomic per-file replacement, verified HTTP GET,
automatic narrow rollback on failed post-release verification.
No forms, CRM, messages, payments, timers, or other site routes are changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
from typing import Any
from urllib.request import Request, urlopen

from scripts.release_predictive_roofing_two_page_20261022 import (
    apply_four_pages_and_eight_assets,
)

ROOT = Path("/srv/empire_os")
MANIFEST = ROOT / "docs/website/release_candidates/INDUSTRY_ENQUIRY_SOURCE_HANDOFF_20261023_V2.json"
MANIFEST_SHA256 = "d41167d3e2413dbfe914bf8f0527ef0da26da3df0723aff8eaa3c1b9f86065aa"
LIVE = ROOT / "apps/empire-public-site/out"
SOURCE_COMMIT = "758a5a31b"
ARCHIVE = Path("/var/backups/empire-website/industry_enquiry_v2_pre_653_20261023.tar")
BACKUP_RECEIPT = ARCHIVE.with_suffix(".receipt.json")
RELEASE_RECEIPT = ARCHIVE.with_suffix(".publication.json")
LOCK = Path("/var/lock/empire-industry-enquiry-v2-release-20261023.lock")
APPROVAL = "--apply-founder-approved-industry-enquiry-v2"
ROUTES = (
    "/commercial", "/industries/roofing", "/industries/solar",
    "/industries/hvac", "/industries/property",
)
KEEP = ("/", "/buy", "/predictive-revenue", "/privacy")


class ReleaseHold(ValueError):
    pass


def _hash(value: bytes) -> str:
    return sha256(value).hexdigest()


def _index(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise ReleaseHold("SITE_DIRECTORY_MISSING_OR_SYMLINK")
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ReleaseHold("SYMLINK_IN_SITE_TREE")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if not stat.S_ISREG(path.stat().st_mode):
                raise ReleaseHold("NONREGULAR_STATIC_PAYLOAD")
            out[name] = _hash(path.read_bytes())
            if len(out) > 2000:
                raise ReleaseHold("UNBOUNDED_STATIC_INVENTORY")
    return out


def _get(route: str) -> bytes:
    req = Request("http://127.0.0.1" + route, headers={
        "Host": "empire-ai.co.uk",
        "User-Agent": "EmpireOS-Original-Website-Owner-V2-GET-Only/1.0",
        "Accept": "*/*",
    }, method="GET")
    with urlopen(req, timeout=8) as response:
        if response.status != 200:
            raise ReleaseHold("LIVE_GET_NON_200_" + route)
        body = response.read(900_001)
        if not body or len(body) > 900_000:
            raise ReleaseHold("LIVE_GET_BOUNDED_READ_FAILED_" + route)
        return body


def preflight() -> dict[str, Any]:
    if _hash(MANIFEST.read_bytes()) != MANIFEST_SHA256:
        raise ReleaseHold("PINNED_V2_MANIFEST_CHANGED")
    d = json.loads(MANIFEST.read_text())
    if (d.get("schema_version") != "empire.website.industry_enquiry_release_candidate.v2"
        or d.get("source_commit") != SOURCE_COMMIT
        or d.get("mode") != "OBSERVE"
        or d.get("status") != "STAGED_BYTES_VERIFIED_OWNER_RELEASE_APPROVAL_REQUIRED"
        or d.get("surgical_release_authorized") is not False
        or d.get("full_site_deployment_authorized") is not False
        or d.get("founder_or_website_owner_release_approval_received") is not False):
        raise ReleaseHold("INVALID_STAGED_RELEASE_CONTRACT")
    if (RELEASE_RECEIPT.exists() or RELEASE_RECEIPT.is_symlink()
        or ARCHIVE.exists() or ARCHIVE.is_symlink()
        or BACKUP_RECEIPT.exists() or BACKUP_RECEIPT.is_symlink()):
        raise ReleaseHold("VERSIONED_RELEASE_OR_BACKUP_ALREADY_EXISTS_REVIEW_REQUIRED")
    stage = Path(d["staging_export"])
    project = stage.parent.parent.parent
    if (stage.is_symlink() or stage.parent.is_symlink()
        or subprocess.check_output(["git", "-C", str(project), "rev-parse", "--short=9", "HEAD"], text=True).strip() != SOURCE_COMMIT):
        raise ReleaseHold("UNTRUSTED_STAGED_SOURCE_REVISION")
    for name, expected in d["source_sha256"].items():
        original = project / name
        if original.is_symlink() or _hash(original.read_bytes()) != expected:
            raise ReleaseHold("PINNED_SOURCE_DRIFT_" + name)
    replace = d["proposed_surgical_replacements_sha256"]
    old = d["expected_live_pre_release_sha256"]
    add = d["proposed_immutable_additions_sha256"]
    refs = d["referenced_staged_assets_sha256"]
    if (set(replace) != set(old) or len(replace) != 10 or len(add) != 6
        or len(refs) != 10
        or d["counts"]["live_files"] != 653
        or d["counts"]["preserved_live_files"] != 643
        or d["counts"]["stage_files"] != 135):
        raise ReleaseHold("EXACT_V2_RELEASE_SCOPE_CHANGED")
    exact_paths = {r.removeprefix("/") + ext for r in ROUTES for ext in (".html", ".txt")}
    if set(replace) != exact_paths:
        raise ReleaseHold("UNEXPECTED_PUBLIC_ROUTE_REPLACEMENT")
    if any(not k.startswith("_next/static/") for k in add):
        raise ReleaseHold("UNEXPECTED_MUTABLE_NEW_ASSET")
    current = _index(LIVE)
    stage_index = _index(stage)
    if len(current) != 653 or len(stage_index) != 135:
        raise ReleaseHold("LIVE_OR_STAGED_FILE_COUNT_DRIFT")
    for name, expected in old.items():
        if current.get(name) != expected:
            raise ReleaseHold("PINNED_LIVE_PRE_RELEASE_HASH_CHANGED_" + name)
    for name, expected in {**replace, **add, **refs}.items():
        if stage_index.get(name) != expected:
            raise ReleaseHold("PINNED_STAGED_FILE_HASH_CHANGED_" + name)
    if any(name in current for name in add):
        raise ReleaseHold("IMMUTABLE_ASSET_COLLISION")
    if any(k in replace for k in ("index.html", "buy.html", "privacy.html", "predictive-revenue.html")):
        raise ReleaseHold("PROTECTED_OWNER_ROUTE_OVERLAP")
    old_http = {}
    for route in ROUTES:
        old_http[route] = _hash(_get(route))
        if old_http[route] != old[route.removeprefix("/") + ".html"]:
            raise ReleaseHold("LIVE_HTTP_DOES_NOT_MATCH_STATIC_SOURCE_" + route)
    keep_http = {r: _hash(_get(r)) for r in KEEP}
    return {"status": "APPROVED_BYTES_READY_FRESH_ROOT_BACKUP_REQUIRED",
            "stage": str(stage), "source_commit": SOURCE_COMMIT,
            "live_before_sha256": current, "stage_sha256": stage_index,
            "live_original_http_sha256": old_http,
            "protected_http_sha256": keep_http,
            "old": old, "replace": replace, "add": add, "referenced_assets": refs,
            "public_writes_performed": False, "backup_verified": False}


def archive_full_site(*, root: Path, dest: Path, contents: dict[str, str]) -> dict[str, Any]:
    """Fresh O_EXCL protected tar; verify every archived payload against source."""
    if dest.exists() or dest.is_symlink():
        raise ReleaseHold("BACKUP_ALREADY_EXISTS")
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise ReleaseHold("BACKUP_DIRECTORY_NOT_TRUSTED")
    if os.geteuid() == 0 and (
        dest.parent.stat().st_uid != 0
        or stat.S_IMODE(dest.parent.stat().st_mode) & 0o077
    ):
        raise ReleaseHold("ROOT_PROTECTED_BACKUP_DIRECTORY_REQUIRED")
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            with tarfile.open(mode="w", fileobj=stream) as tar:
                for rel in sorted(contents):
                    src = root / rel
                    if src.is_symlink() or not src.is_file() or _hash(src.read_bytes()) != contents[rel]:
                        raise ReleaseHold("BACKUP_SOURCE_DRIFT_" + rel)
                    tar.add(src, arcname="out/" + rel, recursive=False)
            stream.flush()
            os.fsync(stream.fileno())
        recovered: dict[str, str] = {}
        with tarfile.open(dest, "r:") as archive:
            for member in archive:
                if not member.isfile() or not member.name.startswith("out/"):
                    raise ReleaseHold("NONREGULAR_FILE_IN_BACKUP")
                rel = member.name.removeprefix("out/")
                if rel in recovered:
                    raise ReleaseHold("DUPLICATE_ARCHIVED_FILE")
                fileobj = archive.extractfile(member)
                if fileobj is None:
                    raise ReleaseHold("UNREADABLE_ARCHIVED_PAYLOAD")
                recovered[rel] = _hash(fileobj.read())
        if recovered != contents:
            raise ReleaseHold("BACKUP_READBACK_HASH_MISMATCH")
        return {"backup_tar": str(dest), "archive_sha256": _hash(dest.read_bytes()),
                "files_readback_verified": len(recovered),
                "complete_original_sha256": _hash(json.dumps(contents, sort_keys=True).encode()),
                "root_owned_private": bool(os.geteuid() == 0 and dest.stat().st_uid == 0
                                           and stat.S_IMODE(dest.stat().st_mode) == 0o600)}
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def _save_private_once(path: Path, payload: dict[str, Any]) -> None:
    data = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def publish() -> dict[str, Any]:
    if os.geteuid() != 0:
        raise ReleaseHold("ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED")
    result = preflight()
    backup = archive_full_site(root=LIVE, dest=ARCHIVE,
                               contents=result["live_before_sha256"])
    if (backup["files_readback_verified"] != 653
        or backup["root_owned_private"] is not True):
        raise ReleaseHold("VERIFIED_ROOT_ROLLBACK_NOT_ESTABLISHED")
    _save_private_once(BACKUP_RECEIPT, {**backup,
        "schema_version": "empire.website.industry_enquiry_v2_backup.v1",
        "source_commit": SOURCE_COMMIT, "publication_authorized": False,
        "customer_mutations": False})
    if _index(LIVE) != result["live_before_sha256"]:
        raise ReleaseHold("LIVE_TREE_CHANGED_AFTER_VERIFIED_BACKUP")
    expected = {**result["live_before_sha256"], **result["replace"], **result["add"]}
    stage = Path(result["stage"])
    verified = {"status": None}

    def verify_and_record() -> None:
        if _index(LIVE) != expected:
            raise ReleaseHold("LIVE_FULL_STATIC_TREE_NOT_PINNED")
        for route in ROUTES:
            expected_digest = result["replace"][route.removeprefix("/") + ".html"]
            if _hash(_get(route)) != expected_digest:
                raise ReleaseHold("LIVE_HTTP_NEW_ROUTE_HASH_MISMATCH_" + route)
        for route, previous in result["protected_http_sha256"].items():
            if _hash(_get(route)) != previous:
                raise ReleaseHold("PROTECTED_LIVE_ROUTE_CHANGED_" + route)
        for asset, digest in result["add"].items():
            if _hash(_get("/" + asset)) != digest:
                raise ReleaseHold("NEW_STATIC_ASSET_HTTP_MISMATCH_" + asset)
        response = _get("/v1/checkout/commercial/offers")
        if not isinstance(json.loads(response), dict):
            raise ReleaseHold("ORIGINAL_COMMERCIAL_OFFERS_API_UNHEALTHY")
        receipt = {
            "schema_version": "empire.website.industry_enquiry_v2_publication.v1",
            "status": "EXACT_APPROVED_INDUSTRY_ENQUIRY_V2_PUBLISHED_AND_GET_VERIFIED",
            "source_commit": SOURCE_COMMIT,
            "approved_manifest_sha256": MANIFEST_SHA256,
            "backup_archive_sha256": backup["archive_sha256"],
            "backup_verified_original_files": backup["files_readback_verified"],
            "replaced_original_route_files": len(result["replace"]),
            "added_immutable_assets": len(result["add"]),
            "preserved_unchanged_original_files": 653 - len(result["replace"]),
            "public_site_files_after": len(expected),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "owner_approval": "FOUNDER_EXPLICIT_CHAT_APPROVAL_20261023",
            "client_submissions": 0,
            "crm_writes": False, "outbound_sent": False,
            "payment_activation": False, "model_training": False,
        }
        _save_private_once(RELEASE_RECEIPT, receipt)
        verified["status"] = receipt
    try:
        apply_four_pages_and_eight_assets(
            live=LIVE, stage=stage, baseline=result["old"],
            replacements=result["replace"], additions=result["add"],
            final_probe=verify_and_record,
        )
    except Exception:
        if verified["status"] is None and RELEASE_RECEIPT.exists():
            RELEASE_RECEIPT.unlink()
        raise
    if verified["status"] is None:
        raise ReleaseHold("MISSING_SUCCESSFUL_RELEASE_RECEIPT")
    return verified["status"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--preflight", action="store_true")
    options.add_argument(APPROVAL, action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.preflight:
            result = preflight()
            print(json.dumps({
                "status": result["status"], "source_commit": SOURCE_COMMIT,
                "live_before_file_count": len(result["live_before_sha256"]),
                "replacement_count": len(result["replace"]),
                "additions_count": len(result["add"]),
                "requires_privileged_backup_and_publication": True,
                "public_writes_performed": False,
            }, sort_keys=True))
        else:
            # Refuse non-root calls BEFORE creating a lock in /run/lock.
            # An unprivileged O_CREAT there can leave a user-owned 0600 file
            # that Linux fs.protected_regular=2 subsequently denies to root.
            if os.geteuid() != 0:
                raise ReleaseHold("ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED")
            fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "rb") as lockfile:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                print(json.dumps(publish(), sort_keys=True))
        return 0
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as exc:
        print(json.dumps({
            "status": "INDUSTRY_ENQUIRY_V2_PUBLICATION_HELD",
            "reason": str(exc),
            "customer_submission": False, "payment_activation": False,
            "outbound_sent": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
