"""Release-owner handoff: exact private backup scope and recovery proof."""
from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import io
import tarfile

import pytest

from empire_os.earned_media_saas_release_scope import check_scope
from empire_os.earned_media_saas_rebased_release import ReleaseHeld, read_index
from empire_os.earned_media_saas_private_backup_audit import inspect_private_backup
from scripts.rehearse_earned_media_saas_private_restore_20261026 import (
    ARCHIVE,CANDIDATE,LIVE,rehearse,
)


def test_exact_rebased_scope_still_preserves_live_owner_edits():
    result = check_scope(LIVE, CANDIDATE)
    assert result["original_files"] == 662
    assert result["candidate_files"] == 670
    assert result["other_existing_files_byte_identical"] == 660
    assert result["all_five_newer_owner_pages_preserved"] is True
    assert len(result["eight_immutable_assets"]) == 8
    assert result["publication_performed"] is False


def test_backup_archive_has_every_source_file_with_matching_bytes():
    result = inspect_private_backup(ARCHIVE, LIVE)
    assert result["status"] == "PRIVATE_662_ARCHIVE_MEMBER_HASHES_EXACT"
    assert result["verified_regular_files"] == 662
    assert result["private_user_backup_only"] is True
    assert result["independent_root_protected_backup_verified"] is False


def test_full_size_disposable_forward_and_restore():
    original=read_index(LIVE)
    result=rehearse()
    assert result["status"] == (
        "PASS_FULL_SIZE_PRIVATE_662_TO_670_AND_RECOVERY_TO_662"
    )
    assert result["original_file_count"] == result["recovery_file_count"] == 662
    assert result["candidate_file_count"] == 670
    assert result["new_assets"] and len(result["new_assets"]) == 8
    assert result["live_files_modified"] is False
    assert result["real_production_publisher_exercised"] is False
    assert result["protected_root_backup_verified"] is False
    assert read_index(LIVE)==original


def test_fake_archive_with_wrong_hash_fails(tmp_path):
    archive=tmp_path/"broken.tar.gz"
    content=b"this is not a real website page"
    with tarfile.open(archive,"w:gz") as writer:
        info=tarfile.TarInfo("./predictive-revenue.html")
        info.size=len(content)
        writer.addfile(info,io.BytesIO(content))
    with pytest.raises(ReleaseHeld, match="PRIVATE_ARCHIVE_BYTE_HASH_DRIFT"):
        inspect_private_backup(archive,LIVE)


def test_fake_archive_path_traversal_fails(tmp_path):
    archive=tmp_path/"malicious.tar.gz"
    with tarfile.open(archive,"w:gz") as writer:
        info=tarfile.TarInfo("./../../outside.txt")
        info.size=1
        writer.addfile(info,io.BytesIO(b"x"))
    with pytest.raises(ReleaseHeld, match="PRIVATE_ARCHIVE_MEMBER_NOT_REGULAR_SAFE_FILE"):
        inspect_private_backup(archive,LIVE)


def test_unreviewed_scope_change_fails_closed(monkeypatch):
    from empire_os import earned_media_saas_release_scope as module
    original_read = module.read_index
    calls=0
    def simulated_read(path):
        nonlocal calls
        calls+=1
        data=original_read(path)
        if calls==2:
            data=dict(data)
            data["industries/roofing.html"]="0"*64
        return data
    monkeypatch.setattr(module,"read_index",simulated_read)
    with pytest.raises(ReleaseHeld,match="RELEASE_DIFFERENCE_NOT_TWO_ROUTES_EIGHT_ASSETS"):
        module.check_scope(LIVE,CANDIDATE)
