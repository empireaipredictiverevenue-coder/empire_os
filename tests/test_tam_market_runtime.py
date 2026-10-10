from pathlib import Path

import pytest

from empire_os.tam_market_runtime import (
    build_tam_runtime,
    build_tam_runtime_snapshot,
    fetch_tam_market_observations_postgres,
    write_tam_snapshot,
)


class Cursor:
    description = ()

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params or ()))

    def fetchone(self):
        return (self.payload,)


class Connection:
    def __init__(self, payload):
        self.cursor_obj = Cursor(payload)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_obj


def test_restricted_reader_uses_capability_role():
    connection = Connection([{
        "entity_id": "e1",
        "company_name": "One",
        "industry": "roofing",
        "country_code": "US",
        "source_ref": "https://example.com/evidence",
        "observed_at": "2026-10-02T12:00:00+00:00",
        "execution_authority": "none",
    }])
    rows = fetch_tam_market_observations_postgres(
        "postgresql://empire_tam_market_login:test-secret@127.0.0.1/empiredb",
        connect_factory=lambda _dsn: connection,
    )
    assert rows[0]["entity_id"] == "e1"
    assert connection.cursor_obj.calls == [
        ("SET TRANSACTION READ ONLY", ()),
        ("SET LOCAL ROLE empire_tam_market_reader", ()),
        ("SELECT public.get_tam_market_observations(%s)", (1000,)),
    ]


def test_runtime_build_preserves_unknown_tam_and_expansion_classes():
    result = build_tam_runtime(
        [{
            "entity_id": "e1",
            "company_name": "Solar One",
            "industry": "solar",
            "country_code": "GB",
            "source_ref": "registry:1",
            "observed_at": "2026-10-02T12:00:00+00:00",
            "execution_authority": "none",
        }],
        tenant_id="empire",
        active_industries=["roofing"],
        active_countries=["US"],
    )
    scope = result["market_scopes"][0]
    assert scope["tam_state"] == "UNKNOWN"
    assert scope["tam_entity_count"] is None
    assert {
        row["opportunity_class"]
        for row in result["opportunity_classes"]
    } == {"new_industry", "new_country", "new_industry_country"}
    assert result["external_execution"] is False
    assert result["execution_authority"] == "none"


def test_runtime_requires_explicit_market_configuration():
    with pytest.raises(ValueError, match="active TAM industries required"):
        build_tam_runtime(
            [],
            tenant_id="empire",
            active_industries=[],
            active_countries=["US"],
        )


def test_runtime_rejects_authoritative_source_row():
    with pytest.raises(ValueError, match="execution authority"):
        build_tam_runtime(
            [{
                "entity_id": "e1",
                "company_name": "One",
                "industry": "roofing",
                "country_code": "US",
                "source_ref": "registry:1",
                "observed_at": "2026-10-02T12:00:00+00:00",
                "execution_authority": "internal_write",
            }],
            tenant_id="empire",
            active_industries=["roofing"],
            active_countries=["US"],
        )


def test_snapshot_round_trip(tmp_path):
    payload = build_tam_runtime(
        [{
            "entity_id": "e1", "company_name": "Test Firm",
            "industry": "solar", "country_code": "GB",
            "source_ref": "registry:1",
            "observed_at": "2026-10-10T10:00:00+00:00",
            "execution_authority": "none",
        }],
        tenant_id="research-scope",
        active_industries=["solar"], active_countries=["GB"],
    )
    path = write_tam_snapshot(tmp_path, payload)
    assert path == (
        Path(tmp_path) / "runtime/tam_market_intelligence/latest.json"
    )
    result = build_tam_runtime_snapshot(tmp_path)
    assert result["available"] is True
    assert result["execution_authority"] == "none"
    assert result["market_scope_count"] == 1
    assert result["market_scopes"][0]["tam_state"] == "UNKNOWN"
    assert result["market_scopes"][0]["tam_entity_count"] is None


