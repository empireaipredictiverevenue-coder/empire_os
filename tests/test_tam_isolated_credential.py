"""Prepared isolated TAM-only credential: no secrets, no fallback, no unit install."""
from pathlib import Path
import pytest
from empire_os.tam_isolated_credential import (
    CREDENTIAL_NAME, UNIT_CREDENTIAL_DIR, load_tam_isolated_dsn,
)

DSN=("postgresql://empire_tam_market_login:"
     "test-secret@127.0.0.1/empiredb")


def private_credential(folder: Path, data=DSN):
    folder.mkdir(parents=True, exist_ok=True)
    p=folder/CREDENTIAL_NAME
    p.write_text(data+"\n")
    p.chmod(0o400)
    return p


def test_isolated_credential_validates_research_only_login(tmp_path):
    private_credential(tmp_path)
    assert load_tam_isolated_dsn(tmp_path)==DSN


@pytest.mark.parametrize("dsn",[
    "postgresql://empire_intelligence_materializer_login:secret@localhost/empiredb",
    "postgresql://empire_tam_market_login:secret@remote.example/empiredb",
    "postgresql://empire_tam_market_login:secret@localhost/otherdb",
    "postgresql://empire_tam_market_login@localhost/empiredb",
    "postgresql://postgres:secret@localhost/empiredb",
    "postgresql://empire_tam_market_login:secret@localhost/empiredb?options=-c%20search_path%3Dpublic",
])
def test_only_tam_login_can_read_credential(tmp_path,dsn):
    private_credential(tmp_path,dsn)
    with pytest.raises(ValueError,match="dedicated local EmpireDB"):
        load_tam_isolated_dsn(tmp_path)


def test_missing_systemd_context_never_uses_old_market_gps(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_DIRECTORY",raising=False)
    monkeypatch.setenv("EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",
                       "postgresql://existing:password@localhost/empiredb")
    with pytest.raises(ValueError,match="systemd credential context"):
        load_tam_isolated_dsn()
    monkeypatch.setenv("CREDENTIALS_DIRECTORY","/run/credentials/empire-market-gps.service")
    with pytest.raises(ValueError,match="systemd credential context"):
        load_tam_isolated_dsn()


def test_untrusted_credential_file_and_symlinks_rejected(tmp_path):
    folder=tmp_path/"creds"
    p=private_credential(folder)
    p.chmod(0o644)
    with pytest.raises(ValueError,match="unsafe isolated TAM credential"):
        load_tam_isolated_dsn(folder)
    p.chmod(0o400)
    p.unlink()
    other=tmp_path/"elsewhere"
    other.write_text(DSN)
    p.symlink_to(other)
    with pytest.raises(ValueError,match="unsafe isolated TAM credential"):
        load_tam_isolated_dsn(folder)


def test_systemd_unit_is_prepared_without_timer_or_enablement():
    p=Path("deploy/systemd/empire-tam-market-read.service")
    content=p.read_text()
    assert "LoadCredential=tam-market.dsn:/etc/empire/tam-market.dsn" in content
    assert "ConditionPathExists=/etc/empire/tam-market.dsn" in content
    assert "ConditionPathExists=/etc/empire/tam-market-scope.env" in content
    assert "ReadWritePaths=/srv/empire_os/runtime/tam_market_intelligence" in content
    assert "NoNewPrivileges=true" in content
    assert "ProtectSystem=strict" in content
    assert "UMask=0077" in content
    assert "EnvironmentFile=/etc/empire/tam-market-scope.env" in content
    assert "empire-tam-market-read.timer" not in content
    assert "WantedBy=" not in content
    assert "market-gps.dsn" not in content
    assert str(UNIT_CREDENTIAL_DIR).endswith("empire-tam-market-read.service")


def test_isolated_catalog_probes_new_login_not_old_materializer():
    from empire_os.tam_market_runtime import (
        probe_isolated_tam_reader_capability,
        probe_tam_reader_capability,
    )
    class Cursor:
        def __init__(self):
            self.calls=[]
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def execute(self,sql,params=None): self.calls.append((sql,params))
        def fetchone(self):
            return (True,True,True,True,True,False,False,False,True,True,True)
    class Connection:
        def __init__(self): self.cursor_value=Cursor()
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def cursor(self): return self.cursor_value
    connection=Connection()
    dsn=DSN
    report=probe_isolated_tam_reader_capability(
        dsn,connect_factory=lambda _:connection
    )
    assert report["status"]=="PASS"
    assert report["isolated_tam_contract_verified"] is True
    calls=connection.cursor_value.calls
    assert calls[0][0]=="SET TRANSACTION READ ONLY"
    assert calls[1][0]=="SET LOCAL ROLE empire_tam_market_reader"
    assert calls[2][1]==(
        "empire_tam_market_login","empire_tam_market_reader"
    )
    assert "prosecdef" in calls[2][0]
    assert "empiredb_migrator" in calls[2][0]
    assert "search_path=" in calls[2][0]
    old="postgresql://empire_intelligence_materializer_login:old-secret@localhost/empiredb"
    with pytest.raises(ValueError):
        probe_isolated_tam_reader_capability(
            old,connect_factory=lambda _: (_ for _ in ()).throw(
                AssertionError("old login must not connect to isolated TAM")
            )
        )
    # Legacy diagnostics still use their own old identity.
    older=Connection()
    legacy=probe_tam_reader_capability(
        old,connect_factory=lambda _:older
    )
    assert legacy["migration_028_contract_verified"] is True
    assert older.cursor_value.calls[1][0]==(
        "SET LOCAL ROLE empire_intelligence_materializer"
    )
