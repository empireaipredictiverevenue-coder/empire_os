from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import stat

import empire_os.acp_runtime_authority as authority
from empire_os.predictive_cloud_fabric import ExecutionAuthority


def fake_stat(
    monkeypatch,
    *,
    uid=0,
    mode=stat.S_IFREG | 0o600,
):
    monkeypatch.setattr(
        authority.os,
        "fstat",
        lambda *args, **kwargs: SimpleNamespace(
            st_uid=uid,
            st_mode=mode,
        ),
    )


def test_missing_capability_is_default_deny(tmp_path):
    result, source = authority.load_acp_execution_authority(
        tmp_path / "missing"
    )

    assert result is None
    assert source == "capability_absent"


def test_root_0600_exact_value_grants_bounded_internal(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.write_text("execute_bounded\n")

    fake_stat(monkeypatch)

    result, source = authority.load_acp_execution_authority(path)

    assert result is ExecutionAuthority.EXECUTE_BOUNDED
    assert source == "root_capability_file"


def test_plain_wrong_value_cannot_grant_authority(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.write_text("AUTO_INTERNAL\n")

    fake_stat(monkeypatch)

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_value_rejected"


def test_observe_value_does_not_grant_mutation(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.write_text("observe\n")

    fake_stat(monkeypatch)

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_value_rejected"


def test_non_root_owner_is_rejected(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.write_text("execute_bounded\n")

    fake_stat(monkeypatch, uid=1000)

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_owner_rejected"


def test_group_readable_capability_is_rejected(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.write_text("execute_bounded\n")

    fake_stat(
        monkeypatch,
        mode=stat.S_IFREG | 0o640,
    )

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_permissions_rejected"


def test_world_readable_capability_is_rejected(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.write_text("execute_bounded\n")

    fake_stat(
        monkeypatch,
        mode=stat.S_IFREG | 0o604,
    )

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_permissions_rejected"


def test_symlink_is_rejected(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "authority-target"
    target.write_text("execute_bounded\n")
    path = tmp_path / "authority"
    path.symlink_to(target)

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_symlink_rejected"


def test_directory_is_rejected(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "authority"
    path.mkdir()

    fake_stat(
        monkeypatch,
        mode=stat.S_IFDIR | 0o600,
    )

    result, source = authority.load_acp_execution_authority(path)

    assert result is None
    assert source == "capability_not_regular_file"
