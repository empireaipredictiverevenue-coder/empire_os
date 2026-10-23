from hashlib import sha256
from pathlib import Path
import tarfile

import pytest

from scripts.publish_industry_enquiry_v2_20261023 import (
    ReleaseHold, _index, archive_full_site,
)
from scripts.release_predictive_roofing_two_page_20261022 import (
    apply_four_pages_and_eight_assets, TwoPageReleaseHeld,
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def temp_site(tmp_path: Path):
    original = tmp_path / "live"
    staged = tmp_path / "stage"
    original.mkdir()
    staged.mkdir()
    for i in range(10):
        file = Path("pages") / f"page_{i}.html"
        (original / file).parent.mkdir(parents=True, exist_ok=True)
        (staged / file).parent.mkdir(parents=True, exist_ok=True)
        (original / file).write_bytes(f"OLD {i}".encode())
        (staged / file).write_bytes(f"NEW {i}".encode())
    for i in range(6):
        file = Path("_next") / "static" / f"asset_{i}.js"
        (staged / file).parent.mkdir(parents=True, exist_ok=True)
        (staged / file).write_bytes(f"ASSET {i}".encode())
    (original / "preserved.txt").write_text("not a release target")
    return original, staged


def parts(live: Path, stage: Path):
    before = _index(live)
    proposed = _index(stage)
    original = {k: v for k, v in before.items() if k.startswith("pages/")}
    replace = {k: v for k, v in proposed.items() if k.startswith("pages/")}
    added = {k: v for k, v in proposed.items() if k.startswith("_next/")}
    return before, original, replace, added


def test_backup_readback_verifies_every_original_file(tmp_path):
    live, stage = temp_site(tmp_path)
    before, _, _, _ = parts(live, stage)
    archive = tmp_path / "protected" / "fresh.tar"
    archive.parent.mkdir()
    result = archive_full_site(root=live, dest=archive, contents=before)
    assert result["files_readback_verified"] == 11
    assert result["archive_sha256"] == digest(archive)
    assert archive.stat().st_mode & 0o777 == 0o600
    with tarfile.open(archive, "r:") as reader:
        assert sorted(member.name for member in reader) == sorted("out/" + name for name in before)
    with pytest.raises(ReleaseHold, match="BACKUP_ALREADY_EXISTS"):
        archive_full_site(root=live, dest=archive, contents=before)


def test_backup_rejects_source_changed_after_inventory(tmp_path):
    live, stage = temp_site(tmp_path)
    before, _, _, _ = parts(live, stage)
    (live / "pages" / "page_2.html").write_text("tampered")
    backup = tmp_path / "fresh.tar"
    with pytest.raises(ReleaseHold, match="BACKUP_SOURCE_DRIFT"):
        archive_full_site(root=live, dest=backup, contents=before)
    assert not backup.exists()


def test_original_owner_transaction_applies_only_authorized_paths(tmp_path):
    live, stage = temp_site(tmp_path)
    before, original, replace, added = parts(live, stage)
    expected = {**before, **replace, **added}
    def check():
        assert _index(live) == expected
    result = apply_four_pages_and_eight_assets(
        live=live, stage=stage, baseline=original,
        replacements=replace, additions=added, final_probe=check,
    )
    assert result["page_navigation_files_replaced"] == 10
    assert result["new_hashed_assets_installed"] == 6
    assert _index(live) == expected
    assert digest(live / "preserved.txt") == before["preserved.txt"]


def test_failed_new_live_probe_restores_all_old_files_and_removes_assets(tmp_path):
    live, stage = temp_site(tmp_path)
    before, original, replace, added = parts(live, stage)
    def fail():
        raise RuntimeError("owner GET canary failed")
    with pytest.raises(RuntimeError, match="owner GET canary failed"):
        apply_four_pages_and_eight_assets(
            live=live, stage=stage, baseline=original,
            replacements=replace, additions=added, final_probe=fail,
        )
    assert _index(live) == before
    assert not any((live / name).exists() for name in added)


def test_collision_prevents_any_public_changes(tmp_path):
    live, stage = temp_site(tmp_path)
    _, original, replace, added = parts(live, stage)
    key = next(iter(added))
    (live / key).parent.mkdir(parents=True, exist_ok=True)
    (live / key).write_text("another owner wrote here")
    current = _index(live)
    with pytest.raises(TwoPageReleaseHeld):
        apply_four_pages_and_eight_assets(
            live=live, stage=stage, baseline=original,
            replacements=replace, additions=added,
        )
    assert _index(live) == current
