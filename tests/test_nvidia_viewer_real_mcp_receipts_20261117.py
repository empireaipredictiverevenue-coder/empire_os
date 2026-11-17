"""Read-only first-party NVIDIA MCP acceptance and failure-gate readbacks."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"runtime/nvidia_ontology_eval"
VIEWER=RUNTIME/"nvidia_viewer_real_mcp_tools_20261117.json"
NLP=RUNTIME/"nvidia_viewer_mcp_real_question_20261117.json"
AGENT=RUNTIME/"opencode_nvidia_real_agent_tool_attestation_20261117.json"
LOG=RUNTIME/"opencode_free_model_nvidia_viewer_agent_20261117.jsonl"
ENV=RUNTIME/".env"

def private_json(path:Path):
    if not path.exists():pytest.skip("runtime receipt only on EmpireOS")
    assert path.stat().st_mode & 0o077 == 0
    return json.loads(path.read_text())

def test_viewer_oauth_authorized_and_native_read_tools_returned():
    r=private_json(VIEWER)
    assert r["source"]=="EXISTING_OPENCODE_V2_AUTHORIZED_VIEWER_GRANT"
    assert r["synthetic_only"] is True
    assert r["oauth_userinfo_http"]==200
    assert r["userinfo_has_subject"] is True
    assert r["tool_count"]==9
    assert r["curated_tool_set_exact"] is True
    assert not r["check_readiness"]["mcp_is_error"]
    assert not r["search_terms"]["mcp_is_error"]
    assert r["viewer_readonly_mcp_acceptance"] is True

def test_admin_routes_refuse_existing_viewer_and_no_secret_dump():
    r=private_json(VIEWER)
    assert r["admin_denials"]["invitations"]["http"]==403
    assert r["admin_denials"]["user_admin"]["http"] in (401,403)
    assert all(x["denied"] for x in r["admin_denials"].values())
    assert r["token_disclosed"] is False
    assert r["new_credentials_created"] is False
    assert r["production_data_sent"] is False

def test_free_agent_did_invoke_exact_nvidia_readiness_tool():
    a=private_json(AGENT)
    assert a["result"]=="EXISTING_OPENCODE_V2_NVIDIA_CHECK_READINESS_REAL_TOOL_VERIFIED"
    assert a["verification_pass"] is True
    assert a["actual_invoked_tool"]=="nvidia-auto-ontology.check_readiness"
    assert a["tool_wrapper"]=="execute"
    assert a["tool_exact_single_call"] is True
    assert a["tool_completed"] is True
    assert a["other_tools_invoked"] is False
    assert a["opencode_model"]=="opencode/glm-5.3-flash-free"
    assert a["viewer_oauth_reused"] is True
    assert a["no_new_inference"] is True
    if not LOG.is_file():pytest.skip("OpenCode session event log only on EmpireOS")
    events=[json.loads(x) for x in LOG.read_text().splitlines()]
    calls=[d["part"] for d in events if d.get("type")=="tool_use"]
    assert len(calls)==1
    assert calls[0]["tool"]=="execute"
    assert calls[0]["state"]["status"]=="completed"
    assert calls[0]["state"]["input"]["code"]==(
        'return await tools["nvidia-auto-ontology"].check_readiness({})'
    )
    data=json.loads(calls[0]["state"]["output"])
    assert data["semantic_layer_built"] is True
    assert data["catalog_present"] is True
    assert data["databases"]==["empire_graph"]

def test_empty_sql_answer_remains_release_hold():
    d=private_json(NLP)
    assert d["scope"]=="EXISTING_AUTHORIZED_OPENCODE_VIEWER_VIA_NATIVE_MCP"
    assert d["actual_mcp_tool"]=="ask_question"
    assert d["is_error"] is False
    assert d["generated_sql_present"] is False
    assert d["actual_database_rows_present"] is False
    assert d["actual_count"] is None
    assert d["expected_count"]==2
    assert d["verified"] is False
    assert d["customer_data_sent"] is False

def test_env_connection_exists_while_ui_list_is_known_incomplete():
    a=private_json(AGENT)
    assert a["tool_result_semantic_layer_built"] is True
    assert a["tool_result_catalog_present"] is True
    assert a["tool_result_can_execute_sql"] is False
    if not ENV.exists():pytest.skip("private isolated evaluation environment only")
    assert ENV.stat().st_mode & 0o077 == 0
    env=dict(line.split("=",1) for line in ENV.read_text().splitlines()
             if "=" in line and not line.startswith("#"))
    assert env["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
    assert env["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]=="http://127.0.0.1:33013"

def test_private_receipts_contain_no_oauth_token_fields():
    for path in (VIEWER,NLP,AGENT):
        d=private_json(path)
        for key in d:
            assert key not in {"access","refresh","password","authorization","client_secret","cookie"}
        dump=json.dumps(d).lower()
        assert "bearer " not in dump
        assert "sk-" not in dump
