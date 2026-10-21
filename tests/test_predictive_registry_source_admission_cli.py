"""CLI is read-only, failure-sanitized, and never manufactures registry proof."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest
import scripts.review_predictive_registry_source_admission_20261021 as cli


def test_missing_reader_credential_stays_unverified(monkeypatch, capsys):
    monkeypatch.delenv(cli.ENV, raising=False)
    assert cli.main(["--read-only"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "HELD_ORIGINAL_REGISTRY_ACCESS_UNVERIFIED"
    assert data["customer_forecast_eligible"] is False
    assert data["database_writes"] is False
    assert data["registry_candidate_count"] is None


def test_database_error_is_redacted(monkeypatch, capsys):
    monkeypatch.setenv(cli.ENV, "secret:do-not-emit")
    def fail(*, dsn):
        raise cli.RegistrySourceHeld("secret and tenant identifiers")
    monkeypatch.setattr(cli, "read_existing_tenant_registry_receipts", fail)
    assert cli.main(["--read-only"]) == 0
    reply = capsys.readouterr().out
    assert "secret" not in reply
    assert "tenant identifiers" not in reply


def test_unauthorized_cli_mode_rejected():
    import os
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        ["/srv/empire_os/.venv/bin/python", "-B", str(Path(cli.__file__))],
        capture_output=True, text=True, timeout=8, check=False, env=env,
    )
    assert result.returncode != 0
    assert "read-only" in result.stderr
