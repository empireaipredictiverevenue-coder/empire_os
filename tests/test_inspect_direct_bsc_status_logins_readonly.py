"""Read-only direct BSC login verification: offline fixtures and redaction."""
from pathlib import Path
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import inspect_direct_bsc_status_logins_readonly as probe
from scripts.provision_direct_bsc_buyer_status_logins import (
    READ_LOGIN, ISSUE_LOGIN, READ_KEY, ISSUE_KEY, dsn_for,
)


def creds():
    return {
        READ_KEY: dsn_for("dbname=empiredb host=127.0.0.1 port=5432",
                          READ_LOGIN,"reader-private-12345"),
        ISSUE_KEY: dsn_for("dbname=empiredb host=127.0.0.1 port=5432",
                           ISSUE_LOGIN,"issuer-private-67890"),
    }


def file(tmp_path):
    config=tmp_path/"credentials.env"
    config.write_text("".join(
        key+"="+json.dumps(value)+"\n" for key,value in creds().items()))
    config.chmod(0o600)
    return config


def root_test_path(monkeypatch, path):
    real=Path.stat
    def safe_stat(p, *args, **kwargs):
        result=real(p,*args,**kwargs)
        if p==path:
            return SimpleNamespace(st_uid=0,st_mode=result.st_mode)
        return result
    monkeypatch.setattr(Path,"stat",safe_stat)


def test_no_args_or_apply_never_read_credentials(capsys):
    for args in ([],["--apply"],["--verify-only","--apply"]):
        assert probe.main(args)==3
    assert "HELD_EXACT_READONLY_FLAG_REQUIRED" in capsys.readouterr().out


def test_sealed_file_required(monkeypatch,tmp_path):
    f=file(tmp_path)
    with pytest.raises(ValueError,match="permissions"):
        probe._safe_env(f)  # regular user's temp fixture is not root owned
    f.chmod(0o644)
    with pytest.raises(ValueError):
        probe._safe_env(f)
    f.chmod(0o600)
    alias=tmp_path/"symlink"
    alias.symlink_to(f)
    with pytest.raises(ValueError):
        probe._safe_env(alias)
    root_test_path(monkeypatch,f)
    assert probe._safe_env(f)==creds()


@pytest.mark.parametrize("value",[
    "dbname=empiredb host=192.0.2.50 port=5432 user="+READ_LOGIN+" password=x",
    "dbname=other host=127.0.0.1 port=5432 user="+READ_LOGIN+" password=x",
    "dbname=empiredb host=127.0.0.1 port=5433 user="+READ_LOGIN+" password=x",
    "dbname=empiredb host=127.0.0.1 port=5432 user=empiredb_app password=x",
    "dbname=empiredb host=127.0.0.1 port=5432 user="+READ_LOGIN,
])
def test_noncanonical_or_uncredentialed_dsn_rejected(value):
    with pytest.raises(ValueError):
        probe._identity(value,READ_LOGIN)


def test_prove_success_leaves_no_token_or_buyer_data(monkeypatch,tmp_path):
    f=file(tmp_path)
    root_test_path(monkeypatch,f)
    monkeypatch.setattr(probe.os,"geteuid",lambda:0)
    checked=[]
    monkeypatch.setattr(probe,"verify_login",
                        lambda *args:checked.append(args))
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def execute(self,sql,params=None):
            if params is not None:
                assert params==("0"*64,)
                assert sql=="SELECT public.read_direct_bsc_buyer_status(%s)"
            return self
        def fetchone(self):return (None,)
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def cursor(self):return Cursor()
        def rollback(self):pass
    output=probe.prove(path=f,connect=lambda *a,**kw:Connection())
    assert len(checked)==2
    assert output["reader_login_verified"] is True
    assert output["issuer_login_verified"] is True
    assert output["token_issued"] is False
    assert output["buyer_records_exposed"] is False
    assert not any("private" in str(v) for v in output.values())


def test_missing_row_or_unexpected_data_denied(monkeypatch,tmp_path):
    f=file(tmp_path);root_test_path(monkeypatch,f)
    monkeypatch.setattr(probe.os,"geteuid",lambda:0)
    monkeypatch.setattr(probe,"verify_login",lambda *a:None)
    class Cursor:
        def __init__(self,returned):self.returned=returned
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def execute(self,*a):return self
        def fetchone(self):return self.returned
    class Connection:
        def __init__(self,row):self.row=row
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def cursor(self):return Cursor(self.row)
        def rollback(self):pass
    for row in (({"buyer_id":"BAD"},),(),None):
        with pytest.raises((ValueError,TypeError)):
            probe.prove(path=f,connect=lambda *a,**kw:Connection(row))


def test_distinct_passwords_required(monkeypatch,tmp_path):
    env=creds()
    env[ISSUE_KEY]=dsn_for(
        "dbname=empiredb host=127.0.0.1 port=5432",
        ISSUE_LOGIN,"reader-private-12345",
    )
    f=tmp_path/"same.env"
    f.write_text("".join(k+"="+json.dumps(v)+"\n" for k,v in env.items()))
    f.chmod(0o600)
    root_test_path(monkeypatch,f)
    monkeypatch.setattr(probe.os,"geteuid",lambda:0)
    with pytest.raises(ValueError,match="shared"):
        probe.prove(path=f)


def test_source_no_financial_writes_and_no_credentials_printed():
    source=Path(probe.__file__).read_text()
    for forbidden in ("CREATE ROLE ", "INSERT INTO public.","ALTER ROLE ",
                      "UPDATE public.","DELETE FROM public.", "systemctl restart"):
        assert forbidden not in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "credentials_exposed" in source
