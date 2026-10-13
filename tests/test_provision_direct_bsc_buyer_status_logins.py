"""Dedicated 049/050 login provisioning contracts: NO default writes."""
from pathlib import Path
import json
import subprocess

import pytest
from scripts import provision_direct_bsc_buyer_status_logins as p


def test_default_off_and_exact_approval_gate(capsys):
    assert p.main([])==0
    o=json.loads(capsys.readouterr().out)
    assert o["status"]=="STAGED_LOGIN_PROVISIONING_NOT_APPLIED"
    assert o["reader_login_created"] is False
    assert o["issuer_login_created"] is False
    for args in (["--apply"],["--preflight"],
                 ["--apply","--approved-050-private-token-issuer-only"],
                 ["--apply",p.APPROVAL,"extra"]):
        assert p.main(args)==3
    assert "HELD_SEPARATE_LOGIN_APPROVAL_REQUIRED" in capsys.readouterr().out


@pytest.mark.parametrize("bad",(
    "dbname=other host=127.0.0.1 user=app",
    "dbname=empiredb host=db.example.com",
    "dbname=empiredb host=8.8.8.8",
    "dbname=empiredb host=127.0.0.1 port=5433",
    "dbname=empiredb host=127.0.0.1 hostaddr=8.8.8.8 port=5432",
    "",
))
def test_cannot_reuse_foreign_database(bad):
    with pytest.raises(ValueError):
        p.dsn_for(bad,p.READ_LOGIN,"safe")


def test_exact_dedicated_dsn_strips_app_password():
    result=p.dsn_for(
      "dbname=empiredb host=127.0.0.1 port=5432 user=empiredb_app "
      "password=old_user_secret",
      p.READ_LOGIN,"my_new_secret",
    )
    assert "old_user_secret" not in result
    assert "empiredb_app" not in result
    assert "my_new_secret" in result
    assert p.READ_LOGIN in result
    with pytest.raises(ValueError):
        p.dsn_for("dbname=empiredb host=127.0.0.1","untrusted_login","safe")


def test_login_sql_contains_exact_roles_and_not_table_grants():
    sql=p.provision_sql({p.READ_LOGIN:"A"*54,p.ISSUE_LOGIN:"B"*54})
    for login,role,secret in (
        (p.READ_LOGIN,p.READ_ROLE,"A"*54),
        (p.ISSUE_LOGIN,p.ISSUE_ROLE,"B"*54),
    ):
        assert f"CREATE ROLE {login} LOGIN NOINHERIT NOSUPERUSER" in sql
        assert (f"CREATE ROLE {login} LOGIN NOINHERIT NOSUPERUSER "
                "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS "
                f"PASSWORD '{secret}';") in sql
        assert (f"GRANT {role} TO {login} "
                "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;") in sql
        assert f"ALTER ROLE {login} SET statement_timeout='3s';" in sql
        assert "DIRECT_STATUS_LOGIN_ALREADY_EXISTS_RECONCILE" in sql
    assert sql.startswith("BEGIN;") and sql.endswith("COMMIT;\n")
    assert "GRANT SELECT" not in sql
    assert "GRANT INSERT" not in sql
    assert "GRANT UPDATE" not in sql
    assert "GRANT DELETE" not in sql
    assert "GRANT empiredb_migrator" not in sql
    assert "CREATE POLICY" not in sql
    with pytest.raises(ValueError):
        p.provision_sql({p.READ_LOGIN:"short",p.ISSUE_LOGIN:"B"*54})
    with pytest.raises(ValueError):
        p.provision_sql({p.READ_LOGIN:"A"*54})


def test_existing_env_not_overwritten_and_new_secret_file_0600(tmp_path):
    target=tmp_path/"owned.env"
    p._write_env(target,'A="x"\n')
    assert target.stat().st_mode & 0o777==0o600
    with pytest.raises(ValueError):
        p._write_env(target,'A="y"\n')
    assert target.read_text()=='A="x"\n'
    link=tmp_path/"link"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        p._write_env(link,'bad')


def test_provisioner_source_has_readback_and_no_public_feature():
    s=Path(p.__file__).read_text()
    for necessary in (
        "existing_contracts_verified()", "checkout_still_off()",
        "SET TRANSACTION READ ONLY",
        "SET LOCAL ROLE ",
        "secrets.token_urlsafe(42)",
        "runuser",
        "DIRECT_STATUS_049_050_ROLE_OR_FUNCTION_DRIFT",
        "session_user",
        "NOINHERIT",
        "_write_env(ENV_FILE,body)",
        '"secrets_printed":False',
    ):
        assert necessary in s
    assert "systemctl restart" not in s
    assert "ALTER DEFAULT PRIVILEGES" not in s
    assert "CREATE POLICY" not in s
    assert "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON" not in s


def test_readback_refuses_any_failed_or_missing_check(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path/"scripts").mkdir()
    paths=[
      "inspect_direct_bsc_private_reader_049_postcommit.sql",
      "inspect_direct_bsc_private_issuer_050_postcommit.sql",
    ]
    for path in paths:
        (tmp_path/"scripts"/path).write_text("BEGIN READ ONLY;")
    class R:
        returncode=0
        stdout="\n".join(
           f"{i:02d}_security_flag|PASS" for i in range(1,13)
        )
        stderr=""
    monkeypatch.setattr(subprocess,"run",lambda *a,**k:R())
    # 049=12 but 050=10 => stop.
    with pytest.raises(ValueError,match="security contract drift"):
        p.existing_contracts_verified()
    def proper(args,**kwargs):
        class Out:
            returncode=0
            stdout="\n".join(
                f"{i:02d}_security_flag|PASS"
                for i in range(1,13 if "049" in args[-1] else 11)
            )
        return Out()
    monkeypatch.setattr(subprocess,"run",proper)
    p.existing_contracts_verified()



def test_ascii_role_names_support_real_postgres_encoding_without_relaxation():
    assert p._role_name(p.READ_LOGIN)==p.READ_LOGIN
    assert p._role_name(p.READ_ROLE.encode("ascii"))==p.READ_ROLE
    assert p._role_name(b"\xff")==""
    assert p._role_name(None)==""
    assert p._role_name(True)==""
