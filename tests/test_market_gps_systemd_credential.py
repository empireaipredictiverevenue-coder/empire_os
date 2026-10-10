"""Systemd LoadCredential bridge to restricted Market GPS: no root secret leakage."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys

import pytest


def _module():
    root = Path(__file__).resolve().parents[1]
    file = root / "scripts/run_market_gps_credentialed.py"
    spec = importlib.util.spec_from_file_location("test_market_gps_credentialed", file)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write(tmp_path, credential):
    (tmp_path / "market-gps.dsn").write_text(credential + "\n")
    return str(tmp_path)


def test_only_restricted_local_credentials_are_accepted(tmp_path):
    m = _module()
    dsn = "postgresql://empire_intelligence_materializer_login:testing@127.0.0.1:5432/empiredb"
    assert m.validated_credential(_write(tmp_path, dsn)) == dsn


@pytest.mark.parametrize("bad", [
    "postgresql://empiredb_app:testing@127.0.0.1:5432/empiredb",
    "postgresql://empire_intelligence_materializer_login:testing@127.0.0.1/other",
    "postgresql://empire_intelligence_materializer_login:testing@public.example/empiredb",
    "postgresql://empire_intelligence_materializer_login@127.0.0.1/empiredb",
    "postgresql://empire_intelligence_materializer_login:testing@127.0.0.1/empiredb?options=-cstatement_timeout%3D0",
    "postgresql://empire_intelligence_materializer_login:testing@127.0.0.1/empiredb?hostaddr=198.51.100.8",
    "nonsense",
])
def test_bad_db_credentials_rejected_without_leaking(tmp_path, bad):
    m = _module()
    with pytest.raises(ValueError) as exc:
        m.validated_credential(_write(tmp_path, bad))
    assert bad not in str(exc.value)


def test_no_credentials_directory_refuses_to_run(monkeypatch, capsys):
    m = _module()
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    assert m.main() == 3
    text = capsys.readouterr().out
    assert "RESTRICTED_CREDENTIAL_NOT_READY" in text
    assert "postgresql://" not in text


def test_service_runs_no_plain_environmentfile():
    unit = (Path(__file__).resolve().parents[1] /
            "deploy/systemd/empire-market-gps.service").read_text()
    assert "LoadCredential=market-gps.dsn:/etc/empire/market-gps.dsn" in unit
    assert "EnvironmentFile=" not in unit
    assert "User=ubuntu" in unit


def test_wrapper_can_invoke_original_runner_with_env_only_during_call(tmp_path, monkeypatch):
    m = _module()
    dsn = "postgresql://empire_intelligence_materializer_login:testing@127.0.0.1/empiredb"
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", _write(tmp_path, dsn))
    from scripts import build_market_sweep_snapshot as original
    key = "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"
    before = os.environ.get(key)
    def fake_run():
        assert os.environ.get(key) == dsn
        return 0
    monkeypatch.setattr(original, "main", fake_run)
    assert m.main() == 0
    assert os.environ.get(key) is None
    if before is not None:
        monkeypatch.setenv(key, before)
