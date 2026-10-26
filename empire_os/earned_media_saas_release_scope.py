"""Pure read-only release scope contract for the 662-to-670 candidate."""
from pathlib import Path
from empire_os.earned_media_saas_rebased_release import (
    read_index,index_digest,REPLACE,LIVE_DRIFT,ReleaseHeld,
)

def check_scope(live:Path, candidate:Path)->dict:
    before=read_index(live)
    after=read_index(candidate)
    changed={name for name in before if before[name]!=after.get(name)}
    added=set(after)-set(before)
    if len(before)!=662 or len(after)!=670:
        raise ReleaseHeld("RELEASE_FILE_COUNTS_CHANGED")
    if changed != REPLACE or len(added)!=8:
        raise ReleaseHeld("RELEASE_DIFFERENCE_NOT_TWO_ROUTES_EIGHT_ASSETS")
    if not all(name.startswith("_next/static/") for name in added):
        raise ReleaseHeld("EXTRA_NON_STATIC_FILE_PROPOSED")
    if any(before[k]!=after[k] for k in LIVE_DRIFT):
        raise ReleaseHeld("NEWER_ORIGINAL_OWNER_PAGE_WOULD_CHANGE")
    if set(before)-set(after):
        raise ReleaseHeld("PUBLISHED_FILE_WOULD_BE_REMOVED")
    return {
        "original_files":len(before),
        "candidate_files":len(after),
        "two_paired_route_files":sorted(changed),
        "eight_immutable_assets":sorted(added),
        "other_existing_files_byte_identical":660,
        "all_five_newer_owner_pages_preserved":True,
        "live_index_sha256":index_digest(before),
        "candidate_index_sha256":index_digest(after),
        "publication_performed":False,
        "root_backup_verified":False,
        "owner_approved":False,
    }
