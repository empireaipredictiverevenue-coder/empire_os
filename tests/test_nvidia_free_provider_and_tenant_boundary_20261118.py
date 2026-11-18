"""Read-only acceptance receipts: current free route and tenant hold."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"runtime/nvidia_ontology_eval"
FRONTEND=RUNTIME/"vendor/frontend"
CODE='const r = await tools["nvidia-auto-ontology"].check_readiness();\nreturn r;'

def _private_json(name):
    p=RUNTIME/name
    if not p.exists(): pytest.skip("Private EmpireOS runtime evidence unavailable")
    assert p.stat().st_mode & 0o077 == 0
    return json.loads(p.read_text())

def test_current_free_model_is_real_agent_mcp_execution():
    d=_private_json("opencode_current_free_model_nvidia_mcp_attestation_20261118.json")
    assert d["verified"] is True
    assert d["model"]=="opencode/mimo-v2.6-flash-free"
    assert d["single_agent_tool_event"] is True
    assert d["tool_completed"] is True
    assert d["actual_nvidia_call"]=="nvidia-auto-ontology.check_readiness"
    assert d["readiness_ready"] is True
    assert d["service_or_default_model_modified"] is False
    assert d["other_tools_invoked"] is False
    assert d["no_token_disclosure"] is True

def test_original_opencode_event_has_one_safe_readiness_tool_only():
    p=RUNTIME/"opencode_mimo_free_route_nvidia_viewer_20261118.jsonl"
    if not p.is_file(): pytest.skip("No private OpenCode events")
    assert p.stat().st_mode & 0o077 == 0
    events=[]
    for ln in p.read_text().splitlines():
        try:events.append(json.loads(ln))
        except (ValueError,TypeError):continue
    calls=[e["part"] for e in events if e.get("type")=="tool_use"]
    assert len(calls)==1
    assert calls[0]["tool"]=="execute"
    st=calls[0]["state"]
    assert st["status"]=="completed"
    assert st["input"]["code"]==CODE
    payload=json.loads(st["output"])
    assert payload["ready"] is True
    assert payload["databases"]==["empire_graph"]
    assert payload["can_execute_sql"] is True

def test_existing_two_identity_conversation_access_is_restricted():
    r=_private_json("nvidia_two_identity_readonly_isolation_20261118.json")
    assert r["two_distinct_users_exist"] is True
    assert r["writes_performed"] is False
    assert r["customer_data_accessed"] is False
    assert r["admin_conversations_http"]==200
    assert r["viewer_conversations_http"]==200
    assert r["conversation_list_overlap_count"]==0
    assert r["admin_own_conversation_http"]==200
    assert r["viewer_foreign_conversation_http"]==404
    assert r["cross_user_private_conversation_denied"] is True

def test_shared_catalogue_is_explicit_tenant_release_hold():
    r=_private_json("nvidia_two_identity_readonly_isolation_20261118.json")
    assert r["shared_catalogue_admin_http"]==200
    assert r["shared_catalogue_viewer_http"]==200
    assert r["shared_catalogue_same_names"] is True
    assert r["admin_catalogue_database_count"]==r["viewer_catalogue_database_count"]==1
    assert r["distinct_tenant_contexts_verified"] is False
    assert r["production_sql_tenant_isolation_verified"] is False
    assert r["status"]=="USER_CONVERSATIONS_SEPARATE_GLOBAL_CATALOGUE_NOT_TENANT_BOUNDARY"

def test_source_of_truth_carries_user_identity_not_tenant_id():
    a=(FRONTEND/"auth/resolve-user.ts").read_text()
    b=(FRONTEND/"auth/proxy-backend.ts").read_text()
    c=(FRONTEND/"lib/internalIdentity.ts").read_text()
    route=(FRONTEND/"app/api/conversations/[id]/route.ts").read_text()
    assert "export type ResolvedUser = { id: string; role: string | null }" in a
    assert "Zone scoping is not applied here" in b
    assert "default (unscoped)" in b
    assert "buildInternalIdentityHeaders = (userId: string)" in c
    assert "where: { id, user_id: user.id }" in route
    assert "tenant_id" not in c
    assert "tenantId" not in c

def test_no_production_sql_isolation_claim_and_synthetic_receipt_pass():
    previous=_private_json("nvidia_viewer_six_real_mcp_sql_20261118.json")
    assert previous["sample"]=="synthetic_empire_graph_only"
    assert previous["total_cases"]==previous["passed_count"]==6
    assert previous["all_verified"] is True
    assert previous["target_db_override_used"] is False
    r=_private_json("nvidia_two_identity_readonly_isolation_20261118.json")
    assert r["production_sql_tenant_isolation_verified"] is False
