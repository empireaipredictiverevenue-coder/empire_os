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
        "postgresql://example",
        connect_factory=lambda _dsn: connection,
    )
    assert rows[0]["entity_id"] == "e1"
    assert connection.cursor_obj.calls == [
        ("SET LOCAL ROLE empire_intelligence_materializer", ()),
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
    payload = {
        "schema_version": "empire.tam-market-intelligence.v1",
        "mode": "OBSERVE",
        "opportunity_classes": [],
        "execution_authority": "none",
    }
    path = write_tam_snapshot(tmp_path, payload)
    assert path == (
        Path(tmp_path)
        / "runtime/tam_market_intelligence/latest.json"
    )
    result = build_tam_runtime_snapshot(tmp_path)
    assert result["available"] is True
    assert result["execution_authority"] == "none"


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
    assert not any("INSERT" in q or "UPDATE" in q or "DELETE" in q
                   or "CREATE ROLE" in q or "GRANT " in q for q in queries)
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
