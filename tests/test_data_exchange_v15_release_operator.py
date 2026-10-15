"""Production V15 release operator never escalates or mutates without root."""
from pathlib import Path
import json
import re

import pytest
from scripts import deploy_data_exchange_custody_v15 as release


def test_exact_sql_is_pinned_to_reviewed_commit_and_hash():
    assert release.SQL_HASH == "d0288b5d69e29da2759e4ba64d67f7399fd5271eb5fefb959a4986a3a2996769"
    assert release.RELEASE_COMMIT == "3d7913b9"
    assert release.checksum(release.ROOT/release.SQL_REL) == release.SQL_HASH


def test_sql_assembles_one_atomic_scope_only():
    template = (release.ROOT/release.SQL_REL).read_text(encoding="utf-8")
    ddl = release.transaction_sql(template, "A"*48)
    assert ddl.startswith("BEGIN;")
    assert ddl.rstrip().endswith("COMMIT;")
    assert ddl.count("BEGIN;") == 1
    assert ddl.count("COMMIT;") == 1
    assert ddl.count("CREATE ROLE empire_data_exchange_custodian") == 1
    assert "NOLOGIN NOINHERIT NOSUPERUSER" in ddl
    assert "NOBYPASSRLS" in ddl
    assert "WITH ADMIN FALSE, INHERIT FALSE, SET TRUE" in ddl
    assert "SET LOCAL ROLE empiredb_migrator" in ddl
    assert "FORCE ROW LEVEL SECURITY" in ddl
    assert "GRANT SELECT,INSERT" in ddl
    assert "empiredb_app" not in ddl[ddl.index("CREATE ROLE"):]


@pytest.mark.parametrize("bad",["", "a"*20, "z"*150, "b'"*50])
def test_sql_refuses_untrusted_password_value(bad):
    sql = (release.ROOT/release.SQL_REL).read_text()
    with pytest.raises(release.ReleaseHeld,match="RUNTIME_PASSWORD_SHAPE_INVALID"):
        release.transaction_sql(sql,bad)


def test_ordinary_remote_user_cannot_apply(capsys,monkeypatch):
    monkeypatch.setattr(release.os,"geteuid",lambda:1000)
    assert release.main(["--apply",release.APPROVAL])==2
    obj=json.loads(capsys.readouterr().out)
    assert obj["status"]=="HOLD"
    assert obj["reason_code"]=="AUTHORISED_ROOT_OPERATOR_REQUIRED"
    assert obj["customer_delivery_enabled"] is False
    assert obj["payment_execution"] is False
    assert obj["outbound_enabled"] is False


def test_explicit_approval_flags_mandatory(capsys,monkeypatch):
    monkeypatch.setattr(release.os,"geteuid",lambda:0)
    assert release.main([])==2
    obj=json.loads(capsys.readouterr().out)
    assert obj["reason_code"]=="EXACT_FOUNDER_APPROVED_APPLY_FLAGS_REQUIRED"


def test_no_production_write_from_unprivileged_test_run(capsys):
    # The test process itself is never a root-owned deployment service.
    from os import geteuid
    if geteuid()==0:
        pytest.skip("unprivileged gauntlet only")
    assert release.main(["--apply",release.APPROVAL])==2
    assert json.loads(capsys.readouterr().out)["status"]=="HOLD"


def test_admin_script_has_no_auto_scheduler_or_outbound_imports():
    source=Path(release.__file__).read_text()
    assert '"systemctl","start","empire-data-exchange-custody-capture.service"' in "".join(source.split())
    for bad in ("send_email(", "mail.send", "resend", "supabase",
                "CREATE EXTENSION", "systemctl enable", "timer.service"):
        assert bad not in source
    assert "ProtectSystem=strict" in source
    assert "NoNewPrivileges=true" in source
    assert "User=ubuntu" in source
    assert "EnvironmentFile=" in source
