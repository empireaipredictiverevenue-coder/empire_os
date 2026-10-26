"""Read-only verification of private 662-file website archive.

Never treats this user-owned test archive as ASTRA's root-protected rollback.
"""
from hashlib import sha256
from pathlib import Path, PurePosixPath
import tarfile

from empire_os.earned_media_saas_rebased_release import read_index, index_digest, ReleaseHeld


def inspect_private_backup(archive: Path, live: Path) -> dict:
    if (archive.is_symlink() or not archive.is_file()
            or archive.stat().st_size > 120_000_000):
        raise ReleaseHeld("UNSAFE_PRIVATE_BACKUP_ARCHIVE")
    before = read_index(live)
    if len(before) != 662:
        raise ReleaseHeld("SOURCE_SITE_BASELINE_NOT_662")
    seen: dict[str, str] = {}
    total = 0
    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar:
            if member.isdir():
                continue
            path = PurePosixPath(member.name)
            if (not member.isfile() or
                    not member.name.startswith("./") or
                    path.is_absolute() or ".." in path.parts or
                    member.size > 20_000_000):
                raise ReleaseHeld("PRIVATE_ARCHIVE_MEMBER_NOT_REGULAR_SAFE_FILE")
            name = member.name[2:]
            if (name not in before or name in seen or
                    not name or name.startswith(".")):
                raise ReleaseHeld("PRIVATE_ARCHIVE_UNEXPECTED_OR_DUPLICATE_MEMBER")
            total += member.size
            if total > 120_000_000:
                raise ReleaseHeld("PRIVATE_ARCHIVE_UNBOUNDED_CONTENT")
            reader = tar.extractfile(member)
            if reader is None:
                raise ReleaseHeld("PRIVATE_ARCHIVE_FILE_NOT_READABLE")
            digest = sha256(reader.read()).hexdigest()
            if digest != before[name]:
                raise ReleaseHeld("PRIVATE_ARCHIVE_BYTE_HASH_DRIFT")
            seen[name] = digest
    if seen != before:
        raise ReleaseHeld("PRIVATE_ARCHIVE_MISSING_BASELINE_FILE")
    if read_index(live) != before:
        raise ReleaseHeld("ORIGINAL_SITE_CHANGED_DURING_BACKUP_VERIFICATION")
    return {
        "schema_version": "empire.website.earned_media_saas_private_backup_audit.v1",
        "status": "PRIVATE_662_ARCHIVE_MEMBER_HASHES_EXACT",
        "archive_sha256": sha256(archive.read_bytes()).hexdigest(),
        "live_662_inventory_sha256": index_digest(before),
        "verified_regular_files": len(seen),
        "archive_total_uncompressed_bytes": total,
        "private_user_backup_only": True,
        "independent_root_protected_backup_verified": False,
        "publication_performed": False,
        "payments_or_outbound_executed": False,
    }