def test_missing_snapshot_fails_closed(tmp_path):
    result = build_tam_runtime_snapshot(tmp_path)
    assert result["available"] is False
    assert result["opportunity_classes"] == []
    assert result["execution_authority"] == "none"



def test_tam_runtime_rejects_cross_tenant_source_binding():
    from empire_os.tam_market_runtime import build_tam_runtime
    with pytest.raises(ValueError,match="mixed tenant"):
        build_tam_runtime(
            [{
                "tenant_id":"different-tenant","entity_id":"e7",
                "company_name":"Business","industry":"roofing",
                "country_code":"US","source_ref":"registry:7",
                "observed_at":"2026-10-10T10:00:00+00:00",
                "execution_authority":"none",
            }],
            tenant_id="intended-tenant",
            active_industries=["roofing"],active_countries=["US"],
        )


def test_tam_runtime_has_time_and_never_claims_tenant_login_is_verified():
    result=build_tam_runtime(
       [{
         "entity_id":"e8", "company_name":"Real canonical firm",
         "industry":"roofing","country_code":"US",
         "source_ref":"registry:8",
         "observed_at":"2026-10-10T10:00:00+00:00",
         "execution_authority":"none",
       }],
       tenant_id="research-scope", active_industries=["roofing"],
       active_countries=["US"],
    )
    assert result["source"]=="empiredb_restricted_tam_reader"
    assert result["tenant_source_scope_verified"] is False
    assert result["data_scope"]=="PLATFORM_MARKET_RESEARCH_ONLY"
    assert result["generated_at"]
    assert result["outreach_enabled"] is False


def test_tam_snapshot_is_owner_private_and_symlink_safe(tmp_path):
    path=write_tam_snapshot(tmp_path,{"mode":"OBSERVE","execution_authority":"none"})
    assert path.stat().st_mode & 0o777 == 0o600
    path.unlink()
    target=tmp_path/"elsewhere.json"
    target.write_text("keep")
    path.symlink_to(target)
    with pytest.raises(ValueError,match="unsafe TAM snapshot"):
        write_tam_snapshot(tmp_path,{"mode":"OBSERVE"})
    assert target.read_text()=="keep"



def test_tam_catalog_preflight_is_read_only_and_proves_exact_capability():
    from empire_os.tam_market_runtime import probe_tam_reader_capability

    class Prober(Cursor):
        def __init__(self, row):
            super().__init__(None)
            self.row=row
        def fetchone(self):
            return self.row

    class Session:
        def __init__(self,row):
            self.cur=Prober(row)
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def cursor(self): return self.cur

    dsn="postgresql://empire_intelligence_materializer_login:local-secret@localhost/empiredb"
    valid=(True,True,True,True,True,False,False,False,True,True,True)
    connection=Session(valid)
    passed=probe_tam_reader_capability(dsn,connect_factory=lambda _:connection)
    assert passed["status"]=="PASS"
    assert passed["migration_028_contract_verified"] is True
    assert passed["source_table_direct_read_grants"] is False
    assert passed["no_data_rows_read"] is True
    queries=[x[0] for x in connection.cur.calls]
    assert queries[0]=="SET TRANSACTION READ ONLY"
    assert queries[1]=="SET LOCAL ROLE empire_intelligence_materializer"
    assert "pg_catalog.pg_proc" in queries[2]
    assert "get_tam_market_observations(integer)" in queries[2]
    assert "p.proowner" in queries[2]
    assert "empiredb_migrator" in queries[2]
    assert "search_path=" in queries[2]
    assert "p.provolatile = 's'" in queries[2]
    assert queries[2].count(
        "SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER"
    ) == 3
    assert all(q.lstrip().split(maxsplit=1)[0].upper() in ("SET","SELECT")
               for q in queries)
    assert "SET TRANSACTION READ ONLY" == queries[0]
    assert "local-secret" not in str(passed)
    for bad in (
        (True,True,False,False,False,False,False,False,True,True,True),
        (True,True,True,True,False,False,False,False,True,True,True),
        (True,True,True,True,True,True,False,False,True,True,True),
        (False,True,True,True,True,False,False,False,True,True,True),
        (True,True,True,True,True,False,False,False,False,True,True),
    ):
        failed=probe_tam_reader_capability(
            dsn,connect_factory=lambda _,b=bad:Session(b)
        )
        assert failed["migration_028_contract_verified"] is False
        assert failed["execution_authority"]=="none"


