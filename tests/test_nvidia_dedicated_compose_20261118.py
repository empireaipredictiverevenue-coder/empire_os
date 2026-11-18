"""Two independent copies of the original NVIDIA Compose data-plane layout.

No Docker daemon is required and no containers are deployed. Assertions
cover dedicated PostgreSQL volumes, private auth secrets, internal networks,
one tenant SQLite bind and loopback-only frontage, rejecting shared/global
resources and unapproved source changes.
"""
from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace
from pathlib import Path
import pytest
import yaml

from empire_os.nvidia_dedicated_compose import (
    DedicatedNvidiaStack,compile_isolated_original_compose,
    validate_disjoint_stacks,
)
from empire_os.nvidia_ontology_tenant_policy import NvidiaTenantDenied

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/"runtime/nvidia_ontology_eval/compose.yaml"
TENANT_A="10000000-0000-4000-8000-000000000001"
TENANT_B="20000000-0000-4000-8000-000000000002"

def build(tmp_path,tag,tenant,frontend,mcp):
    folder=tmp_path/f"tenant_{tag}"
    folder.mkdir(mode=0o700)
    src=folder/f"source_{tag}.sqlite"
    # Static file (not source material from a customer).
    src.write_bytes(b"SQLite-synthetic-source-"+tag.encode())
    src.chmod(0o600)
    env=folder/"tenant.env"
    env.write_text("\n".join([
        f"POSTGRES_USER=tenant_{tag}",
        f"POSTGRES_PASSWORD=independent-postgres-secret-{tag}-isolated",
        f"POSTGRES_DATABASE=tenantdb_{tag}",
        f"AUTH_SECRET=independent-oauth-secret-{tag}-isolated",
        f"AUTO_ONTOLOGY_ADMIN_PASSWORD=independent-bootstrap-secret-{tag}-isolated",
        f"AUTO_ONTOLOGY_ADMIN_EMAIL=admin-{tag}@example.invalid",
        f"CONNECTION_STRINGS=sqlite:////reference/empire_graph.sqlite",
        f"APP_URL=http://localhost:{frontend}",
        f"AUTO_ONTOLOGY_MCP_PUBLIC_URL=http://127.0.0.1:{mcp}",
        f"REASONING_MODEL=openai/nvidia/nemotron-3.5-super-vl:free",
    ])+"\n")
    env.chmod(0o600)
    return DedicatedNvidiaStack(tenant_id=tenant,
        project=f"nvidia-tenant-{tag}-20261118",
        env_file=env,sqlite_file=src,
        frontend_port=frontend,mcp_port=mcp,
        source_digest=hashlib.sha256(src.read_bytes()).hexdigest())

@pytest.fixture
def pair(tmp_path):
    return (
        build(tmp_path,"a",TENANT_A,33100,33500),
        build(tmp_path,"b",TENANT_B,33101,33501),
    )

def test_two_tenant_original_stack_resources_are_physical_disjoint(pair):
    a,b=pair
    validate_disjoint_stacks(a,b)
    compiled=[compile_isolated_original_compose(ORIGINAL,x) for x in pair]
    assert compiled[0]["name"]!=compiled[1]["name"]
    assert compiled[0]["networks"]["sandbox"]["internal"] is True
    for i,config in enumerate(compiled):
        stack=pair[i]
        assert config["services"]["auto-ontology-frontend"]["ports"]==[
            f"127.0.0.1:{stack.frontend_port}:3000"]
        assert all(service.get("env_file")==[str(stack.env_file)]
                   for service in config["services"].values()
                   if "env_file" in service)
        for service_name in ("auto-ontology","ingestion-service"):
            volume=config["services"][service_name]["volumes"][0]
            assert volume["source"]==str(stack.sqlite_file)
            assert volume["read_only"] is True
            assert volume["target"]=="/reference/empire_graph.sqlite"
        assert config["services"]["postgres"]["volumes"]==[
            "postgres_data:/var/lib/postgresql/data"]
        assert "external" not in config["networks"]["sandbox"]
        assert config["volumes"]["postgres_data"] is None
    assert compiled[0]["services"]["auto-ontology"]["volumes"][0]["source"]!=(
        compiled[1]["services"]["auto-ontology"]["volumes"][0]["source"])

