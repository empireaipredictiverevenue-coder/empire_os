"""Private-only atomic 2-route/8-asset release transaction, for ASTRA review.

This is NOT a privileged production publisher. Public site root and original
candidate are never writable transaction destinations. No owner signoff,
root-controlled receipt, production backup or payment capability here.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Callable

from empire_os.earned_media_saas_rebased_release import read_index, index_digest
from empire_os.earned_media_saas700_reconciliation import (
    LIVE, DESTINATION, LIVE_700_PIN,
)

ROUTES = frozenset(("predictive-revenue.html", "predictive-revenue.txt"))
ASSET_PREFIX = "_next/static/"
CANDIDATE_PIN = "62b62b184d5597ffc806a825723c4638f2953702c823561233d30058e398dab2"


class PrivateTrialHeld(ValueError):
    pass


def release_scope(before: dict[str, str], after: dict[str, str],
                  *, source_pin: str, candidate_pin: str,
                  original_count: int = 700,
                  new_count: int = 708) -> list[str]:
    if (source_pin != LIVE_700_PIN or candidate_pin != CANDIDATE_PIN
            or original_count != 700 or new_count != 708):
        raise PrivateTrialHeld("EXACT_708_REVIEW_PINS_ONLY")
    if (len(before) != original_count or len(after) != new_count
            or index_digest(before) != source_pin
            or index_digest(after) != candidate_pin):
        raise PrivateTrialHeld("PINNED_SOURCE_OR_CANDIDATE_CHANGED")
    changed = {name for name in before if after.get(name) != before[name]}
    if changed != ROUTES:
        raise PrivateTrialHeld("EXACT_TWO_EXISTING_ROUTES_REQUIRED")
    if set(before) - set(after):
        raise PrivateTrialHeld("EXISTING_SOURCE_FILES_REMOVED")
    additions = sorted(set(after) - set(before))
    if (len(additions) != 8 or
            any(not name.startswith(ASSET_PREFIX) for name in additions)
            or any(".." in Path(name).parts for name in additions)):
        raise PrivateTrialHeld("EIGHT_NEW_IMMUTABLE_ASSETS_REQUIRED")
    return additions


def _replace_exact(path: Path, content: bytes, mode: int) -> None:
    """Atomic replacement inside the disposable private test tree."""
    fd, temp = tempfile.mkstemp(prefix=".empire-saas708-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fchmod(out.fileno(), mode)
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def run_private_trial(
    private_live_copy: Path,
    private_candidate: Path,
    *,
    source_pin: str,
    candidate_pin: str,
    original_count: int = 700,
    new_count: int = 708,
    fail_at: str | None = None,
    post_apply: Callable[[], None] | None = None,
) -> dict:
    """Reversible transaction on an existing disposable private copy ONLY.

    Always raises for the actual public site; refuses a destination within
    the public site or candidate. Must be invoked by test operator explicitly.
    Rollback refuses to overwrite newly diverged files.
    """
    destination = private_live_copy.resolve(strict=True)
    stage = private_candidate.resolve(strict=True)
    protected = (LIVE.resolve(strict=True), DESTINATION.resolve(strict=True))
    for forbidden in protected:
        if destination == forbidden or forbidden in destination.parents:
            raise PrivateTrialHeld("LIVE_OR_STAGED_SOURCE_MAY_NOT_BE_TRANSACTION_DESTINATION")
    # Test implementation cannot act on any real deployment or release folder.
    scratch = Path(tempfile.gettempdir()).resolve(strict=True)
    if scratch not in destination.parents:
        raise PrivateTrialHeld("DISPOSABLE_TEMP_DIRECTORY_REQUIRED")
    if (destination == stage or stage in destination.parents or
            destination in stage.parents):
        raise PrivateTrialHeld("STAGE_AND_DISPOSABLE_DESTINATION_OVERLAP")
    if private_live_copy.is_symlink() or private_candidate.is_symlink():
        raise PrivateTrialHeld("ROOT_SYMLINK_UNTRUSTED")
    before = read_index(destination)
    after = read_index(stage)
    additions = release_scope(
        before, after, source_pin=source_pin, candidate_pin=candidate_pin,
        original_count=original_count, new_count=new_count,
    )
    snapshots: dict[str, tuple[bytes, int]] = {}
    for route in sorted(ROUTES):
        path = destination / route
        snapshots[route] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
    # No content publication is possible without full scope and hashes passing.
    if fail_at == "before":
        raise PrivateTrialHeld("INJECTED_FAILURE_BEFORE_WRITE")
    added: list[str] = []
    swapped: list[str] = []
    try:
        for rel in additions:
            src = stage / rel
            dst = destination / rel
            if src.is_symlink() or not src.is_file() or dst.exists() or dst.is_symlink():
                raise PrivateTrialHeld("IMMUTABLE_ASSET_COLLISION")
            dst.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
            added.append(rel)
            with os.fdopen(fd, "wb") as out:
                out.write(src.read_bytes())
                out.flush()
                os.fsync(out.fileno())
            if sha256(dst.read_bytes()).hexdigest() != after[rel]:
                raise PrivateTrialHeld("IMMUTABLE_ASSET_HASH_CHANGED")
        if fail_at == "after_assets":
            raise PrivateTrialHeld("INJECTED_FAILURE_AFTER_ASSETS")
        for n, rel in enumerate(sorted(ROUTES), 1):
            src = stage / rel
            dst = destination / rel
            if (sha256(src.read_bytes()).hexdigest() != after[rel] or
                    sha256(dst.read_bytes()).hexdigest() != before[rel]):
                raise PrivateTrialHeld("ROUTE_BYTES_CHANGED_DURING_REPLACEMENT")
            _replace_exact(dst, src.read_bytes(), snapshots[rel][1])
            swapped.append(rel)
            if sha256(dst.read_bytes()).hexdigest() != after[rel]:
                raise PrivateTrialHeld("ROUTE_REPLACED_BYTES_MISMATCH")
            if fail_at == "after_first_route" and n == 1:
                raise PrivateTrialHeld("INJECTED_FAILURE_AFTER_ONE_ROUTE")
        if read_index(destination) != after:
            raise PrivateTrialHeld("POST_APPLY_708_INVENTORY_NOT_EXACT")
        if fail_at == "after_all":
            raise PrivateTrialHeld("INJECTED_FAILURE_AFTER_FULL_APPLY")
        if post_apply is not None:
            post_apply()
        return {
            "schema_version": "empire.website.saas708_private_atomic_trial.v1",
            "status": "EXACT_EIGHT_ASSETS_TWO_ROUTES_PRIVATE_COPY_APPLIED",
            "changed_existing_routes": len(swapped),
            "added_immutable_assets": len(added),
            "result_inventory_sha256": index_digest(read_index(destination)),
            "production_site_modified": False,
            "root_publisher_exercised": False,
            "original_owner_approval_supplied": False,
        }
    except BaseException:
        conflicts = []
        for rel in reversed(swapped):
            target = destination / rel
            if (target.is_symlink() or not target.is_file()
                    or sha256(target.read_bytes()).hexdigest() != after[rel]):
                conflicts.append(rel)
                continue
            content, mode = snapshots[rel]
            _replace_exact(target, content, mode)
        for rel in reversed(added):
            target = destination / rel
            if (target.is_symlink() or not target.is_file()
                    or sha256(target.read_bytes()).hexdigest() != after[rel]):
                conflicts.append(rel)
                continue
            target.unlink()
        if conflicts or read_index(destination) != before:
            raise PrivateTrialHeld("CONCURRENT_CHANGE_ROLLBACK_REQUIRES_OWNER")
        raise


def private_rehearsal_copy(destination: Path) -> tuple[Path, dict[str, str]]:
    """Copy current 700 live files only to a newly created disposable directory."""
    scratch = Path(tempfile.gettempdir()).resolve(strict=True)
    if scratch not in destination.resolve().parents:
        raise PrivateTrialHeld("DISPOSABLE_TEMP_DIRECTORY_REQUIRED")
    if destination.exists() or destination.is_symlink():
        raise PrivateTrialHeld("TRIAL_DESTINATION_ALREADY_EXISTS")
    if destination.resolve() == LIVE.resolve():
        raise PrivateTrialHeld("CANNOT_COPY_ONTO_PRODUCTION")
    source = read_index(LIVE)
    if len(source) != 700 or index_digest(source) != LIVE_700_PIN:
        raise PrivateTrialHeld("CURRENT_PRODUCTION_700_BASELINE_DRIFT")
    shutil.copytree(LIVE, destination, symlinks=False)
    if read_index(destination) != source:
        raise PrivateTrialHeld("PRIVATE_SOURCE_COPY_INCOMPLETE")
    return destination, source
