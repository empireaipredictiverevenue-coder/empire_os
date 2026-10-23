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


def test_unprivileged_publish_rejects_before_creating_lock(tmp_path, monkeypatch, capsys):
    """No ubuntu-owned sticky-directory lock from a held first attempt."""
    import json
    import scripts.publish_industry_enquiry_v2_20261023 as publisher

    lock = tmp_path / "v2-release.lock"
    monkeypatch.setattr(publisher, "LOCK", lock)
    monkeypatch.setattr(publisher.os, "geteuid", lambda: 1000)
    exit_code = publisher.main([publisher.APPROVAL])

    result = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert result["status"] == "INDUSTRY_ENQUIRY_V2_PUBLICATION_HELD"
    assert result["reason"] == "ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED"
    assert result["customer_submission"] is False
    assert result["outbound_sent"] is False
    assert not lock.exists()


def test_authorised_lock_path_uses_single_file_without_real_publication(tmp_path, monkeypatch, capsys):
    """Simulate a trusted private owner directory; never touch the real backup."""
    import json
    import os
    import scripts.publish_industry_enquiry_v2_20261023 as publisher

    private = tmp_path / "root-only"
    private.mkdir(mode=0o700)
    lock = private / "v2-release.lock"
    real_lock = publisher._locked_release
    monkeypatch.setattr(publisher, "_locked_release",
        lambda: real_lock(lock, None, expected_uid=os.getuid(), enforce_root=False))
    monkeypatch.setattr(publisher, "publish", lambda: {"status": "PRIVATE_NOOP_TEST"})
    exit_code = publisher.main([publisher.APPROVAL])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PRIVATE_NOOP_TEST"
    assert lock.is_file()
    assert lock.stat().st_mode & 0o777 == 0o600


def test_private_owner_lock_preserves_legacy_concurrency_without_mutating_it(tmp_path):
    import os
    import fcntl
    from scripts.publish_industry_enquiry_v2_20261023 import _locked_release
    private_dir = tmp_path / "protected"
    private_dir.mkdir(mode=0o700)
    private = private_dir / "industry.lock"
    legacy = tmp_path / "old-ubuntu.lock"
    legacy.write_bytes(b"")
    legacy.chmod(0o600)
    before = legacy.stat()
    with _locked_release(private, legacy, expected_uid=os.geteuid(), enforce_root=False):
        assert private.is_file()
        assert private.stat().st_mode & 0o777 == 0o600
        assert private.stat().st_uid == os.geteuid()
        with private.open("rb") as competing:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with legacy.open("rb") as competing:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    after = legacy.stat()
    assert (before.st_ino, before.st_uid, before.st_mode, before.st_size) == (
        after.st_ino, after.st_uid, after.st_mode, after.st_size)


def test_private_lock_rejects_insecure_owner_directory(tmp_path):
    import os
    from scripts.publish_industry_enquiry_v2_20261023 import _locked_release
    directory = tmp_path / "insecure"
    directory.mkdir(mode=0o777)
    directory.chmod(0o777)
    with pytest.raises(ReleaseHold, match="ROOT_ONLY_RELEASE_LOCK_DIRECTORY_REQUIRED"):
        with _locked_release(directory / "lock", None,
                             expected_uid=os.geteuid(), enforce_root=False):
            pytest.fail("untrusted lock directory admitted")
    assert not (directory / "lock").exists()


def test_private_lock_refuses_symlink_and_world_readable_file(tmp_path):
    import os
    from scripts.publish_industry_enquiry_v2_20261023 import _locked_release
    directory = tmp_path / "protected"
    directory.mkdir(mode=0o700)
    target = tmp_path / "unrelated"
    target.write_text("must not write")
    (directory / "lock").symlink_to(target)
    with pytest.raises(OSError):
        with _locked_release(directory / "lock", None,
                             expected_uid=os.geteuid(), enforce_root=False):
            pytest.fail("symlink lock admitted")
    (directory / "lock").unlink()
    (directory / "lock").write_text("")
    (directory / "lock").chmod(0o644)
    with pytest.raises(ReleaseHold, match="UNTRUSTED_PRIVATE_RELEASE_LOCK_FILE"):
        with _locked_release(directory / "lock", None,
                             expected_uid=os.geteuid(), enforce_root=False):
            pytest.fail("world-readable owner lock admitted")


def test_unprivileged_owner_cannot_run_even_with_private_lock_available(tmp_path):
    import os
    from scripts.publish_industry_enquiry_v2_20261023 import _locked_release
    if os.geteuid() == 0:
        pytest.skip("only meaningful in an unprivileged test runner")
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    with pytest.raises(ReleaseHold, match="ORIGINAL_WEBSITE_ROOT_OWNER_AUTHORITY_REQUIRED"):
        with _locked_release(directory / "lock", None):
            pytest.fail("non-root acquired publication lock")
    assert not (directory / "lock").exists()