def test_original_docker_compose_parser_accepts_both_isolated_candidates(pair,tmp_path):
    for i,stack in enumerate(pair):
        manifest=compile_isolated_original_compose(ORIGINAL,stack)
        path=tmp_path/f"dedicated-candidate-{i}.yaml"
        path.write_text(yaml.safe_dump(manifest,sort_keys=False))
        path.chmod(0o600)
        result=subprocess.run(
            ["docker","compose","--env-file",str(stack.env_file),
             "-f",str(path),"config","--quiet"],
            cwd=str(tmp_path),capture_output=True,text=True,timeout=30,
        )
        assert result.returncode==0, "docker compose rejected isolated candidate"
        # No daemon access / no deployment.

@pytest.mark.parametrize("mutation",[
    "same_tenant","same_project","same_frontend","same_mcp",
    "same_env","same_source","same_postgres_secret","same_auth_secret",
    "same_admin_secret"
])
def test_shared_cross_tenant_resource_or_secret_denied(pair,mutation):
    a,b=pair
    if mutation=="same_tenant": b=replace(b,tenant_id=a.tenant_id)
    if mutation=="same_project": b=replace(b,project=a.project)
    if mutation=="same_frontend": b=replace(b,frontend_port=a.frontend_port)
    if mutation=="same_mcp": b=replace(b,mcp_port=a.mcp_port)
    if mutation=="same_env": b=replace(b,env_file=a.env_file)
    if mutation=="same_source": b=replace(
        b,sqlite_file=a.sqlite_file,source_digest=a.source_digest)
    if "secret" in mutation:
        key={
            "same_postgres_secret":"POSTGRES_PASSWORD",
            "same_auth_secret":"AUTH_SECRET",
            "same_admin_secret":"AUTO_ONTOLOGY_ADMIN_PASSWORD",
        }[mutation]
        config_a=dict(x.split("=",1) for x in a.env_file.read_text().splitlines())
        config_b=dict(x.split("=",1) for x in b.env_file.read_text().splitlines())
        config_b[key]=config_a[key]
        b.env_file.write_text("\n".join(f"{k}={v}" for k,v in config_b.items())+"\n")
    with pytest.raises(NvidiaTenantDenied):
        validate_disjoint_stacks(a,b)


def test_global_unscoped_fallback_rejected(pair):
    a,_=pair
    env=a.env_file.read_text().replace(
        "CONNECTION_STRINGS=sqlite:////reference/empire_graph.sqlite",
        "CONNECTION_STRINGS=sqlite:////reference/empire_graph.sqlite,postgresql://shared/global")
    a.env_file.write_text(env)
    with pytest.raises(NvidiaTenantDenied):
        compile_isolated_original_compose(ORIGINAL,a)

def test_wrong_fixture_digest_refuses_source_swap(pair):
    a,_=pair
    a.sqlite_file.write_bytes(b"replaced without owner approval")
    with pytest.raises(NvidiaTenantDenied):
        compile_isolated_original_compose(ORIGINAL,a)

def test_world_readable_config_and_symlink_source_denied(pair,tmp_path):
    a,_=pair
    a.env_file.chmod(0o644)
    with pytest.raises(NvidiaTenantDenied):
        compile_isolated_original_compose(ORIGINAL,a)
    a.env_file.chmod(0o600)
    link=tmp_path/"symlink.sqlite"
    link.symlink_to(a.sqlite_file)
    with pytest.raises(NvidiaTenantDenied):
        compile_isolated_original_compose(ORIGINAL,replace(a,sqlite_file=link))

def test_original_compose_shared_volume_or_network_drift_denied(pair,tmp_path):
    a,_=pair
    baseline=yaml.safe_load(ORIGINAL.read_text())
    for field in ("volumes","networks"):
        doc=yaml.safe_load(ORIGINAL.read_text())
        name="postgres_data" if field=="volumes" else "sandbox"
        doc[field][name]={"external":True}
        altered=tmp_path/f"modified-{field}.yaml"
        altered.write_text(yaml.safe_dump(doc))
        with pytest.raises(NvidiaTenantDenied):
            compile_isolated_original_compose(altered,a)

def test_unverified_tenant_isolation_is_not_proven_by_valid_compose(pair):
    from empire_os.nvidia_ontology_tenant_policy import NvidiaTenantAccessPolicy,TenantDeployment
    a,_=pair
    manifest=compile_isolated_original_compose(ORIGINAL,a)
    assert manifest["name"]==a.project
    # There is no attestation of a *running* backend, no signed identity
    # crosswalk, and no original canonical reader mounted into FastMCP.
    policy=NvidiaTenantAccessPolicy(TenantDeployment(a.tenant_id,a.project,a.sqlite_file.name))
    with pytest.raises(NvidiaTenantDenied):
        policy.authorize("unbound-nvidia-user")
