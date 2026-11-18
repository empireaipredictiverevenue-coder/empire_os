"""Synthetic contract tests for NVIDIA MCP environment-connection readiness."""
from __future__ import annotations
import asyncio
import httpx,pytest
from fastmcp import FastMCP,Client
from auto_ontology_mcp import readiness
from auto_ontology_mcp.config import Settings,DEFAULT_SPEC_PATH
from scripts.nvidia_mcp_env_source_compat_20261118 import (
    ENV_SOURCE_PATH, ENV_NOTE, install
)

STATUS=readiness.STATUS_PATH
CONNS=readiness.CONNECTIONS_PATH
DBS=readiness.DATABASES_PATH
def settings():
    return Settings(api_url="http://nvidia-unit.test",
        spec_path=DEFAULT_SPEC_PATH,host="127.0.0.1",port=33013,
        timeout_s=10,chat_timeout_s=30)
def acceptance(status={"calculated":True},ui={"count":0,"data":[]},
               catalog={"count":1,"data":[{"name":"empire_graph"}]},source=True):
    def handler(request):
        val={STATUS:status,CONNS:ui,DBS:catalog,ENV_SOURCE_PATH:source}[request.url.path]
        if isinstance(val,int) and not isinstance(val,bool):
            return httpx.Response(val,json={"error":"not allowed"})
        return httpx.Response(200,json=val)
    async def run():
        async with httpx.AsyncClient(base_url="http://nvidia-unit.test",
            transport=httpx.MockTransport(handler)) as client:
            mcp=FastMCP(name="native-readiness-test")
            readiness.register(mcp,settings(),client)
            previous=await mcp.get_tool("check_readiness")
            await install(mcp,client)
            current=await mcp.get_tool("check_readiness")
            assert previous is not current
            assert previous.name==current.name=="check_readiness"
            assert current.description==previous.description
            async with Client(mcp) as session:
                tools=await session.list_tools()
                assert [x.name for x in tools]==["check_readiness"]
                outcome=await session.call_tool("check_readiness",{})
                return outcome.data
    return asyncio.run(run())
def test_env_configured_connection_not_falsely_missing():
    r=acceptance()
    assert r.semantic_layer_built is True
    assert r.catalog_present is True
    assert r.databases==["empire_graph"]
    assert r.can_execute_sql is True
    assert r.ready is True
    assert r.blockers==[]
    assert r.unverified==[ENV_NOTE]
def test_without_env_or_ui_connection_remains_blocked():
    r=acceptance(source=False)
    assert r.can_execute_sql is False
    assert r.ready is False
    assert any("No database connection" in s for s in r.blockers)
def test_empty_catalog_blocks_even_when_env_configured():
    r=acceptance(catalog={"data":[],"count":0})
    assert r.ready is False
    assert r.can_execute_sql is True
    assert any("No database has been ingested" in s for s in r.blockers)
def test_uncompiled_blocks_even_when_env_configured():
    r=acceptance(status={"calculated":False})
    assert r.ready is False
    assert r.can_execute_sql is True
def test_env_probe_denied_does_not_assert_connection():
    r=acceptance(source=403)
    assert r.ready is False
    assert r.can_execute_sql is False
def test_ui_connection_does_not_need_env_source():
    r=acceptance(ui={"count":1,"data":[{"database_name":"empire_graph"}]},source=403)
    assert r.ready is True
    assert r.can_execute_sql is True
    assert r.unverified==[]
def test_frontend_read_denied_stays_unverified():
    r=acceptance(ui=403,source=True)
    assert r.can_execute_sql is None
    assert r.ready is True
    assert any("not permitted to read" in note for note in r.unverified)
def test_readiness_probe_no_sql_execution_or_connection_writes():
    source=open("/srv/empire_os/scripts/nvidia_mcp_env_source_compat_20261118.py").read()
    assert "connection:manage" not in source
    assert "POST" not in source
    assert "DELETE" not in source
    assert '"/api/connections/source"' in source

def test_original_nine_tool_names_and_contracts_preserved():
    from auto_ontology_mcp.server import build_server
    async def run():
        s=Settings(api_url="http://localhost:33000",
            spec_path=DEFAULT_SPEC_PATH,host="127.0.0.1",port=33013,
            timeout_s=20,chat_timeout_s=180,public_url="http://127.0.0.1:33013")
        mcp,client=build_server(s)
        try:
            before={t.name:t for t in await mcp.list_tools()}
            await install(mcp,client)
            after={t.name:t for t in await mcp.list_tools()}
            assert len(before)==len(after)==9
            assert set(before)==set(after)
            assert mcp.auth is not None
            for name in before:
                assert before[name].parameters==after[name].parameters
                assert before[name].description==after[name].description
        finally:
            await client.aclose()
    asyncio.run(run())


def test_real_fresh_viewer_sql_receipt_executes_database_count():
    from pathlib import Path
    path=Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_viewer_mcp_real_question_20261118.json")
    if not path.is_file():pytest.skip("Live viewer readback available on EmpireOS only")
    import json
    assert path.stat().st_mode & 0o077 == 0
    d=json.loads(path.read_text())
    assert d["actual_mcp_tool"]=="ask_question"
    assert d["administrator_not_used"] is True
    assert d["verified"] is True
    assert d["is_error"] is False
    assert d["generated_sql_present"] is True
    assert d["actual_database_rows_present"] is True
    assert d["sql_count_aggregate"] is True
    assert d["semantic_filter_preserved"] is True
    assert d["expected_count"]==d["actual_count"]==2
    assert d["user_token_disclosed"] is False

def test_live_viewer_six_native_mcp_sql_cases_verified():
    from pathlib import Path
    import json
    p=Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_viewer_six_real_mcp_sql_20261118.json")
    if not p.is_file():
        pytest.skip("Authenticated live Viewer MCP receipt only exists on EmpireOS")
    assert p.stat().st_mode & 0o077 == 0
    data=json.loads(p.read_text())
    assert data["scope"]=="EXISTING_AUTHORIZED_NVIDIA_VIEWER_NATIVE_MCP_SIX_CASE_ACCEPTANCE"
    assert data["admin_not_used"] is True
    assert data["oauth_grant_reused"] is True
    assert data["token_disclosed"] is False
    assert data["target_db_override_used"] is False
    assert data["model_alias"]=="openai/nvidia/nemotron-3.5-super-vl:free"
    assert data["total_cases"]==data["passed_count"]==6
    assert data["all_verified"] is True
    assert len(data["cases"])==6
    for case in data["cases"]:
        assert case["passed"] is True
        assert case["tool_is_error"] is False
        assert case["generated_sql"] is True
        assert case["executed_rows"] is True
        assert case["valid_table_and_predicate"] is True
        assert case["actual"]==case["expected"]
        assert case["failure"] is None