@pytest.mark.parametrize("invalid",[
    "postgresql://empiredb_app:secret@localhost/empiredb",
    "postgresql://empire_intelligence_materializer_login:secret@remote.example.com/empiredb",
    "postgresql://empire_intelligence_materializer_login:secret@localhost/otherdb",
    "postgresql://empire_intelligence_materializer_login:secret@localhost/empiredb?options=-c%20search_path%3Dpublic",
    "",
])
def test_tam_catalog_preflight_never_falls_back_to_unsafe_login(invalid):
    from empire_os.tam_market_runtime import probe_tam_reader_capability
    with pytest.raises(ValueError):
        probe_tam_reader_capability(
            invalid,connect_factory=lambda _: (_ for _ in ()).throw(
                AssertionError("bad credentials must not be used")
            )
        )


def test_tam_catalog_connection_failure_is_redacted_and_no_data_read():
    from empire_os.tam_market_runtime import probe_tam_reader_capability
    dsn="postgresql://empire_intelligence_materializer_login:secret@localhost/empiredb"
    def unavailable(_):
        raise RuntimeError("private password=secret should not appear in response")
    result=probe_tam_reader_capability(dsn,connect_factory=unavailable)
    assert result["status"]=="RESTRICTED_CATALOG_PROBE_UNAVAILABLE"
    assert result["no_data_rows_read"] is True
    assert "secret" not in str(result)



RESTRICTED_DSN = (
    "postgresql://empire_tam_market_login:"
    "test-secret@127.0.0.1/empiredb"
)


@pytest.mark.parametrize("dsn",[
    "postgresql://postgres:secret@localhost/empiredb",
    "postgresql://empiredb_app:secret@localhost/empiredb",
    "postgresql://empire_intelligence_materializer_login:secret@localhost/empiredb",
    "postgresql://empire_intelligence_materializer_login:secret@remote.example/empiredb",
    "postgresql://empire_intelligence_materializer_login:secret@localhost/other",
    "postgresql://empire_intelligence_materializer_login@localhost/empiredb",
    "postgresql://empire_intelligence_materializer_login:secret@localhost/empiredb?hostaddr=8.8.8.8",
    "postgresql://empire_intelligence_materializer_login:secret@localhost/empiredb?options=-c%20session_replication_role%3Dreplica",
    "",
])
def test_real_market_reader_fails_closed_on_unsafe_connection(dsn):
    with pytest.raises(ValueError):
        fetch_tam_market_observations_postgres(
            dsn,connect_factory=lambda _: (_ for _ in ()).throw(
                AssertionError("unsafe DB connection must never be opened")
            )
        )


@pytest.mark.parametrize("limit",[False,True,-1,0,1.3,"100",5001])
def test_real_market_reader_rejects_non_integer_or_out_of_range_bound(limit):
    with pytest.raises(ValueError,match="reader limit"):
        fetch_tam_market_observations_postgres(
            RESTRICTED_DSN,limit=limit,
            connect_factory=lambda _: (_ for _ in ()).throw(
                AssertionError("invalid limit must never query database")
            )
        )


@pytest.mark.parametrize("payload",[
    [1], [{"valid":"one"}, "corrupt"],
    [{"i":1},{"i":2}],
    {"entity_id":"wrong format"},
    None,
])
def test_real_market_reader_never_silently_drops_malformed_source_rows(payload):
    def simulate(_):
        return Connection(payload)
    with pytest.raises(ValueError,match="invalid payload"):
        fetch_tam_market_observations_postgres(
            RESTRICTED_DSN,limit=1,connect_factory=simulate
        )


def test_real_market_reader_returns_empty_only_if_database_said_empty():
    result=fetch_tam_market_observations_postgres(
        RESTRICTED_DSN,connect_factory=lambda _:Connection([])
    )
    assert result==[]


