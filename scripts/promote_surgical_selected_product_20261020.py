"""Guarded byte-preserving deployment for existing LIVE static /buy, /commercial.

Adds one self-origin JS script to the existing pages without replacing other
owners' premium-brokerage HTML, checkout JS, styles or content. Backups and
rollback are digest checked. No service restart, customer POST or revenue action.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
STAGE = Path("/home/ubuntu/empire_staging/agency_surgical_live_pages_20261020")
BACKUP = Path("/home/ubuntu/empire_releases/agency_selected_product_public_20261020")
ASSET = Path("_next/static/agency/selected-product-bridge-20261020.js")
PAGES = ("buy.html", "commercial.html")
TAG = '<script defer src="/_next/static/agency/selected-product-bridge-20261020.js"></script>'
SCHEMA = "empire.public_web.selected_product_surgical_release.v1"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic(target: Path, data: bytes) -> None:
    if target.is_symlink() or not target.parent.is_dir():
        raise RuntimeError("UNSAFE_DESTINATION")
    descriptor, temporary = tempfile.mkstemp(prefix=".agency-update-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source() -> dict:
    if not LIVE.is_dir() or LIVE.is_symlink() or not STAGE.is_dir():
        raise RuntimeError("RELEASE_ROOT_UNAVAILABLE")
    if (LIVE / ASSET).exists() or (LIVE / ASSET).is_symlink():
        raise RuntimeError("ASSET_ALREADY_OWNED")
    if BACKUP.exists() or BACKUP.is_symlink():
        raise RuntimeError("BACKUP_ALREADY_EXISTS_NO_OVERWRITE")
    plan = {}
    for name in PAGES:
        live = LIVE / name
        stage = STAGE / name
        if live.is_symlink() or stage.is_symlink():
            raise RuntimeError("UNSAFE_PAGE_SYMLINK")
        before = live.read_bytes()
        after = stage.read_bytes()
        marker = TAG.encode()
        if before.count(b"</body>") != 1 or before.count(marker) != 0:
            raise RuntimeError("LIVE_HTML_NOT_ELIGIBLE_FOR_ADDITIVE_SCRIPT")
        if after != before.replace(b"</body>", marker + b"</body>"):
            raise RuntimeError("STAGED_PAGE_NOT_EXACT_BYTE_PRESERVING_PATCH")
        plan[name] = (before, after)
    script = (STAGE / ASSET).read_bytes()
    if not script or len(script) > 10_000:
        raise RuntimeError("BRIDGE_ASSET_INVALID")
    return {"pages":plan, "script":script}


def _backup(data: dict) -> dict:
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=False)
    original = BACKUP / "original"
    original.mkdir(mode=0o700)
    for name, (before, _) in data["pages"].items():
        (original / name).write_bytes(before)
    manifest = {
        "schema": SCHEMA,
        "mode": "PUBLIC_STATIC_ADDITIVE_EXACT_PAGE_PATCH",
        "pages": {name: {"before_sha256": digest(before), "after_sha256": digest(after)}
                  for name, (before, after) in data["pages"].items()},
        "asset_sha256": digest(data["script"]),
        "release_applied": False,
        "no_service_restart": True,
        "no_outbound_or_payment": True,
    }
    (BACKUP / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    return manifest


def apply() -> dict:
    data = source()
    for name, (before, _) in data["pages"].items():
        if (LIVE / name).read_bytes() != before:
            raise RuntimeError("LIVE_PAGE_CHANGED_DURING_PREFLIGHT")
    _backup(data)
    asset_dir = (LIVE / ASSET).parent
    if asset_dir.is_symlink():
        raise RuntimeError("ASSET_PARENT_SYMLINK")
    asset_dir.mkdir(parents=True, exist_ok=True)
    if asset_dir.is_symlink():
        raise RuntimeError("ASSET_PARENT_UNSAFE")
    changed = []
    try:
        asset = LIVE / ASSET
        atomic(asset, data["script"])
        changed.append(asset)
        for name in PAGES:
            before, after = data["pages"][name]
            page = LIVE / name
            if page.read_bytes() != before:
                raise RuntimeError("CONCURRENT_LIVE_PAGE_CHANGE_ABORT")
            atomic(page, after)
            changed.append(page)
        for name in PAGES:
            if digest((LIVE / name).read_bytes()) != digest(data["pages"][name][1]):
                raise RuntimeError("POST_PROMOTION_DIGEST_MISMATCH")
        if digest((LIVE / ASSET).read_bytes()) != digest(data["script"]):
            raise RuntimeError("POST_PROMOTION_ASSET_MISMATCH")
        report = {"status": "PUBLIC_STATIC_SELECTED_PRODUCT_PATCH_APPLIED_VERIFY_BROWSER",
                  "page_before_sha256": {n:digest(v[0]) for n,v in data["pages"].items()},
                  "page_after_sha256": {n:digest(v[1]) for n,v in data["pages"].items()},
                  "asset_sha256": digest(data["script"]),
                  "no_service_restart": True, "database_writes": False,
                  "orders_created": False, "outbound_sent": False}
        (BACKUP / "applied.json").write_text(json.dumps(report, sort_keys=True, indent=2)+"\n")
        return report
    except Exception:
        for name in PAGES:
            page = LIVE / name
            before, after = data["pages"][name]
            if page.exists() and page.read_bytes() == after:
                atomic(page, before)
        asset = LIVE / ASSET
        if asset.is_file() and digest(asset.read_bytes()) == digest(data["script"]):
            asset.unlink()
        raise


def rollback() -> dict:
    meta = BACKUP / "manifest.json"
    if meta.is_symlink() or not meta.is_file():
        raise RuntimeError("RELEASE_MANIFEST_NOT_PRESENT")
    m = json.loads(meta.read_text())
    if m.get("schema") != SCHEMA or set(m.get("pages", {})) != set(PAGES):
        raise RuntimeError("RELEASE_MANIFEST_INVALID")
    originals = {}
    for name in PAGES:
        target = LIVE / name
        current = target.read_bytes()
        before = (BACKUP / "original" / name).read_bytes()
        if digest(before) != m["pages"][name]["before_sha256"]:
            raise RuntimeError("BACKUP_DIGEST_MISMATCH")
        if digest(current) not in (
            m["pages"][name]["before_sha256"],
            m["pages"][name]["after_sha256"],
        ):
            raise RuntimeError("ANOTHER_OWNER_MODIFIED_PAGE_NO_ROLLBACK")
        originals[name] = before
    asset = LIVE / ASSET
    if asset.exists() and digest(asset.read_bytes()) != m["asset_sha256"]:
        raise RuntimeError("ANOTHER_OWNER_MODIFIED_ASSET_NO_ROLLBACK")
    for name, original in originals.items():
        if (LIVE / name).read_bytes() != original:
            atomic(LIVE / name, original)
    if asset.exists():
        asset.unlink()
    return {"status":"PUBLIC_STATIC_SELECTED_PRODUCT_RESTORED_PRIOR_BYTES",
            "no_service_restart":True,"database_writes":False}


def verify() -> dict:
    meta = BACKUP / "manifest.json"
    if not meta.is_file() or meta.is_symlink():
        raise RuntimeError("RELEASE_MANIFEST_MISSING")
    m = json.loads(meta.read_text())
    if m.get("schema") != SCHEMA or set(m.get("pages", {})) != set(PAGES):
        raise RuntimeError("RELEASE_MANIFEST_UNEXPECTED")
    original_bytes_preserved = True
    for name in PAGES:
        original = (BACKUP / "original" / name).read_bytes()
        published = (LIVE / name).read_bytes()
        original_bytes_preserved &= digest(original) == m["pages"][name]["before_sha256"]
        original_bytes_preserved &= published == original.replace(
            b"</body>", TAG.encode() + b"</body>"
        )
        original_bytes_preserved &= digest(published) == m["pages"][name]["after_sha256"]
    script = LIVE / ASSET
    integrity = script.is_file() and not script.is_symlink()
    integrity &= digest(script.read_bytes()) == m["asset_sha256"] if integrity else False
    if not original_bytes_preserved or not integrity:
        raise RuntimeError("PUBLISHED_ARTIFACT_DRIFT_OR_OWNER_CHANGE")
    return {
        "status": "PUBLISHED_STATIC_SELECTED_PRODUCT_DIGESTS_VERIFIED",
        "pages": list(PAGES), "single_script_per_page": True,
        "original_live_bytes_preserved_except_additive_tag": True,
        "published_script_sha256": m["asset_sha256"],
        "public_browser_test_independent": True,
        "outbound_sent": False, "database_writes": False,
        "checkout_created": False, "execution_authority": "none",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = p.parse_args()
    try:
        result = apply() if args.apply else rollback() if args.rollback else verify()
    except Exception as exc:
        print(json.dumps({"status":"RELEASE_HELD","reason":str(exc)}))
        return 3
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
