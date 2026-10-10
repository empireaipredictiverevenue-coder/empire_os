"""Scoped TAM market research v1: explicit opt-in, no fallback, zero-safe."""
import copy
import json

import pytest

from empire_os import tam_market_runtime as tam


DSN="postgresql://empire_tam_market_login:test-secret@127.0.0.1/empiredb"


def result(limit=12):
    industries=("insurance","roofing","solar")
    countries=("GB","US")
    scopes=[(i,c) for i in industries for c in countries]
    return {
      "schema_version":"empire.tam-scoped-reader.v1",
      "selection_method":"MARKET_QUOTA_SAMPLED",
      "source_population_complete":False,
      "requested_limit":limit,
      "requested_scope_count":6,
      "execution_authority":"none",
      "buyer_intent_inferred":False,
      "tam_inferred_from_roster":False,
      "rows":[
        {"entity_id":"roof-1","company_name":"Roofing USA",
         "industry":"roofing","country_code":"US",
         "observed_at":"2026-10-10T14:00:00+00:00",
         "source_ref":"registry:roof-1","execution_authority":"none"},
        {"entity_id":"solar-gb","company_name":"Solar GBR",
         "industry":"solar","country_code":"GB",
         "observed_at":"2026-10-10T14:00:00+00:00",
         "source_ref":"registry:solar-gb","execution_authority":"none"},
      ],
      "scope_coverage":[{
          "industry":i,"country_code":c,
          "sample_quota":limit//6+(j < limit%6),
          "selected_count":int((i,c) in (("roofing","US"),("solar","GB"))),
          "population_complete":False,
      } for j,(i,c) in enumerate(scopes)]
    }


class Cursor:
    def __init__(self,payload):
        self.payload=payload
        self.calls=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params=None):self.calls.append((sql,params))
    def fetchone(self):return (self.payload,)


class Connection:
    def __init__(self,payload):
        self.cur=Cursor(payload)
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def cursor(self):return self.cur


def sample_reader(payload=None):
    conn=Connection(result() if payload is None else payload)
    got=tam.fetch_tam_scoped_market_sample(
        DSN,industries=["roofing","solar","insurance"],
        countries=["US","GB"],limit=12,
        connect_factory=lambda _:conn,
    )
    return got,conn


def test_scoped_runtime_response_covers_all_six_markets_with_unknown_tam():
    got,conn=sample_reader()
    assert got["requested_scope_count"]==6
    assert len(got["rows"])==2
    assert len(got["scope_coverage"])==6
    assert sum(x["selected_count"] for x in got["scope_coverage"])==2
    assert sum(x["sample_quota"] for x in got["scope_coverage"])==12
    assert conn.cur.calls==[
      ("SET TRANSACTION READ ONLY",None),
      ("SET LOCAL ROLE empire_tam_market_reader",None),
      ("SELECT public.get_tam_market_observations_scoped(%s,%s,%s)",
       (["insurance","roofing","solar"],["GB","US"],12)),
    ]


@pytest.mark.parametrize("change",[
 {"source_population_complete":True},
 {"tam_inferred_from_roster":True},
 {"buyer_intent_inferred":True},
 {"execution_authority":"send"},
 {"requested_scope_count":1},
 {"requested_limit":1000},
 {"schema_version":"fake"},
 {"rows":[{"entity_id":"bad","industry":"finance","country_code":"US",
           "execution_authority":"none"}]},
 {"rows":[{"entity_id":"bad","industry":"solar","country_code":"FR",
           "execution_authority":"none"}]},
 {"scope_coverage":[]},
])
def test_scoped_market_reader_rejects_invalid_contract(change):
    wrong={**result(),**change}
    with pytest.raises(ValueError):
        sample_reader(wrong)


def test_scoped_market_reader_rejects_false_quota_and_duplicate_entity():
    wrong=result()
    wrong["scope_coverage"][0]["sample_quota"]=13
    with pytest.raises(ValueError,match="inconsistent"):
        sample_reader(wrong)
    wrong=result()
    wrong["rows"].append(dict(wrong["rows"][0]))
    with pytest.raises(ValueError,match="duplicated"):
        sample_reader(wrong)
    wrong=result()
    wrong["scope_coverage"][0]["selected_count"]=1
    with pytest.raises(ValueError,match="inconsistent"):
        sample_reader(wrong)


@pytest.mark.parametrize("invalid",[
 (["finance"],["GB"],6),
 (["roofing","roofing"],["GB"],6),
 (["roofing"],["FR"],6),
 (["roofing"],["GB","GB"],6),
 (["roofing","solar","insurance"],["GB","US"],5),
 (["roofing","solar","insurance"],["GB","US"],1001),
])
def test_scoped_reader_refuses_unapproved_markets_before_connect(invalid):
    def connect(_):
        raise AssertionError("must not connect for bad scope")
    with pytest.raises(ValueError):
        tam.fetch_tam_scoped_market_sample(
            DSN,industries=invalid[0],countries=invalid[1],
            limit=invalid[2],connect_factory=connect,
        )


def test_scoped_catalog_probe_is_read_only_and_checks_044(monkeypatch):
    monkeypatch.setattr(tam,"probe_isolated_tam_reader_capability",
                        lambda *a,**k:{"isolated_tam_contract_verified":True})
    conn=Connection(None)
    conn.cur.fetchone=lambda: (True,True,True,False,False)
    passed=tam.probe_isolated_tam_scoped_capability(
        DSN,connect_factory=lambda _:conn,
    )
    assert passed["scoped_contract_verified"] is True
    assert passed["no_data_rows_read"] is True
    assert conn.cur.calls[0][0]=="SET TRANSACTION READ ONLY"
    assert conn.cur.calls[1][0]=="SET LOCAL ROLE empire_tam_market_reader"
    assert "pg_catalog.pg_proc" in conn.cur.calls[2][0]
    assert "get_tam_market_observations_scoped" in conn.cur.calls[2][0]


