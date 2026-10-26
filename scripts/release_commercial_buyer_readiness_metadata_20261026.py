"""One-file original commercial SEO metadata upgrade, no gateway restart.

Requires an exact old head contract. Backs up bytes before an atomic switch;
the only rewritten file is the existing static /commercial HTML.
Does not modify offers, proposal fields, JS assets, indexation, or payments.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen
import json
import os
import tempfile

ROOT = Path("/srv/empire_os/apps/empire-public-site/out")
PAGE = ROOT / "commercial.html"
BACKUP_ROOT = Path("/home/ubuntu/empire_releases/commercial_buyer_readiness_meta_20261026")
BACKUP = BACKUP_ROOT / "commercial.before.html"
OLD_TITLE = "AI Consultancy &amp; Revenue Intelligence | Empire AI"
NEW_TITLE = "Buyer Readiness &amp; Revenue Intelligence | Empire AI"
OLD_DESC = "Explore founder-led AI consultancy, competitor search intelligence, digital workforce and predictive revenue solutions. Request a scoped business enquiry; no payment required."
NEW_DESC = "Learn how to evaluate buyer readiness across your total addressable market, trace revenue leaks and request a scoped Empire AI business assessment. No payment required."


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def checked_candidate(original: bytes) -> bytes:
    raw = original.decode("utf8")
    if raw.count(OLD_TITLE) != 3 or raw.count(OLD_DESC) != 6:
        raise ValueError("RELEASE_BASELINE_METADATA_MISMATCH")
    replaced = raw.replace(OLD_TITLE, NEW_TITLE).replace(OLD_DESC, NEW_DESC)
    if replaced.count(OLD_TITLE) or replaced.count(OLD_DESC):
        raise ValueError("OLD_METADATA_REMAINS")
    if replaced.count(NEW_TITLE) != 3 or replaced.count(NEW_DESC) != 6:
        raise ValueError("EXPECTED_METADATA_OCCURRENCE_MISMATCH")
    # Assert source-to-output edit stays strictly metadata-only.
    restored = replaced.replace(NEW_TITLE, OLD_TITLE).replace(NEW_DESC, OLD_DESC)
    if restored != raw:
        raise ValueError("OUTSIDE_METADATA_CHANGED")
    return replaced.encode("utf8")


def atomic_bytes(destination: Path, content: bytes) -> None:
    fd, filename = tempfile.mkstemp(prefix=".buyer-meta-", dir=str(destination.parent))
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(filename, destination)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def run() -> dict:
    if PAGE.is_symlink() or not PAGE.is_file() or PAGE.stat().st_size > 300_000:
        raise ValueError("PUBLIC_COMMERCIAL_HTML_UNSAFE")
    old = PAGE.read_bytes()
    if NEW_TITLE.encode() in old and NEW_DESC.encode() in old:
        return {"status": "ALREADY_LIVE", "sha256": digest(old), "outbound": False}
    updated = checked_candidate(old)
    if BACKUP_ROOT.is_symlink() or BACKUP.is_symlink():
        raise ValueError("UNSAFE_BACKUP_PATH")
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    if BACKUP_ROOT.stat().st_mode & 0o077 or BACKUP.exists():
        raise ValueError("BACKUP_DIRECTORY_UNSAFE_OR_EXISTING")
    fd = os.open(BACKUP, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as backup:
        backup.write(old)
        backup.flush()
        os.fsync(backup.fileno())
    try:
        atomic_bytes(PAGE, updated)
        req = Request("https://empire-ai.co.uk/commercial", headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/131 Safari/537.36", "Cache-Control": "no-cache",
        }, method="GET")
        with urlopen(req, timeout=10) as response:
            body = response.read(400_000)
            if response.status != 200 or NEW_TITLE.encode() not in body or NEW_DESC.encode() not in body:
                raise ValueError("PUBLIC_READBACK_MISMATCH")
        if PAGE.read_bytes() != updated:
            raise ValueError("LOCAL_READBACK_MISMATCH")
    except Exception:
        atomic_bytes(PAGE, old)
        raise
    return {
        "status": "ONE_COMMERCIAL_PAGE_METADATA_PUBLISHED",
        "url": "https://empire-ai.co.uk/commercial",
        "before_sha256": digest(old), "after_sha256": digest(updated),
        "backup": str(BACKUP), "public_http_verified": True,
        "changed_page_count": 1, "form_changed": False, "outbound": False,
        "database_writes": False, "money_moved": False, "gateway_restarted": False,
    }


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "HELD_OR_ROLLED_BACK", "reason": str(exc),
                          "outbound": False, "database_writes": False}, sort_keys=True))
        raise SystemExit(2) from None
