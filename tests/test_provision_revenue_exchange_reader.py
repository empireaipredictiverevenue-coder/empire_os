from pathlib import Path

import pytest

import scripts.provision_revenue_exchange_reader as module


def test_dry_run_main_does_not_apply(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["provision_revenue_exchange_reader.py"])
    assert module.main() == 0
    out = capsys.readouterr().out
    assert '"changes_applied": false' in out
    assert '"founder_gate": "authority_expansion"' in out


def test_env_writer_is_create_only_and_secret_safe(tmp_path):
    target = tmp_path / "reader.env"
    module._write_env_file(target, "postgresql://reader:secret@127.0.0.1/empiredb")
    text = target.read_text()
    assert text.startswith(module.KEY + "=")
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="explicit credential rotation required"):
        module._write_env_file(target, "postgresql://reader:new@127.0.0.1/empiredb")


def test_provision_sql_grants_exact_reader_capability_and_no_write_capabilities():
    sql = module._provision_sql("abc_DEF-123")
    assert f"GRANT {module.CAPABILITY} TO {module.LOGIN}" in sql
    assert "NOINHERIT" in sql
    assert "NOSUPERUSER" in sql
    assert "NOCREATEROLE" in sql
    assert "NOBYPASSRLS" in sql
    lowered = sql.lower()
    assert "outbound" not in lowered
    assert "payment_approver" not in lowered
    assert "settlement" not in lowered
    assert "revenue_recognizer" not in lowered


def test_runtime_dsn_uses_dedicated_login_only():
    dsn = module._runtime_dsn(
        "postgresql://broad:pw@127.0.0.1:5432/empiredb",
        "reader-secret",
    )
    assert "empire_revenue_exchange_reader_login" in dsn
    assert "reader-secret" in dsn
    assert "broad" not in dsn


def test_runtime_dsn_rejects_nonlocal_database():
    with pytest.raises(ValueError, match="local EmpireDB endpoint required"):
        module._runtime_dsn(
            "postgresql://broad:pw@db.example.com:5432/empiredb",
            "reader-secret",
        )
