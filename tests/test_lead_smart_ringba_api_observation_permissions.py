import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_lead_smart_ringba_api_observer as writer


def output(tmp_path: Path) -> Path:
    directory = tmp_path / "ringba"
    directory.mkdir()
    return directory / "api_observation" / "latest.json"


def test_observation_remains_readable_and_atomically_updated(tmp_path):
    out = output(tmp_path)
    value = {
        "mode": "OBSERVE",
        "raw_call_row_count": 1,
        "execution_authority": "NONE",
    }

    writer.write_observation(value, out=out)
    assert json.loads(out.read_text()) == value
    assert stat.S_IMODE(out.stat().st_mode) == 0o640

    updated = dict(value, raw_call_row_count=2)
    writer.write_observation(updated, out=out)
    assert json.loads(out.read_text()) == updated
    assert not list(out.parent.glob("*.tmp"))


def test_root_started_observer_assigns_reader_owner(tmp_path, monkeypatch):
    out = output(tmp_path)
    observed = out.parent.parent.stat()
    expected_owner = (observed.st_uid, observed.st_gid)
    chown_calls = []

    monkeypatch.setattr(writer.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        writer.os,
        "chown",
        lambda path, uid, gid: chown_calls.append(
            (Path(path), uid, gid)
        ),
    )

    writer.write_observation({"raw_call_row_count": 1}, out=out)
    assert len(chown_calls) == 2
    assert all(
        (uid, gid) == expected_owner
        for _, uid, gid in chown_calls
    )
    assert chown_calls[0][0] != out
    assert chown_calls[1][0] == out.parent
    assert stat.S_IMODE(out.parent.stat().st_mode) == 0o750


def test_root_run_rejects_root_owned_reader_directory(tmp_path, monkeypatch):
    out = output(tmp_path)
    reader_dir = out.parent.parent
    original_lstat = Path.lstat

    def fake_lstat(path):
        value = original_lstat(path)
        if path == reader_dir:
            return SimpleNamespace(
                st_mode=value.st_mode,
                st_uid=0,
                st_gid=0,
            )
        return value

    monkeypatch.setattr(writer.os, "geteuid", lambda: 0)
    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(RuntimeError, match="non-root"):
        writer.write_observation({"raw_call_row_count": 1}, out=out)
    assert not out.exists()


def test_symlink_reader_root_rejected(tmp_path):
    out = output(tmp_path)
    actual = tmp_path / "real"
    actual.mkdir()
    out.parent.parent.rmdir()
    out.parent.parent.symlink_to(actual, target_is_directory=True)
    with pytest.raises(RuntimeError, match="real directory"):
        writer.write_observation({}, out=out)
