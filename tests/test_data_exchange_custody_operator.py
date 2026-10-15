"""V15 custody operator: no free running scanner, no unapproved DB write."""
from datetime import datetime,timezone
import json
from pathlib import Path
import pytest

from scripts import operate_data_exchange_observation_custody as app
from test_data_exchange_agi_bridge import NOW


def official(url):
    token=url.split("/")[-1].replace(".json","")
    record_id=int(token)
    return {
        "entity":record_id,"dataset":"brownfield-land",
        "quality":"authoritative",
        "organisation-entity":202 if record_id==1722645 else 207,
        "planning-permission-status":"non-permissioned",
        "hectares":"0.5",
        "entry-date":"2020-04-03",
        "site-address":"PERSONAL-ADDRESS-NOT-FOR-CUSTODY",
        "contact-email":"SECRET-NOT-FOR-CUSTODY@example.org",
    }


def test_locked_source_capture_reuses_existing_validator():
    snap=app.capture(now=NOW,fetch_json=official)
    assert snap["dataset_record_count"]==3
    assert snap["assessment_status"]=="HOLD"
    assert snap["rights_review_eligible"] is False
    assert "SECRET-NOT-FOR-CUSTODY" not in str(snap)
    assert "PERSONAL-ADDRESS" not in str(snap)
    assert {r["record_id"] for r in snap["records"]}=={
        "1722645","1739516","1739547"}


@pytest.mark.parametrize("ids",[
    (), (1739547,), (1722645, 1739516, 999999),
    (1739547,1739516,1722645),(1722645,1722645,1739547),
    ("1722645",1739516,1739547),
])
def test_fixed_bounded_pilot_identifiers(ids):
    with pytest.raises(ValueError,match="LOCKED_OFFICIAL_SOURCE_PILOT_IDS_REQUIRED"):
        app.capture(now=NOW,entity_ids=ids,fetch_json=official)


def test_preview_never_calls_database(monkeypatch,capsys):
    from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
    monkeypatch.delenv(app.DSN_ENV,raising=False)
    monkeypatch.delenv("EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE",raising=False)
    actual_capture=app.capture
    monkeypatch.setattr(app,"capture",lambda **kwargs:actual_capture(now=NOW,fetch_json=official))
    class NoDatabase:
        def __init__(self,*a,**kw):
            raise AssertionError("preview must not touch DB")
    monkeypatch.setattr(app,"EmpireDBConstructionCustody",NoDatabase)
    assert app.main([])==0
    out=json.loads(capsys.readouterr().out)
    assert out["capture_mode"]=="PREVIEW_ONLY_NOT_STORED"
    assert out["record_count"]==3
    assert out["database_writes"] is False
    assert out["customer_delivery_enabled"] is False


@pytest.mark.parametrize("dsn,release,flag",[
    (None,None,False),
    ("postgres://placeholder",None,True),
    ("postgres://placeholder","FOUNDER_APPROVED_OBSERVATION_APPEND_ONLY",False),
])
def test_write_requires_all_bounded_authority_gates(monkeypatch,capsys,dsn,release,flag):
    if dsn is None:monkeypatch.delenv(app.DSN_ENV,raising=False)
    else:monkeypatch.setenv(app.DSN_ENV,dsn)
    if release is None:monkeypatch.delenv("EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE",raising=False)
    else:monkeypatch.setenv("EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE",release)
    monkeypatch.setattr(app,"capture",lambda **kwargs:(_ for _ in ()).throw(
        AssertionError("must not fetch before gating")))
    argv=["--append"]+(["--approved-custody-only"] if flag else [])
    assert app.main(argv)==2
    out=json.loads(capsys.readouterr().out)
    assert out["capture_mode"]=="HOLD"
    assert out["customer_delivery_enabled"] is False


def test_approved_one_shot_capture_only_uses_existing_db_role(monkeypatch,capsys):
    monkeypatch.setenv(app.DSN_ENV,"opaque-dedicated-connection")
    monkeypatch.setenv("EMPIRE_DATA_EXCHANGE_CUSTODY_RELEASE",app.RELEASE)
    actual_capture=app.capture
    monkeypatch.setattr(app,"capture",lambda **kwargs:actual_capture(now=NOW,fetch_json=official))
    calls=[]
    class TestDb:
        def __init__(self,dsn):
            assert dsn=="opaque-dedicated-connection"
        def append_once(self,snap,*,now):
            calls.append(snap)
            return {"mode":"CANONICAL_APPEND_COMMITTED","sequence":0,
                    "head_chain_sha256":"f"*64,"database_writes":True}
    monkeypatch.setattr(app,"EmpireDBConstructionCustody",TestDb)
    assert app.main(["--append","--approved-custody-only"])==0
    out=json.loads(capsys.readouterr().out)
    assert len(calls)==1
    assert out["database_writes"] is True
    assert out["record_count"]==3
    assert out["customer_delivery_enabled"] is False


def test_sql_is_unversioned_prepared_only_and_never_grants_generic_execution():
    sql=(Path(__file__).resolve().parents[1]/
         "docs/commercial/prepared_sql/PREPARED_ONLY_data_exchange_observation_custody_20261015.sql"
         ).read_text(encoding="utf-8")
    assert "PREPARED ONLY" in sql
    assert "SET LOCAL ROLE empiredb_migrator" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "GRANT SELECT,INSERT" in sql
    assert "empire_data_exchange_custodian" in sql
    assert "NOT rolcanlogin" in sql
    assert "pg_advisory_xact_lock(510218720)" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "BEFORE TRUNCATE" in sql
    assert "BEFORE INSERT" in sql
    assert "Data Exchange continuity mismatch" in sql
    assert "GRANT ALL" not in sql.upper()
    assert "GRANT INSERT ON public.empire_data_exchange_observations TO empiredb_app" not in sql
    assert "CREATE ROLE" not in sql
    assert "ALTER ROLE" not in sql
    assert "CREATE USER" not in sql
