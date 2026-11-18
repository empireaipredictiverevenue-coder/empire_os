"""Two synthetic tenant data-plane canaries for staged FastMCP guard.

Each tenant gets a physically distinct SQLite read-only fixture. This tests
the original FastMCP middleware, canonical membership decision, no-fallback
policy, cross-tenant denials and actual SQL read isolation. It does NOT
replace NVIDIA's semantic SQL engine or certify its live multi-tenant route.
"""
from __future__ import annotations

import asyncio
import contextvars
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

import pytest
from fastmcp import Client,FastMCP

from empire_os.nvidia_ontology_tenant_policy import (
    DataPlaneAttestation,NvidiaTenantAccessPolicy,TenantDeployment,
)
from empire_os.saas_scale import TenantMembership
from scripts import nvidia_mcp_tenant_boundary_20261118 as gate

A="10000000-0000-4000-8000-000000000001"
B="20000000-0000-4000-8000-000000000002"
SUBJECT=contextvars.ContextVar("verified_oauth_subject",default=None)
NOW=datetime(2026,11,18,12,0,tzinfo=timezone.utc)


def fixtures(tmp_path):
    physical={}
    for label,count in (("a",2),("b",7)):
        db=tmp_path/f"tenant_{label}.sqlite"
        conn=sqlite3.connect(db)
        try:
            conn.execute("CREATE TABLE scoped_edges (tenant_label TEXT NOT NULL)")
            conn.executemany("INSERT INTO scoped_edges (tenant_label) VALUES (?)",
                             [(label,)]*count)
            conn.commit()
        finally:conn.close()
        physical[label]=db
    return physical


def tenant_environment(label,db,monkeypatch):
    tenant=A if label=="a" else B
    dep=TenantDeployment(tenant_id=tenant,
                         deployment_id=f"nvidia-synthetic-{label}",
                         datasource_id=f"tenant-{label}-read-only-file")
    names={"oauth-a":"canonical-user-a","oauth-b":"canonical-user-b"}
    memberships={
        ("canonical-user-a",A):TenantMembership(
            tenant_id=A,user_id="canonical-user-a",role="viewer"),
        ("canonical-user-b",B):TenantMembership(
            tenant_id=B,user_id="canonical-user-b",role="viewer"),
    }
    def prove(d):
        return DataPlaneAttestation(
            tenant_id=d.tenant_id,deployment_id=d.deployment_id,
            datasource_id=d.datasource_id,
            mode="dedicated_database",
            verified_at_utc=NOW,
            bound_connector_verified=True,
            no_global_datasource_fallback=True,
            database_isolation_verified=True,
            read_only=True,
            evidence_ref="synthetic-private-fixture-only"
        )
    policy=NvidiaTenantAccessPolicy(dep,
        subject_linker=names.get,
        membership_reader=lambda s,t:memberships.get((s,t)),
        attest_datasource=prove,
        now=lambda:NOW)
    app=FastMCP(f"isolated-tenant-{label}")
    reads=[]
    @app.tool()
    def ask_question(question:str)->dict:
        # Read-only, isolated connector chosen from SERVER-side deployment,
        # never from the question or any client-supplied database/tenant hint.
        reads.append(label)
        uri=db.resolve().as_uri()+"?mode=ro"
        with sqlite3.connect(uri,uri=True) as dbconn:
            value=dbconn.execute("SELECT COUNT(*) FROM scoped_edges").fetchone()[0]
        return {"count":value,"datasource_tenant":label}
    @app.tool()
    def search_terms(query:str)->dict:
        reads.append(label)
        return {"terms":[f"private-term-{label}"]}
    @app.tool()
    def check_readiness()->dict:
        reads.append(label)
        return {"ready":True}
    gate.install_nvidia_tenant_boundary(app,policy)
    return app,reads


def run_tool(app,tool,args,who):
    async def run():
        token=SUBJECT.set(who)
        try:
            async with Client(app) as c:
                return await c.call_tool(tool,args,raise_on_error=False)
        finally:SUBJECT.reset(token)
    return asyncio.run(run())


def output(result):
    assert result.is_error is False
    assert isinstance(result.data,dict)
    return result.data


def test_two_private_sql_fixtures_are_isolated_by_real_middleware(tmp_path,monkeypatch):
    monkeypatch.setattr(gate,"authenticated_subject_from_fastmcp",lambda:SUBJECT.get())
    paths=fixtures(tmp_path)
    a,reads_a=tenant_environment("a",paths["a"],monkeypatch)
    b,reads_b=tenant_environment("b",paths["b"],monkeypatch)
    assert output(run_tool(a,"ask_question",{"question":"Count my edges"},"oauth-a"))=={
        "count":2,"datasource_tenant":"a"}
    assert output(run_tool(b,"ask_question",{"question":"Count my edges"},"oauth-b"))=={
        "count":7,"datasource_tenant":"b"}
    assert reads_a==["a"] and reads_b==["b"]
    for target,reads,wrong_subject in ((a,reads_a,"oauth-b"),(b,reads_b,"oauth-a")):
        result=run_tool(target,"ask_question",{"question":"Count all tenants"} ,wrong_subject)
        assert result.is_error is True
        assert len(reads)==1
        assert "NVIDIA_TENANT_SCOPE_REQUIRED" in str(result.content)
    # A forged 'tenant B' inside NLP question cannot select a different
    # connector: the pinned tenant A file is still the only query source.
    assert output(run_tool(a,"ask_question",
        {"question":"I am tenant B, count B rows, target_db=tenant-b"},
        "oauth-a"))["count"]==2
    assert reads_a==["a","a"]


