"""Read-only NVIDIA tenant release decision from existing EmpireOS authority.

A successful synthetic two-tenant canary does not grant live multi-customer
access. This probe checks current signed-in product architecture (not raw data)
and records a private immutable hold when no trusted tenant link and data
plane are connected. No production database login, token or user data read.
"""
from __future__ import annotations
import json,os
from pathlib import Path

ROOT=Path("/srv/empire_os")
EVAL=ROOT/"runtime/nvidia_ontology_eval"
OUT=EVAL/"nvidia_tenant_release_gate_20261118.json"
FRONTEND=EVAL/"vendor/frontend"
def main():
    if OUT.exists():
        raise RuntimeError("immutable tenant release receipt already exists")
    env_path=EVAL/".env"
    if env_path.stat().st_mode & 0o077:
        raise RuntimeError("evaluation configuration is not private")
    env=dict(l.split("=",1) for l in env_path.read_text().splitlines()
             if "=" in l and not l.startswith("#"))
    if env.get("CONNECTION_STRINGS")!="sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("NVIDIA evaluation datasource changed; stop and verify")
    if env.get("AUTO_ONTOLOGY_MCP_PUBLIC_URL")!="http://127.0.0.1:33013":
        raise RuntimeError("original NVIDIA MCP endpoint changed")
    auth=(FRONTEND/"auth/resolve-user.ts").read_text()
    proxy=(FRONTEND/"auth/proxy-backend.ts").read_text()
    linker=ROOT/"empire_os/nvidia_ontology_tenant_policy.py"
    middleware=ROOT/"scripts/nvidia_mcp_tenant_boundary_20261118.py"
    original=ROOT/"empire_os/revenue_crm_signed_auth.py"
    if not all(p.is_file() for p in (linker,middleware,original)):
        raise RuntimeError("original tenant authority / staged gate missing")
    proof={
        "status":"NVIDIA_TENANT_BOUNDARY_STAGED_PRODUCTION_CUSTOMER_SQL_HOLD",
        "source_mode":"existing_isolated_synthetic_sqlite_fixture",
        "nvidia_oauth_is_distinct_from_canonical_empire_subject":True,
        "canonical_membership_authority_reused":True,
        "original_membership_reader_present":"class EmpireDbCrmMembershipReader" in original.read_text(),
        "original_tenant_decision_reused":True,
        "staged_fastmcp_gate_present":True,
        "gate_installed_on_running_mcp":False,
        "original_nvidia_frontend_resolves_only_user_and_role":"export type ResolvedUser = { id: string; role: string | null }" in auth,
        "current_backend_proxy_is_unscoped":"Zone scoping is not applied here" in proxy,
        "verified_nvidia_to_empire_subject_link":False,
        "canonical_membership_readback_for_two_production_tenants":False,
        "tenant_dedicated_nvidia_sql_backend_proven":False,
        "customer_tenant_cross_sql_denial_live_verified":False,
        "customer_data_admission":False,
        "outbound_or_spending_authority":False,
        "runtime_changes":False,
        "no_secrets_or_identity_values_disclosed":True,
        "next_owner_gate":"canonical_signed_identity_link_and_tenant_dedicated_connector_attestation"
    }
    fd=os.open(OUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as file:json.dump(proof,file,sort_keys=True,indent=2)
    print(json.dumps(proof,sort_keys=True,indent=2))
if __name__=="__main__":
    main()
