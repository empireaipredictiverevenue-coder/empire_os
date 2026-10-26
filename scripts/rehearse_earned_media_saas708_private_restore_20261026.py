"""Private 700 -> 708 -> 700 recovery test; never a production publisher."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import tarfile

from empire_os.earned_media_saas700_reconciliation import (
    LIVE,DESTINATION,verify,
)
from empire_os.earned_media_saas_rebased_release import read_index,index_digest
from empire_os.earned_media_saas_private_backup_audit import inspect_private_backup

ARCHIVE = Path(
    "/home/ubuntu/empire_releases/earned_media_saas_union_20261026/"
    "private_700_baseline_backup/live_700_pre_708.tar.gz"
)
SCRATCH_ROOT = ARCHIVE.parent


def rehearse() -> dict:
    review = verify()
    before = read_index(LIVE)
    final = read_index(DESTINATION)
    backup = inspect_private_backup(ARCHIVE,LIVE,expected_count=700)
    if (len(before)!=700 or len(final)!=708
            or review["candidate_index_sha256"]!=index_digest(final)
            or backup["live_site_inventory_sha256"]!=index_digest(before)):
        raise ValueError("CURRENT_SOURCE_OR_BACKUP_NOT_EXACT")
    replace = review["replaced_existing_files"]
    added = sorted(set(final)-set(before))
    if len(added)!=8:
        raise ValueError("EXACT_EIGHT_NEW_ASSET_SCOPE_NOT_VERIFIED")
    if SCRATCH_ROOT.is_symlink() or not SCRATCH_ROOT.is_dir():
        raise ValueError("NO_PRIVATE_SCRATCH_ROOT")
    with TemporaryDirectory(prefix="empire-saas-708-private-",dir=SCRATCH_ROOT) as temp:
        copy=Path(temp)/"disposable-copy"
        shutil.copytree(LIVE,copy,symlinks=False)
        if read_index(copy)!=before:
            raise ValueError("INITIAL_PRIVATE_COPY_DIFFERS")
        for rel in replace+added:
            target=copy/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(DESTINATION/rel,target)
        if read_index(copy)!=final:
            raise ValueError("REBASED_708_PRIVATE_FORWARD_NOT_BYTE_EXACT")
        # Simulated failed post-publish check in disposable test tree ONLY.
        for rel in added:
            (copy/rel).unlink()
        with tarfile.open(ARCHIVE, "r:gz") as backup_file:
            for rel in replace:
                member=backup_file.getmember("./"+rel)
                stream=backup_file.extractfile(member)
                if stream is None:
                    raise ValueError("MISSING_RESTORE_MEMBER")
                with stream:
                    (copy/rel).write_bytes(stream.read())
        if read_index(copy)!=before:
            raise ValueError("PRIVATE_700_BASELINE_NOT_RECOVERED_EXACTLY")
    if read_index(LIVE)!=before or read_index(DESTINATION)!=final:
        raise ValueError("LIVE_OR_STAGED_SOURCE_CHANGED_DURING_TEST")
    return {
        "schema_version":"empire.website.earned_media_saas708_full_private_rehearsal.v1",
        "status":"PASS_PRIVATE_700_TO_708_AND_EXACT_700_RECOVERY",
        "original_file_count":700,
        "candidate_file_count":708,
        "restored_file_count":700,
        "unchanged_original_files":698,
        "replaced_route_files":replace,
        "new_immutable_assets":len(added),
        "original_site_index_sha256":index_digest(before),
        "private_candidate_index_sha256":index_digest(final),
        "private_backup_sha256":backup["archive_sha256"],
        "root_owned_production_backup_verified":False,
        "founder_new_708_payload_approved":False,
        "astra_owner_approval_verified":False,
        "production_publisher_executed":False,
        "production_site_modified":False,
        "real_buyer_enquiry_submitted":False,
        "actual_revenue_verified":False,
    }


if __name__ == "__main__":
    print(json.dumps(rehearse(),sort_keys=True))
