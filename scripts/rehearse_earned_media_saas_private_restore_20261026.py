"""Full-size private website forward-and-recovery rehearsal. Not a publisher."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import tarfile

from empire_os.earned_media_saas_release_scope import check_scope
from empire_os.earned_media_saas_rebased_release import read_index, index_digest
from empire_os.earned_media_saas_private_backup_audit import inspect_private_backup

LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
PRIVATE = Path("/home/ubuntu/empire_releases/earned_media_saas_union_20261026")
CANDIDATE = PRIVATE / "rebased_candidate"
SCRATCH = PRIVATE / "private_backup_rehearsal"
ARCHIVE = SCRATCH / "pre_release_662_20261026.tar.gz"


def rehearse() -> dict:
    # All writes below are confined to TemporaryDirectory within PRIVATE.
    if (SCRATCH.is_symlink() or not SCRATCH.is_dir()
            or LIVE.is_symlink() or CANDIDATE.is_symlink()):
        raise ValueError("UNSAFE_PREVIEW_REHEARSAL_LOCATION")
    scope = check_scope(LIVE, CANDIDATE)
    archive = inspect_private_backup(ARCHIVE, LIVE)
    before = read_index(LIVE)
    after = read_index(CANDIDATE)
    changed = scope["two_paired_route_files"]
    added = scope["eight_immutable_assets"]
    with TemporaryDirectory(prefix="empire-saas-670-rehearsal-", dir=SCRATCH) as dirname:
        sandbox = Path(dirname) / "disposable-copy"
        shutil.copytree(LIVE, sandbox, symlinks=False)
        if read_index(sandbox) != before:
            raise ValueError("PRIVATE_BASELINE_COPY_MISMATCH")
        for rel in changed + added:
            dst = sandbox / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CANDIDATE / rel, dst)
        if read_index(sandbox) != after:
            raise ValueError("PRIVATE_FORWARD_COPY_NOT_EXACT_670")
        # Simulated post-release test failure: recover solely in sandbox.
        for rel in added:
            (sandbox / rel).unlink()
        with tarfile.open(ARCHIVE, "r:gz") as tar:
            for rel in changed:
                member = tar.getmember("./" + rel)
                stream = tar.extractfile(member)
                if stream is None:
                    raise ValueError("PRIVATE_ARCHIVE_RESTORE_MEMBER_UNREADABLE")
                with stream:
                    (sandbox / rel).write_bytes(stream.read())
        if read_index(sandbox) != before:
            raise ValueError("PRIVATE_BACKUP_RECOVERY_NOT_EXACT_662")
    if read_index(LIVE) != before or read_index(CANDIDATE) != after:
        raise ValueError("ORIGINAL_SOURCE_CHANGED_DURING_PRIVATE_REHEARSAL")
    return {
        "schema_version": "empire.website.earned_media_saas_full_private_rehearsal.v1",
        "status": "PASS_FULL_SIZE_PRIVATE_662_TO_670_AND_RECOVERY_TO_662",
        "original_file_count": 662,
        "candidate_file_count": 670,
        "recovery_file_count": 662,
        "original_unchanged_files": 660,
        "release_route_files": changed,
        "new_assets": added,
        "private_archive_sha256": archive["archive_sha256"],
        "original_inventory_sha256": index_digest(before),
        "candidate_inventory_sha256": index_digest(after),
        "private_archive_verified": True,
        "real_production_publisher_exercised": False,
        "protected_root_backup_verified": False,
        "astra_owner_authorized": False,
        "founder_new_payload_authorized": False,
        "live_files_modified": False,
        "messages_or_payments_executed": False,
    }


def main() -> None:
    print(json.dumps(rehearse(), sort_keys=True))


if __name__ == "__main__":
    main()
