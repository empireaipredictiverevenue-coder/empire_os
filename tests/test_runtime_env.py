import os
from pathlib import Path

import pytest

from empire_os.runtime_env import load_runtime_env


def test_exported_environment_wins_over_file(tmp_path, monkeypatch):
    p=tmp_path/"runtime.env"
    p.write_text("SUPABASE_URL=file-url\nSUPABASE_SERVICE_KEY=file-key\n")
    monkeypatch.setenv("SUPABASE_URL","exported-url")
    env=load_runtime_env(p,required=("SUPABASE_URL","SUPABASE_SERVICE_KEY"))
    assert env["SUPABASE_URL"]=="exported-url"
    assert env["SUPABASE_SERVICE_KEY"]=="file-key"


def test_unreadable_or_missing_file_is_ok_when_env_exported(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL","https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY","secret-present")
    env=load_runtime_env(
        tmp_path/"missing.env",
        required=("SUPABASE_URL","SUPABASE_SERVICE_KEY"),
    )
    assert env["SUPABASE_SERVICE_KEY"]=="secret-present"


def test_missing_required_values_fail_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL",raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY",raising=False)
    with pytest.raises(RuntimeError,match="missing required runtime env"):
        load_runtime_env(
            tmp_path/"missing.env",
            required=("SUPABASE_URL","SUPABASE_SERVICE_KEY"),
        )