def test_missing_scoped_function_refuses_a_market_read(monkeypatch,tmp_path):
    monkeypatch.setenv("EMPIRE_TAM_READER_MODE","scoped_v1")
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","empire-platform-research")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","roofing,solar,insurance")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB,US")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda:DSN)
    monkeypatch.setattr(tam,"probe_isolated_tam_scoped_capability",
       lambda *a,**k:{"scoped_contract_verified":False})
    monkeypatch.setattr(tam,"fetch_tam_market_observations_postgres",
       lambda *a,**k:(_ for _ in ()).throw(
           AssertionError("no legacy global sample fallback permitted")))
    monkeypatch.setattr(tam,"fetch_tam_scoped_market_sample",
       lambda *a,**k:(_ for _ in ()).throw(
           AssertionError("no scoped source read before catalog preflight")))
    with pytest.raises(RuntimeError,match="scoped catalog preflight"):
        tam.refresh_tam_market_runtime(tmp_path,limit=12)
    assert not (tmp_path/"runtime/tam_market_intelligence/latest.json").exists()


def test_verified_scoped_data_retains_six_requested_quota_slots(
    monkeypatch,tmp_path,
):
    monkeypatch.setenv("EMPIRE_TAM_READER_MODE","scoped_v1")
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","empire-platform-research")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","roofing,solar,insurance")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB,US")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda:DSN)
    monkeypatch.setattr(tam,"probe_isolated_tam_scoped_capability",
       lambda *a,**k:{"scoped_contract_verified":True})
    monkeypatch.setattr(tam,"fetch_tam_scoped_market_sample",
       lambda *a,**k:result())
    saved=tam.refresh_tam_market_runtime(tmp_path,limit=12)
    assert saved["source_row_count"]==2
    assert saved["market_scope_count"]==2
    assert saved["requested_market_scope_count"]==6
    assert saved["market_scope_zero_observation_count"]==4
    assert len(saved["market_scope_sample_coverage"])==6
    assert saved["sampling_method"]=="MARKET_QUOTA_SAMPLED"
    assert saved["source_rows_examined_meaning"]=="RETURNED_SAMPLE_ROWS_ONLY"
    assert saved["source_population_complete"] is False
    assert saved["execution_authority"]=="none"
    assert saved["buyer_intent_inferred"] is False
    assert all(s["tam_entity_count"] is None for s in saved["market_scopes"])
    reader=tam.build_tam_runtime_snapshot(tmp_path)
    assert reader["available"] is True


def test_unknown_tam_mode_never_falls_back_to_legacy_or_scoped(
    monkeypatch,tmp_path,
):
    monkeypatch.setenv("EMPIRE_TAM_READER_MODE","preview_unsupported")
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","empire-platform-research")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","roofing")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","US")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda:DSN)
    with pytest.raises(RuntimeError,match="reader mode not approved"):
        tam.refresh_tam_market_runtime(tmp_path,limit=12)



def test_scoped_snapshot_tam_truth_distinguishes_requested_from_observed(
    monkeypatch,tmp_path,
):
    from empire_os.revenue_completion_supervisor import tam_snapshot_truth
    monkeypatch.setenv("EMPIRE_TAM_READER_MODE","scoped_v1")
    monkeypatch.setenv("EMPIRE_TAM_TENANT_ID","empire-platform-research")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_INDUSTRIES","roofing,solar,insurance")
    monkeypatch.setenv("EMPIRE_TAM_ACTIVE_COUNTRIES","GB,US")
    monkeypatch.setattr(tam,"load_tam_isolated_dsn",lambda:DSN)
    monkeypatch.setattr(tam,"probe_isolated_tam_scoped_capability",
       lambda *a,**k:{"scoped_contract_verified":True})
    monkeypatch.setattr(tam,"fetch_tam_scoped_market_sample",
       lambda *a,**k:result())
    payload=tam.refresh_tam_market_runtime(tmp_path,limit=12)
    truth=tam_snapshot_truth(payload)
    assert truth["available"] is True
    assert truth["sampling_method"]=="MARKET_QUOTA_SAMPLED"
    assert truth["market_scope_count"]==2
    assert truth["requested_market_scope_count"]==6
    assert truth["market_scope_zero_observation_count"]==4
    assert truth["source_row_count"]==2
    invalids=[]
    item=copy.deepcopy(payload)
    item["market_scope_sample_coverage"][0]["selected_count"]=9
    invalids.append(item)
    item=copy.deepcopy(payload)
    item["market_scope_zero_observation_count"]=0
    invalids.append(item)
    item=copy.deepcopy(payload)
    item["requested_sample_limit"]=1000
    invalids.append(item)
    item=copy.deepcopy(payload)
    item["source_population_complete"]=True
    invalids.append(item)
    item=copy.deepcopy(payload)
    item["source_rows_examined_meaning"]="ALL_MARKET_CENSUS"
    invalids.append(item)
    item=copy.deepcopy(payload)
    item["market_scope_sample_coverage"][0]["population_complete"]=True
    invalids.append(item)
    for bad in invalids:
        status=tam_snapshot_truth(bad)
        assert status["available"] is False
        assert status["market_scope_count"]==0
        assert status["execution_authority"]=="none"
