"""No-operation contract for original 066 owner release. Live mutation never tested."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / (
    "scripts/activate_existing_predictive_066_held_20261108.py"
)
spec=importlib.util.spec_from_file_location("owner_066_release",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_original_sql_is_exactly_sha_pinned_and_derived_not_replaced():
    source=m.ORIGINAL.read_bytes()
    assert m.h(source)==m.ORIGINAL_SHA
    sql=m.original_sql()
    assert source.decode()!=sql
    assert m.h(m.ORIGINAL.read_bytes())==m.ORIGINAL_SHA
    assert sql.count("CREATE ROLE empire_predictive_rights_reader")==1
    assert "CREATE ROLE empire_predictive_rights_login" not in sql
    assert "empiredb_migrator_login" in sql
    assert sql.count("m.inherit_option AND m.set_option AND NOT m.admin_option")==1
    assert sql.startswith("-- EmpireOS Predictive Cloud 066")
    assert sql.rstrip().endswith("COMMIT;")


def test_one_held_transaction_and_original_049_policy_preflight():
    sql=m.original_sql()
    assert sql.count("\nBEGIN;")==1
    assert sql.rstrip().endswith("COMMIT;")
    assert sql.index("CREATE ROLE empire_predictive_rights_reader") < sql.index("DO $guard$")
    assert m.TRUSTED_049_SHA==m.h(m.TRUSTED_049.read_bytes())
    assert "m.inherit_option AND m.set_option AND NOT m.admin_option" in m.TRUSTED_049.read_text()


def test_readback_demands_all_rls_acl_nologin_and_no_entitlement():
    sql=m.SQL_READBACK
    for token in (
        "relforcerowsecurity", "relrowsecurity", "aclexplode",
        "empire_predictive_rights_reader", "empire_predictive_rights_login",
        "has_function_privilege", "NOT has_table_privilege",
        "acl.grantee=0", "revocations_held",
    ):
        assert token in sql
    assert "customer" not in m.original_sql().split("CREATE TABLE")[1].split("CREATE TABLE")[0]


def test_backup_is_full_and_root_only_by_construction():
    source=SCRIPT.read_text()
    assert 'BACKUP_DIR.mkdir(mode=0o700)' in source
    assert 'os.open(BACKUP,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)' in source
    assert '"-Fc","-d","empiredb"' in source
    assert '"pg_restore","--list"' in source
    assert "--no-owner" not in source
    assert "--no-privileges" not in source
    assert '"--apply-founder-approved"' in source
    assert '"--rehearse-isolated"' in source


def test_untrusted_original_source_sha_blocks_execution(monkeypatch,tmp_path):
    wrong=tmp_path/"066.sql"
    wrong.write_text("BEGIN; COMMIT;")
    monkeypatch.setattr(m,"ORIGINAL",wrong)
    with pytest.raises(RuntimeError,match="original_owner_sql_sha_changed"):
        m.original_sql()
