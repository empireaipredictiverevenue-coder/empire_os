"""Guarded schema installer checks without production SQL execution."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE=Path(__file__).resolve().parents[1] / "scripts/guarded_install_consumer_schema_20261021.py"
spec=importlib.util.spec_from_file_location("consumer_schema_installer",MODULE)
installer=importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(installer)


def test_exact_release_digest_reflects_both_sql_files_and_prepared_role():
    digest=installer.fingerprint()
    assert isinstance(digest,str) and len(digest)==64
    assert digest=="2fa878eb0d93d011dc55b1cba0e9c37b58603944b9c99abb4959a1238b80de0c"
    assert "NOLOGIN NOINHERIT" in installer.ROLE_SQL
    assert len(installer.TABLES)==5


def test_original_migrations_execute_in_one_outer_transaction():
    for source in (installer.SQL057,installer.SQL058):
        text=installer.strip_transaction_boundaries(source)
        assert "BEGIN;" not in text
        assert "COMMIT;" not in text
        assert "SET LOCAL ROLE empiredb_migrator" in text
        assert "FORCE ROW LEVEL SECURITY" in text or "CREATE POLICY" in text


def test_production_writer_requires_local_postgres_identity(monkeypatch):
    monkeypatch.setattr(installer.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(installer.pwd, "getpwuid", lambda _: SimpleNamespace(pw_name="ubuntu"))
    for key in ("PGHOST","PGPORT","EMPIREDB_DSN"):
        monkeypatch.delenv(key, raising=False)
    def never_connect(**kwargs):
        raise AssertionError("unauthorised install attempted to open a DB")
    monkeypatch.setattr(installer.psycopg,"connect",never_connect)
    with pytest.raises(RuntimeError,match="OPERATE_UNDER_POSTGRES_IDENTITY"):
        installer.installer("apply",installer.fingerprint())


def test_explicit_release_digest_is_required_even_for_postgres_identity(monkeypatch):
    monkeypatch.setattr(installer.os,"geteuid",lambda:1001)
    monkeypatch.setattr(installer.pwd,"getpwuid",lambda _:SimpleNamespace(pw_name="postgres"))
    for key in ("PGHOST","PGPORT","EMPIREDB_DSN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(installer.psycopg,"connect",lambda **_:pytest.fail("db opened"))
    with pytest.raises(RuntimeError,match="EXACT_RELEASE_DIGEST_APPROVAL_REQUIRED"):
        installer.installer("apply","wrong-digest")


def test_fixture_mode_refuses_live_or_ambiguous_connection(monkeypatch):
    for key in ("PGHOST","PGPORT","EMPIREDB_DSN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(installer.psycopg,"connect",lambda **_:pytest.fail("db opened"))
    with pytest.raises(RuntimeError,match="EPHEMERAL_FIXTURE_CLUSTER_REQUIRED"):
        installer.installer("test")


def test_atomic_real_pg_fixtures_are_safe_and_have_positive_negative_paths():
    root=MODULE.parents[1]
    positive=(root/"scripts/test_consumer_atomic_installer_20261021.sh").read_text()
    negative=(root/"scripts/test_consumer_atomic_installer_reject_20261021.sh").read_text()
    for s in (positive,negative):
        assert "empire_consumer_optin_fixture" in s
        assert "PGHOST" in s and "PGPORT" in s
        assert "--test-ephemeral" in s
        assert "sudo" not in s
        assert "--apply-owner-approved" not in s
    assert "NONCOMPLIANT_ROLE_REJECTED_WITH_ZERO_TABLE_WRITES" in negative