def test_market_reader_sql_failure_does_not_expose_password_or_chain():
    def unavailable(_):
        raise RuntimeError("could not connect with test-secret")
    with pytest.raises(RuntimeError,match="restricted TAM market read failed") as exc:
        fetch_tam_market_observations_postgres(
            RESTRICTED_DSN,connect_factory=unavailable
        )
    assert exc.value.__cause__ is None
    assert "test-secret" not in str(exc.value)



def test_fake_tam_json_never_claims_canonical_live_success(tmp_path):
    path=write_tam_snapshot(tmp_path,{
        "schema_version":"empire.tam-market-intelligence.v1",
        "available":True,"mode":"OBSERVE","execution_authority":"none",
        "opportunity_classes":[{"opportunity_key":"tam:fake"}],
    })
    assert path.is_file()
    result=build_tam_runtime_snapshot(tmp_path)
    assert result["available"] is False
    assert result["opportunity_classes"] == []
    assert result["reason_code"]=="SNAPSHOT_CONTRACT_NOT_VERIFIED"


def test_untrusted_public_snapshot_or_symlink_does_not_claim_live(tmp_path):
    payload=build_tam_runtime(
        [{"entity_id":"a","company_name":"Test","industry":"solar",
          "country_code":"GB","source_ref":"registry:1",
          "observed_at":"2026-10-10T10:00:00+00:00"}],
        tenant_id="research",active_industries=["solar"],
        active_countries=["GB"],
    )
    path=write_tam_snapshot(tmp_path,payload)
    path.chmod(0o644)
    assert not build_tam_runtime_snapshot(tmp_path)["available"]
    path.chmod(0o600)
    path.unlink()
    real=tmp_path/"target.json"
    real.write_text("not tam")
    path.symlink_to(real)
    assert not build_tam_runtime_snapshot(tmp_path)["available"]


def test_live_tam_refresh_refuses_to_read_rows_until_restricted_catalog_passes(
    tmp_path,monkeypatch,
):
    from empire_os import tam_market_runtime as tam
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","research-platform")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","solar,roofing")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB,US")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda: RESTRICTED_DSN)
    calls=[]
    def fake_probe(*args,**kwargs):
        calls.append("preflight")
        return {"status":"RESTRICTED_CATALOG_CONTRACT_INCOMPLETE",
                 "isolated_tam_contract_verified":False}
    def forbidden_read(*args,**kwargs):
        calls.append("READ")
        raise AssertionError("canonical rows must not be read without approved role/function")
    monkeypatch.setattr(tam,"probe_isolated_tam_reader_capability",fake_probe)
    monkeypatch.setattr(tam,"fetch_tam_market_observations_postgres",forbidden_read)
    with pytest.raises(RuntimeError,match="isolated catalog preflight not verified"):
        tam.refresh_tam_market_runtime(tmp_path)
    assert calls==["preflight"]
    assert not (tmp_path/"runtime/tam_market_intelligence/latest.json").exists()


def test_live_tam_refresh_requires_explicit_market_scope_before_any_db_call(
    tmp_path,monkeypatch,
):
    from empire_os import tam_market_runtime as tam
    monkeypatch.delenv("EMPIRE_TAM_ACTIVE_INDUSTRIES",raising=False)
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","research-platform")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",
        lambda: (_ for _ in ()).throw(AssertionError("no credential before scope")))
    with pytest.raises(RuntimeError,match="TAM runtime configuration incomplete"):
        tam.refresh_tam_market_runtime(tmp_path)
    assert not (tmp_path/"runtime/tam_market_intelligence/latest.json").exists()


