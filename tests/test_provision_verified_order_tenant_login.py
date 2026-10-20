"""Safe single-tenant order login provisioning contract; no actual writes."""
from pathlib import Path
import re

import pytest

from scripts import provision_verified_order_tenant_login_20261020 as m


def test_requires_explicit_authorized_flags(capsys):
    assert m.main([]) == 3
    assert "EXACT_FLAG_REQUIRED" in capsys.readouterr().out


def test_login_sql_is_single_scoped_role_with_atomic_proof():
    sql = m._create_login_sql("a" * 64)
    assert "BEGIN;" in sql and "COMMIT;" in sql
    assert "CREATE ROLE empire_verified_order_tenant_login" in sql
    assert "NOBYPASSRLS" in sql and "NOINHERIT" in sql
    assert "NOCREATEDB" in sql and "NOCREATEROLE" in sql
    assert "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE" in sql
    assert "GRANT CONNECT ON DATABASE empiredb TO empire_verified_order_tenant_login" in sql
    assert "INSERT INTO public.empire_tenant_role_bindings" in sql
    assert "FOUNDER_APPROVED_EXACT_ORDER_READER_20261020" in sql
    assert "SET LOCAL password_encryption='scram-sha-256'" in sql
    assert "GRANT ALL" not in sql
    assert "CREATE POLICY" not in sql
    assert "CREATE TABLE" not in sql
    assert "INSERT INTO public.fulfilment_orders" not in sql


@pytest.mark.parametrize("password", ["", "not-hex", "a" * 63, "z" * 64])
def test_invalid_generated_credential_cannot_enter_sql(password):
    with pytest.raises(ValueError):
        m._create_login_sql(password)


def test_unready_preflight_cannot_provision(monkeypatch, capsys):
    monkeypatch.setattr(m, "preflight", lambda: {"status": "HELD"})
    def unexpected(*_args, **_kwargs):
        raise AssertionError("must not provision")
    monkeypatch.setattr(m, "_create_vault", unexpected)
    monkeypatch.setattr(m, "_admin", unexpected)
    assert m.main(["--apply-founder-approved-one-tenant-login"]) == 2
    assert "PRECHECK_HOLD" in capsys.readouterr().out


def test_root_vault_excludes_order_ids_and_never_logs_credentials():
    source = Path(m.__file__).read_text()
    assert "secrets.token_hex(32)" in source
    assert "0o700" in source and "0o600" in source
    assert "O_EXCL" in source and "O_NOFOLLOW" in source
    assert 'print(password)' not in source
    assert "127.0.0.1:5432" in source
    assert "PGPASSWORD" not in source
