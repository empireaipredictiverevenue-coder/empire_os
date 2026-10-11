"""CRM first-party login operator safety, no production credentials/DB."""
import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/provision_crm_dedicated_logins.py"
spec = importlib.util.spec_from_file_location("crm_login_operator", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def hba(line, users, database=None, method="scram-sha-256", type="local", error=None):
    return {"rule_number": line, "line_number": line, "type": type,
            "database": database or ["empiredb"], "user_name": users,
            "auth_method": method, "error": error}


def exact_hba():
    return [hba(n, [role]) for n, role in enumerate(module.ROLES, 1)] + [
        hba(9, ["all"], database=["all"], method="peer")
    ]


def test_first_party_only_specific_three_roles():
    assert module.AUTH == "empire_crm_auth_login"
    assert module.MEMBER == "empire_crm_membership_login"
    assert module.READER.startswith("empire_crm_tenant_")
    assert len(module.READER.rsplit("_", 1)[-1]) == 12
    assert len(set(module.ROLES)) == 3


def test_exact_role_only_scram_is_ready():
    assert module.hba_ready(exact_hba()) is True


def test_unconfigured_peer_auth_or_shadowed_hba_is_blocked():
    assert module.hba_ready([hba(1, ["all"], database=["all"], method="peer")]) is False
    assert module.hba_ready(
        [hba(0, ["all"], database=["all"], method="trust")] + exact_hba()
    ) is False
    assert module.hba_ready(
        [hba(0, ["all"], database=["all"], method="peer")] + exact_hba()
    ) is False
    assert module.hba_ready([hba(1, [module.AUTH], method="trust")] +
                            [hba(i, [role]) for i, role in enumerate(module.ROLES[1:], 2)]) is False
    assert module.hba_ready(exact_hba()[:-2]) is False
    assert module.hba_ready(exact_hba() + [hba(10, ["unrelated"], error="invalid")]) is False
    assert module.hba_ready([hba(1, [module.AUTH], type="host")] + exact_hba()[1:]) is False


def test_role_group_and_partial_match_cannot_authorize_login():
    assert module.hba_ready(
        [hba(0, ["+somegroup"], database=["all"], method="peer")] + exact_hba()
    ) is False
    assert module.hba_ready(
        [hba(1, [module.AUTH, module.MEMBER])] + exact_hba()[1:]
    ) is False
    assert module.hba_ready([]) is False


def test_approval_flag_guarded_and_no_secret_logging_terms():
    source = SCRIPT.read_text()
    assert "--approved-three-crm-logins" in source
    assert "os.geteuid() != 0" in source
    assert "SET LOCAL password_encryption='scram-sha-256'" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "WITH INHERIT FALSE, SET TRUE" in source
    assert "pgpass" in source
    assert "pg_catalog.pg_hba_file_rules" in source
    assert "ALTER ROLE" in source
    assert "CREATE ROLE" in source
    assert "empire_tenant_role_bindings" in source
    assert "READER not in roles" in source
    assert "public.empire_crm_login_credentials" in source
    assert "SUBJECT = \"founder:phil_livesley\"" in source
    assert "systemctl" not in source
    assert "pg_hba.conf" in source and "never changes pg_hba" in source.lower()
    assert "print(passwords)" not in source
    assert "logger." not in source
    assert "GRANT ALL" not in source
    assert "GRANT UPDATE" not in source
    assert "GRANT DELETE" not in source


def test_no_args_refused_without_database_or_vault_changes():
    r = subprocess.run(["python3", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 3
    assert ("BLOCKED_ROOT_OPERATOR_REQUIRED" in r.stdout
            or "BLOCKED_EXACT_APPROVAL_ARGUMENTS_REQUIRED" in r.stdout)


def test_scram_verifiers_are_salted_nonreversible():
    from base64 import b64decode
    passwd="isolated-production-length-fixture-password-12345"
    first=module.scram_verifier(passwd,b"abcdefghijklmnop")
    second=module.scram_verifier(passwd,b"ponmlkjihgfedcba")
    assert first.startswith("SCRAM-SHA-256$4096:")
    assert first != second
    assert passwd not in first
    assert len(first) < 220
    assert len(b64decode(first.split(":",1)[1].split("$")[0]))==16
    for bad in ("too-short", None, ""):
        import pytest
        with pytest.raises(ValueError):
            module.scram_verifier(bad)
    import pytest
    with pytest.raises(ValueError):
        module.scram_verifier(passwd,b"short")


def test_secret_file_exclusive_owner_only(tmp_path,monkeypatch):
    import stat
    import pytest
    monkeypatch.setattr(module,"VAULT_DIR",tmp_path/"new-private-vault")
    monkeypatch.setattr(module,"PASSFILE",tmp_path/"new-private-vault"/"pgpass")
    passwords={role:"dummy-fixture-very-strong-password-"+role for role in module.ROLES}
    module._write_passfile(passwords)
    assert stat.S_IMODE(module.VAULT_DIR.stat().st_mode)==0o700
    assert stat.S_IMODE(module.PASSFILE.stat().st_mode)==0o600
    assert len(module.PASSFILE.read_text().splitlines())==3
    assert all(module.SOCKET in line and ":5432:empiredb:" in line for line in
               module.PASSFILE.read_text().splitlines())
    with pytest.raises(RuntimeError):
        module._write_passfile(passwords)


def test_only_scram_verifiers_enter_role_ddl():
    import inspect
    source = inspect.getsource(module.operator_apply)
    assert 'data.get("verifiers")' in source
    assert "passwords" not in source
    assert "sql.Literal(verifiers[role])" in source
    assert "sql.Literal(verifiers[READER])" in source
    assert "INSERT INTO public.empire_tenant_role_bindings" in source
    assert "GRANT empire_revenue_crm_reader TO" in source
    assert "GRANT ALL" not in source
    assert "public.empire_crm_tenant_memberships" not in source
    assert "public.empire_crm_login_credentials" not in source
    assert "catalog(vault_reserved=True)" in source