def test_live_tam_refresh_safe_positive_path_unknown_denominator(
    tmp_path,monkeypatch,
):
    from empire_os import tam_market_runtime as tam
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","platform-research")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","solar")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda: RESTRICTED_DSN)
    checks=[]
    def proof(*args,**kwargs):
        checks.append("catalog")
        return {"status":"PASS", "isolated_tam_contract_verified":True}
    def read(*args,**kwargs):
        assert checks==["catalog"]
        checks.append("read")
        return [{"entity_id":"e1","company_name":"Canonical Ltd",
                 "industry":"solar","country_code":"GB",
                 "source_ref":"registry:source:1",
                 "observed_at":"2026-10-10T11:00:00+00:00",
                 "execution_authority":"none"}]
    monkeypatch.setattr(tam,"probe_isolated_tam_reader_capability",proof)
    monkeypatch.setattr(tam,"fetch_tam_market_observations_postgres",read)
    result=tam.refresh_tam_market_runtime(tmp_path)
    assert checks==["catalog","read"]
    assert result["market_scope_count"]==1
    assert result["market_scopes"][0]["tam_state"]=="UNKNOWN"
    assert result["market_scopes"][0]["tam_entity_count"] is None
    assert result["buyer_intent_inferred"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"]=="none"
    path=tmp_path/"runtime/tam_market_intelligence/latest.json"
    assert path.is_file() and path.stat().st_mode & 0o777==0o600
    assert tam.build_tam_runtime_snapshot(tmp_path)["available"] is True



def test_isolated_refresh_hard_scopes_and_excludes_unauthorised_markets(
    tmp_path,monkeypatch,
):
    import json
    from empire_os import tam_market_runtime as tam
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","empire-platform-research")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","roofing,solar,insurance")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB,US")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda: RESTRICTED_DSN)
    monkeypatch.setattr(
        tam,"probe_isolated_tam_reader_capability",
        lambda *_a,**_kw: {"isolated_tam_contract_verified":True}
    )
    def record(ident,industry,country):
        return {
            "entity_id":ident,"company_name":"Test "+ident,
            "industry":industry,"country_code":country,
            "source_ref":"registry:"+ident,
            "observed_at":"2026-10-10T14:00:00+00:00",
            "execution_authority":"none",
        }
    source=[
        record("r1","roofing","GB"),
        record("s1","solar","US"),
        record("i1","insurance","GB"),
        record("r2","roofing","DE"),
        record("f1","finance","US"),
    ]
    monkeypatch.setattr(
        tam,"fetch_tam_market_observations_postgres",
        lambda *_a,**_kw: source
    )
    out=tam.refresh_tam_market_runtime(tmp_path,limit=1000)
    assert out["raw_source_rows_examined"]==5
    assert out["out_of_scope_rows_excluded"]==2
    assert out["source_row_count"]==3
    assert out["source_population_complete"] is False
    assert out["approved_research_countries"]==["GB","US"]
    assert out["approved_research_industries"]==["insurance","roofing","solar"]
    assert len(out["market_scopes"])==3
    assert all(x["industry"] in ("roofing","solar","insurance")
               and x["country_code"] in ("GB","US") for x in out["market_scopes"])
    saved=json.loads(
        (tmp_path/"runtime/tam_market_intelligence/latest.json").read_text()
    )
    assert "Test r2" not in str(saved)
    assert "Test f1" not in str(saved)
    assert saved["outreach_enabled"] is False
    assert all(x["tam_entity_count"] is None for x in saved["market_scopes"])



def test_tam_refresh_cli_logs_receipt_not_company_records(monkeypatch,capsys):
    import sys
    from empire_os import tam_market_runtime as tam
    monkeypatch.setattr(tam,"refresh_tam_market_runtime",lambda *_a,**_k:{
        "source_row_count":1,"market_scope_count":1,
        "market_scopes":[{"company_name":"Private Company Should Never Print"}],
        "opportunity_classes":[],
        "execution_authority":"none",
        "outreach_enabled":False,
    })
    monkeypatch.setattr(sys,"argv",[
        "tam_market_runtime","--refresh","--limit","1000"
    ])
    assert tam.main()==0
    out=capsys.readouterr().out
    assert "CANONICAL_SNAPSHOT_WRITTEN" in out
    assert "Private Company" not in out
    assert "source_row_count" in out
    assert "outreach_enabled" in out
