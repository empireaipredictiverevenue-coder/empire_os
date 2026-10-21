#!/usr/bin/env python3
"""Guarded FIRST-PAINT brokerage HTML-only release from an exact live baseline.

Adds hashed static build assets without rewriting shared files or other pages.
Does not restart services, enable payment, send messages or submit enquiries.
Founder approval applies only to this scoped first-paint release.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile

from scripts.release_brokerage_premium_commercial_assets_20261019 import Visible

LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
STAGED = Path("/home/ubuntu/empire_worktrees/brokerage_current_flagship_first_paint_fix_20261021/apps/empire-public-site/out")
RECEIPTS = Path("/home/ubuntu/empire_worktrees/brokerage_current_flagship_first_paint_fix_20261021/release_receipts")
OLD_SHA = "c0f8518d0113ea30faf38cd4f2f769e80fd2ff46d715e4d86100cde6f4659b7f"
NEW_SHA = "404d87e3c3ee366415662389992c0001eb25e0bcf24e526ef898b1f0e5f2e03e"
PATH = b"/v1/checkout/brokerage/premium-discovery"
REQUIRED = ("Agency Intelligence", "Enterprise Territory Intelligence")
ADDED_COUNT = 13
ADDED_TOTAL_BYTES = 315856

def digest(data: bytes) -> str:
    return sha256(data).hexdigest()

@dataclass(frozen=True)
class Plan:
    old: bytes
    new: bytes
    added: tuple[Path, ...]
    page_bundle: str

def inspect(live: Path = LIVE, stage: Path = STAGED) -> Plan:
    old_path, new_path = live / "commercial.html", stage / "commercial.html"
    if (old_path.is_symlink() or new_path.is_symlink()
        or not old_path.is_file() or not new_path.is_file()):
        raise ValueError("UNSAFE_OR_MISSING_COMMERCIAL_HTML")
    old, new = old_path.read_bytes(), new_path.read_bytes()
    if digest(old) != OLD_SHA:
        raise ValueError("CONCURRENT_LIVE_COMMERCIAL_PAGE_CHANGED")
    if digest(new) != NEW_SHA:
        raise ValueError("STAGED_FIRST_PAINT_PAGE_CHANGED")
    a, b = Visible(), Visible()
    a.feed(old.decode("utf-8"))
    b.feed(new.decode("utf-8"))
    if len(a.strings) != 112 or len(b.strings) != 122:
        raise ValueError("EXISTING_SITE_COPY_OR_ADDITIONS_DRIFT")
    # Original commercial content preserved in order; only newly supplied
    # first-paint brokerage section may add visible copy.
    cursor = iter(b.strings)
    if not all(any(x == y for y in cursor) for x in a.strings):
        raise ValueError("COMMERCIAL_VISIBLE_CONTENT_CHANGED")
    if any(sum(x == y for y in b.strings) != 1 for x in REQUIRED):
        raise ValueError("PREMIUM_TWO_FIRST_PAINT_LABELS_NOT_PRESENT")
    if any(x in old.decode("utf-8") for x in REQUIRED):
        raise ValueError("PREMIUM_FIRST_PAINT_ALREADY_LIVE")
    for x in REQUIRED:
        if new.decode("utf-8").find(x) < 0:
            raise ValueError("PREMIUM_FIRST_PAINT_MISSING")
    if new.find(b"Agency Intelligence") > new.find(b"Founder-approved starting prices"):
        raise ValueError("PREMIUM_SECTION_NOT_ABOVE_ORIGINAL_OFFERS")
    scripts = [x for x in b.scripts
               if x.startswith("/_next/static/chunks/app/commercial/page-")
               and x.endswith(".js")]
    if len(scripts) != 1:
        raise ValueError("PREMIUM_JS_BUNDLE_AMBIGUOUS")
    page_js = stage / scripts[0].lstrip("/")
    if (not page_js.is_file() or page_js.is_symlink() or
        PATH not in page_js.read_bytes() or
        b"Request an intelligence scope" not in page_js.read_bytes()):
        raise ValueError("PREMIUM_ENQUIRY_NOT_IN_PAGE_JS")
    for url in b.scripts:
        if not url.startswith("/_next/static/"):
            continue
        path = stage / url.lstrip("/")
        if path.is_symlink() or not path.is_file():
            raise ValueError("REFERENCED_STAGED_SCRIPT_MISSING")
    staged_static, live_static = stage / "_next/static", live / "_next/static"
    if not staged_static.is_dir() or not live_static.is_dir():
        raise ValueError("STATIC_ASSET_ROOT_MISSING")
    added = []
    for source in staged_static.rglob("*"):
        if source.is_symlink():
            raise ValueError("STAGED_SYMLINK_REFUSED")
        if not source.is_file():
            continue
        relative = source.relative_to(staged_static)
        if ".." in relative.parts:
            raise ValueError("BAD_STATIC_ASSET_PATH")
        target = live_static / relative
        if target.exists() or target.is_symlink():
            if (target.is_symlink() or not target.is_file() or
                    target.read_bytes() != source.read_bytes()):
                raise ValueError("EXISTING_SHARED_ASSET_CHANGED")
        else:
            added.append(relative)
    if (len(added) != ADDED_COUNT or
        sum((staged_static / x).stat().st_size for x in added) != ADDED_TOTAL_BYTES):
        raise ValueError("STATIC_ASSET_DELTA_NOT_REVIEWED")
    return Plan(old, new, tuple(sorted(added)), scripts[0])

def atomic_write(path: Path, content: bytes, *, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".brokerage-first-paint-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def publish(plan: Plan, *, live: Path = LIVE, stage: Path = STAGED,
            receipts: Path = RECEIPTS) -> dict:
    # Exact second baseline check before any side effects.
    if digest((live / "commercial.html").read_bytes()) != OLD_SHA:
        raise ValueError("LIVE_CHANGED_BEFORE_APPLY")
    receipts.mkdir(parents=True, exist_ok=True, mode=0o700)
    rollback = receipts / f"commercial-first-paint-rollback-{OLD_SHA[:16]}.html"
    if rollback.exists():
        if rollback.read_bytes() != plan.old or rollback.is_symlink():
            raise ValueError("ROLLBACK_SNAPSHOT_CONFLICT")
    else:
        atomic_write(rollback, plan.old, mode=0o600)
    static_live, static_new = live / "_next/static", stage / "_next/static"
    for rel in plan.added:
        target, source = static_live / rel, static_new / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise ValueError("NEW_ASSET_APPEARED_AFTER_PREFLIGHT")
        atomic_write(target, source.read_bytes(), mode=0o644)
    if digest((live / "commercial.html").read_bytes()) != OLD_SHA:
        raise ValueError("LIVE_CHANGED_WHILE_STAGING_STATIC")
    atomic_write(live / "commercial.html", plan.new, mode=0o644)
    if digest((live / "commercial.html").read_bytes()) != NEW_SHA:
        atomic_write(live / "commercial.html", plan.old, mode=0o644)
        raise ValueError("POST_SWAP_DIGEST_FAILED_ROLLBACK")
    return {
        "status": "BROKERAGE_CURRENT_FIRST_PAINT_PAGE_PUBLISHED",
        "old_sha256": OLD_SHA, "new_sha256": NEW_SHA,
        "new_static_assets": len(plan.added),
        "rollback_file": str(rollback),
        "other_pages_mutated": False, "services_restarted": False,
        "database_writes": False, "outbound_sent": False,
        "payments_changed": False, "crm_mutation": False,
        "first_real_enquiry_verified": False,
    }

def verify_live(live: Path = LIVE, stage: Path = STAGED) -> dict:
    page = live / "commercial.html"
    if page.is_symlink() or not page.is_file() or digest(page.read_bytes()) != NEW_SHA:
        raise ValueError("FIRST_PAINT_LIVE_HTML_NOT_EXACT")
    if digest((stage / "commercial.html").read_bytes()) != NEW_SHA:
        raise ValueError("FIRST_PAINT_SOURCE_DRIFT")
    parser = Visible()
    parser.feed(page.read_text(encoding="utf-8"))
    if (len(parser.strings) != 122
        or any(parser.strings.count(s) != 1 for s in REQUIRED)
        or parser.strings.index("Agency Intelligence")
           > parser.strings.index("Founder-approved starting prices")):
        raise ValueError("FIRST_PAINT_HTML_VISIBLE_CONTENT_DRIFT")
    matched = 0
    for source in (stage / "_next/static").rglob("*"):
        if source.is_symlink():
            raise ValueError("SYMLINK_STAGED_ASSET")
        if not source.is_file():
            continue
        relative = source.relative_to(stage / "_next/static")
        current = live / "_next/static" / relative
        if (current.is_symlink() or not current.is_file()
            or current.read_bytes() != source.read_bytes()):
            raise ValueError("LIVE_ASSET_DIFFERENT_OR_MISSING")
        matched += 1
    if matched != 41:
        raise ValueError("UNEXPECTED_STAGED_ASSET_COUNT")
    return {"status": "BROKERAGE_CURRENT_FIRST_PAINT_LIVE_BYTES_VERIFIED",
            "new_html_sha256": NEW_SHA, "matched_static_assets": matched,
            "two_services_visible_in_initial_html": True,
            "payment_or_sales_verification": False,
            "no_customer_post": True, "site_mutation": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--apply-founder-approved-first-paint", action="store_true")
    group.add_argument("--verify-live", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_live:
            print(json.dumps(verify_live(), sort_keys=True))
            return 0
        plan = inspect()
        print("BROKERAGE_VISIBLE_FIRST_PAINT_CONTENT_AND_STATIC_PREFLIGHT_PASS")
        print("SAFE_NEW_STATIC_ASSETS", len(plan.added))
        if args.preflight:
            return 0
        print(json.dumps(publish(plan), sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError) as e:
        print("BROKERAGE_VISIBLE_FIRST_PAINT_HOLD=" + str(e))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
