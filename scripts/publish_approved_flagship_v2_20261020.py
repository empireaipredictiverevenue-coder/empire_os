"""One-time founder-approved exact-byte flagship V2 static website release.

Atomic Linux renameat2 RENAME_EXCHANGE, original root-protected backup,
owner-attested candidate and postpublication route/asset/checkout checks.
Does NOT alter any financial, outbound, consent or ingestion gate.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tarfile
import urllib.request
import urllib.error

from scripts.review_flagship_public_v2_signoff_20261020 import review, SCHEMA as REVIEW_SCHEMA
from scripts.review_flagship_full_export_union_20261020 import (
    CANDIDATE, LIVE, _file_index, ReleaseHold,
)

EXPECTED_INVENTORY = "650318b7e8db14213cb115eb5adc90be846f1d6681142d04e9c293bd135bcfe3"
EXACT_ISSUED_REVIEW = CANDIDATE / "PUBLIC_V2_RELEASE_SIGNOFF_PROPOSAL.json"
ORIGINAL = CANDIDATE / "out"
READY = CANDIDATE / "out.v2-staged"
ROLLBACK = CANDIDATE / "out.pre-v2-public"
RECEIPT = Path("/var/backups/empire-website/FLAGSHIP_V2_PUBLICATION_RECEIPT_20261020.json")
LOCK = Path("/var/lock/empire-flagship-v2-release.lock")
EXPECTED_PAGE_SHA = {
    "index.html": "061b03b39a22575a4ed79626e1ef44637a012345bcc9a855610b07e45871e209",
    "buy.html": "435cd7b1fed3490998ec2ca74cd0fc68f1a6ff0a324a10adba6428def4e92552",
    "commercial.html": "c0f8518d0113ea30faf38cd4f2f769e80fd2ff46d715e4d86100cde6f4659b7f",
}
SCHEMA = "empire.website.flagship_v2_atomic_publication_receipt.v1"


def _atomic_directory_swap(left: Path, right: Path) -> None:
    if left.stat().st_dev != right.stat().st_dev:
        raise ReleaseHold("RENAME_CROSS_FILESYSTEM_HOLD")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = (
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    # -100 = AT_FDCWD, 2 = RENAME_EXCHANGE
    if renameat2(-100, os.fsencode(left), -100, os.fsencode(right), 2) != 0:
        err = ctypes.get_errno()
        raise OSError(err, "ATOMIC_STATIC_DIRECTORY_SWAP_FAILED")


def _expected_inventory(private_receipt: dict) -> dict[str, tuple[str, int]]:
    original = _file_index(ORIGINAL)
    expected = private_receipt["static_file_sha256"]
    if len(original) != 632 or set(original) != set(expected):
        raise ReleaseHold("WRONG_CANDIDATE_PATH_SET")
    if any(original[k][0] != expected[k] for k in original):
        raise ReleaseHold("CANDIDATE_FILES_CHANGED")
    return original


def _live_equals_protected_original_backup() -> bool:
    """Compare *all* original public bytes to the root-protected tar receipt."""
    archive = Path("/var/backups/empire-website/flagship_current_live_20261020_before_union.tar")
    actual = _file_index(LIVE)
    recorded: dict[str, tuple[str, int]] = {}
    with tarfile.open(archive, mode="r:") as source:
        for item in source:
            if item.isdir():
                continue
            if not item.isfile() or not item.name.startswith("out/"):
                return False
            name = item.name.removeprefix("out/")
            if not name or name in recorded:
                return False
            fp = source.extractfile(item)
            if fp is None:
                return False
            digest = sha256()
            size = 0
            for chunk in iter(lambda: fp.read(65536), b""):
                digest.update(chunk)
                size += len(chunk)
            recorded[name] = (digest.hexdigest(), size)
            if len(recorded) > 2000:
                return False
    return recorded == actual


def _fixed_approval_check() -> tuple[dict, dict[str, tuple[str, int]]]:
    result = review(require_backup=True)
    if (
        result.get("schema_version") != REVIEW_SCHEMA
        or result.get("status") != "EXACT_V2_BUILD_PROVEN_FOUNDER_PUBLICATION_APPROVAL_REQUIRED"
        or result.get("candidate_static_inventory_sha256") != EXPECTED_INVENTORY
        or result.get("full_static_file_count") != 632
        or result.get("original_live_static_file_count") != 603
        or not _live_equals_protected_original_backup()
        or result.get("all_candidate_file_hashes_verified") is not True
        or result.get("original_gateway_pinned_assets_verified") is not True
        or result.get("public_files_modified") is not False
    ):
        raise ReleaseHold("EXACT_FOUNDER_APPROVAL_SOURCE_HOLD")
    if result.get("exact_intended_new_html") != EXPECTED_PAGE_SHA:
        raise ReleaseHold("APPROVED_HTML_BYTE_HASH_CHANGED")
    sealed = json.loads(EXACT_ISSUED_REVIEW.read_text(encoding="utf-8"))
    changed_review_keys = {
        key for key in set(sealed) | set(result)
        if sealed.get(key) != result.get(key)
    }
    if (
        not changed_review_keys.issubset({"private_browser_receipt_sha256"})
        or sealed.get("website_owner_public_release_approved") is not False
    ):
        raise ReleaseHold("SEALED_REVIEW_CORE_EVIDENCE_CHANGED")
    if changed_review_keys:
        from scripts.review_flagship_public_v2_signoff_20261020 import BROWSER
        if (
            BROWSER.stat().st_mtime_ns <= EXACT_ISSUED_REVIEW.stat().st_mtime_ns
            or result["private_browser_receipt_sha256"] ==
               sealed["private_browser_receipt_sha256"]
        ):
            raise ReleaseHold("BROWSER_EVIDENCE_REVALIDATION_UNTRUSTED")
        # The browser proof was repeated *after* the original packet.
        # review() independently verifies every result; its source/build,
        # page digests, checkout release and rollback proofs are unchanged.
        # Preserve both review hashes for an auditable, non-circular recheck.
    result["prior_sealed_browser_receipt_sha256"] = sealed[
        "private_browser_receipt_sha256"
    ]
    result["browser_evidence_rechecked_after_packet"] = bool(changed_review_keys)
    private_receipt = json.loads(
        (CANDIDATE / "RELEASE_CANDIDATE_RECEIPT.json").read_text(encoding="utf-8")
    )
    return result, _expected_inventory(private_receipt)


def _get_public(route: str, *, json_expected: bool = False) -> bytes:
    request = urllib.request.Request(
        "http://127.0.0.1" + route,
        headers={"Host": "empire-ai.co.uk", "Accept": "*/*"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=6) as response:
        if response.status != 200:
            raise ReleaseHold("LIVE_GET_ROUTE_STATUS_HOLD")
        payload = response.read(800_001)
        if not payload or len(payload) > 800_000:
            raise ReleaseHold("LIVE_GET_ROUTE_PAYLOAD_HOLD")
        if json_expected:
            if response.headers.get_content_type() != "application/json":
                raise ReleaseHold("LIVE_GET_API_TYPE_HOLD")
            if not isinstance(json.loads(payload), dict):
                raise ReleaseHold("LIVE_GET_API_SHAPE_HOLD")
        elif response.headers.get_content_type() != "text/html":
            raise ReleaseHold("LIVE_PAGE_CONTENT_TYPE_HOLD")
        return payload


def _verify_live_current(expected: dict[str, tuple[str, int]]) -> dict:
    if _file_index(LIVE) != expected:
        raise ReleaseHold("PUBLISHED_BYTE_INTEGRITY_HOLD")
    exact_paths = {
        "/": "index.html", "/buy": "buy.html", "/commercial": "commercial.html",
    }
    for route, name in exact_paths.items():
        if sha256(_get_public(route)).hexdigest() != EXPECTED_PAGE_SHA[name]:
            raise ReleaseHold("LIVE_HTML_SOURCE_MISMATCH")
    for page in (
        "/about", "/insights/revenue-opportunity-assessment",
    ):
        _get_public(page)
    # The original gateway deliberately blocks unapproved editorial,
    # finance/legal and roofing content even if files are present.
    for held_page in (
        "/roofing/installation-checklist", "/treasury-proof",
    ):
        req = urllib.request.Request(
            "http://127.0.0.1" + held_page,
            headers={"Host": "empire-ai.co.uk"}, method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as denied:
                raise ReleaseHold("UNAPPROVED_CONTENT_UNEXPECTEDLY_PUBLIC")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise ReleaseHold("CONTENT_GATE_STATUS_CHANGED") from None
    for api in (
        "/v1/checkout/catalog",
        "/v1/checkout/exchange/tiers",
        "/v1/checkout/brokerage/premium-discovery",
    ):
        _get_public(api, json_expected=True)
    request = urllib.request.Request(
        "http://127.0.0.1:8098/health",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise ReleaseHold("CHECKOUT_SERVICE_NOT_READY")
        health = json.load(response)
    if (
        not isinstance(health, dict)
        or health.get("status") != "online"
        or health.get("payment_execution") is not False
        or health.get("revenue_recognition") is not False
    ):
        raise ReleaseHold("FINANCIAL_GATES_CHANGED_HOLD")
    for name in (
        "empire-public-gateway.service", "empire-self-serve-checkout.service",
        "empire-ops-control.timer",
    ):
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", name],
            capture_output=True, timeout=5, text=True,
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            raise ReleaseHold("EXPECTED_EXISTING_SERVICE_NOT_ACTIVE")
    return {
        "public_v2_page_hashes_match": True,
        "public_html_gets_verified": 5,
        "unapproved_guide_and_treasury_routes_still_404": True,
        "checkout_get_only_apis_verified": 3,
        "payment_execution": False,
        "revenue_recognition": False,
        "existing_services_active": True,
        "buyer_post_submitted": False,
    }


def _prepare_stage(expected: dict[str, tuple[str, int]]) -> None:
    if READY.exists() or READY.is_symlink() or ROLLBACK.exists() or RECEIPT.exists():
        raise ReleaseHold("PUBLISH_PREEXISTING_STATE_HOLD")
    shutil.copytree(ORIGINAL, READY)
    user = pwd.getpwnam("ubuntu")
    # Live website owner must retain ordinary access for later reviewed updates.
    for folder, dirs, files in os.walk(READY):
        os.chown(folder, user.pw_uid, user.pw_gid)
        for name in files:
            os.chown(os.path.join(folder, name), user.pw_uid, user.pw_gid)
    os.chmod(READY, 0o775)
    if _file_index(READY) != expected:
        raise ReleaseHold("LOCAL_PUBLISH_COPY_CHANGED")


def _write_receipt(payload: dict) -> None:
    fd = os.open(RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def publish(expected_arg: str) -> dict:
    if os.geteuid() != 0:
        raise ReleaseHold("ROOT_GUARDED_PUBLICATION_REQUIRED")
    if expected_arg != EXPECTED_INVENTORY:
        raise ReleaseHold("FOUNDER_APPROVED_INVENTORY_MISMATCH")
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if RECEIPT.exists() or ROLLBACK.exists() or READY.exists():
            raise ReleaseHold("PUBLISH_ALREADY_ATTEMPTED_OR_COMPLETED")
        result, expected = _fixed_approval_check()
        previous = _file_index(LIVE)
        if len(previous) != 603:
            raise ReleaseHold("PRIOR_SITE_FILE_COUNT_CHANGED")
        _prepare_stage(expected)
        # Check original safety after copy, immediately before atomic switch.
        _fixed_approval_check()
        if _file_index(LIVE) != previous:
            raise ReleaseHold("LIVE_UPDATED_CONCURRENTLY")
        swapped = False
        try:
            _atomic_directory_swap(LIVE, READY)
            swapped = True
            runtime = _verify_live_current(expected)
            if _file_index(READY) != previous:
                raise ReleaseHold("ROLLBACK_BYTES_NOT_PRESERVED")
            # Preserve exact old directory separate from private new stage.
            os.rename(READY, ROLLBACK)
            receipt = {
                "schema_version": SCHEMA,
                "status": "EXACT_APPROVED_V2_WEBSITE_PUBLICATION_VERIFIED",
                "published_at_utc": datetime.now(timezone.utc).isoformat(),
                "founder_approved_inventory_sha256": EXPECTED_INVENTORY,
                "original_live_file_count": 603,
                "new_public_file_count": 632,
                "private_source_receipt_sha256": result["private_candidate_receipt_sha256"],
                "old_october_13_checkout_manifest_preserved": True,
                "old_live_directory_saved": str(ROLLBACK),
                "root_protected_tar_rollback_preserved": True,
                "public_files_modified": True,
                "payment_activation_changed": False,
                "outbound_activated": False,
                "unapproved_content_activation": False,
                "new_schedulers_created": False,
                "runtime": runtime,
            }
            _write_receipt(receipt)
            return receipt
        except BaseException:
            # A verification error immediately reverts the exact public tree.
            recovery = ROLLBACK if ROLLBACK.exists() else READY
            if swapped and recovery.exists():
                _atomic_directory_swap(LIVE, recovery)
            raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-founder-approved-exact-v2", action="store_true")
    parser.add_argument("--expected-inventory-sha256", default="")
    args = parser.parse_args(argv)
    if not args.apply_founder_approved_exact_v2:
        parser.error("exact founder approval required")
    try:
        result = publish(args.expected_inventory_sha256)
        print(json.dumps({
            "status": result["status"],
            "published_files": result["new_public_file_count"],
            "approved_inventory": result["founder_approved_inventory_sha256"],
            "runtime": result["runtime"],
            "rollback_retained": True,
        }, sort_keys=True))
        return 0
    except (ReleaseHold, OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({
            "status": "WEBSITE_PUBLICATION_HELD_OR_ROLLED_BACK",
            "reason": str(e) if isinstance(e, ReleaseHold) else type(e).__name__,
            "public_launch_verified": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