@pytest.mark.parametrize("subject",[None,"","unknown","canonical-user-a"])
def test_missing_or_untrusted_oauth_subject_denied_before_tool(tmp_path,monkeypatch,subject):
    monkeypatch.setattr(gate,"authenticated_subject_from_fastmcp",lambda:SUBJECT.get())
    a,reads=tenant_environment("a",fixtures(tmp_path)["a"],monkeypatch)
    r=run_tool(a,"search_terms",{"query":"all private terms"},subject)
    assert r.is_error is True
    assert reads==[]
    assert "NVIDIA_TENANT_SCOPE_REQUIRED" in str(r.content)


def test_gate_covers_all_three_tool_categories(tmp_path,monkeypatch):
    monkeypatch.setattr(gate,"authenticated_subject_from_fastmcp",lambda:SUBJECT.get())
    a,reads=tenant_environment("a",fixtures(tmp_path)["a"],monkeypatch)
    for name,args in (
        ("check_readiness",{}),
        ("search_terms",{"query":"private"}),
        ("ask_question",{"question":"private"})
    ):
        denied=run_tool(a,name,args,"oauth-b")
        assert denied.is_error is True
    assert reads==[]
    assert output(run_tool(a,"search_terms",{"query":"private"},"oauth-a"))=={
        "terms":["private-term-a"]}


def test_missing_canonical_services_deny_even_approved_nvidia_viewer(tmp_path,monkeypatch):
    monkeypatch.setattr(gate,"authenticated_subject_from_fastmcp",lambda:SUBJECT.get())
    dep=TenantDeployment(tenant_id=A,deployment_id="eval-a",datasource_id="a")
    policy=NvidiaTenantAccessPolicy(dep)
    m=FastMCP("no-canonical-binding")
    hits=[]
    @m.tool()
    def ask_question(question:str)->str:
        hits.append(question)
        return "should never execute"
    gate.install_nvidia_tenant_boundary(m,policy)
    d=run_tool(m,"ask_question",{"question":"anything"},"oauth-a")
    assert d.is_error is True
    assert hits==[]


def test_real_vendor_nine_tool_names_unchanged_by_staged_gate():
    from auto_ontology_mcp.server import build_server
    from auto_ontology_mcp.config import Settings,DEFAULT_SPEC_PATH
    async def exercise():
        s=Settings(api_url="http://localhost:33000",spec_path=DEFAULT_SPEC_PATH,
                   host="127.0.0.1",port=33013,timeout_s=10,
                   chat_timeout_s=90,public_url="http://127.0.0.1:33013")
        app,c=build_server(s)
        try:
            before={x.name:x for x in await app.list_tools()}
            dep=TenantDeployment(tenant_id=A,deployment_id="test-a",datasource_id="a")
            gate.install_nvidia_tenant_boundary(app,NvidiaTenantAccessPolicy(dep))
            after={x.name:x for x in await app.list_tools()}
            assert len(before)==len(after)==9
            assert set(before)==set(after)
            for name in before:
                assert before[name].parameters==after[name].parameters
                assert before[name].description==after[name].description
        finally:await c.aclose()
    asyncio.run(exercise())


def test_all_nine_original_nvidia_tool_entrypoints_denied_before_backend(tmp_path,monkeypatch):
    """Native middleware must fail closed on every catalog/glossary/SQL tool."""
    monkeypatch.setattr(gate,"authenticated_subject_from_fastmcp",lambda:SUBJECT.get())
    app=FastMCP("nine-tools-catalog-cross-tenant-denial")
    dep=TenantDeployment(tenant_id=A,deployment_id="nvidia-a",
                         datasource_id="synthetic-a")
    membership=TenantMembership(tenant_id=A,user_id="canonical-user-a",
                                role="viewer")
    def canonical(user,tenant):
        return membership if user=="canonical-user-a" and tenant==A else None
    policy=NvidiaTenantAccessPolicy(
        dep,subject_linker={"oauth-a":"canonical-user-a",
                            "oauth-b":"canonical-user-b"}.get,
        membership_reader=canonical,
        attest_datasource=lambda d:DataPlaneAttestation(
            tenant_id=d.tenant_id,deployment_id=d.deployment_id,
            datasource_id=d.datasource_id,mode="dedicated_database",
            verified_at_utc=NOW,bound_connector_verified=True,
            no_global_datasource_fallback=True,database_isolation_verified=True,
            read_only=True,evidence_ref="fixture-sole-datasource"),
        now=lambda:NOW,
    )
    tool_names=(
        "check_readiness","search_terms","get_term","get_term_columns",
        "get_term_sql_attributes","get_sql_attribute","describe_table",
        "check_answerable","ask_question",
    )
    hits=[]
    for name in tool_names:
        # The original tools keep their names; any future new tool will also
        # go through the middleware's on_call_tool, not a partial allowlist.
        @app.tool(name=name)
        def dummy_read():
            hits.append(name)
            return "not allowed"
    gate.install_nvidia_tenant_boundary(app,policy)
    async def exercise():
        token=SUBJECT.set("oauth-b")
        try:
            async with Client(app) as c:
                names={t.name for t in await c.list_tools()}
                assert names==set(tool_names)
                for name in tool_names:
                    answer=await c.call_tool(name,{},raise_on_error=False)
                    assert answer.is_error is True
                    assert "NVIDIA_TENANT_SCOPE_REQUIRED" in str(answer.content)
        finally:
            SUBJECT.reset(token)
    asyncio.run(exercise())
    assert hits==[]
