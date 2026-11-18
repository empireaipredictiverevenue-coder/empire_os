"""Actual staged two-tenant NVIDIA private fixture and Compose readbacks."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
import yaml

from empire_os.nvidia_dedicated_compose import (
    DedicatedNvidiaStack,compile_isolated_original_compose,
    validate_disjoint_stacks,
)

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
STAGE=ROOT/"two_tenant_canary_20261118"
RECORD=STAGE/"stage_verified_final_paths_v2.json"
TENANTS=(
    ("a","10000000-0000-4000-8000-000000000001",33100,33500,2),
    ("b","20000000-0000-4000-8000-000000000002",33101,33501,7),
)

def staged():
    if not RECORD.exists():
        pytest.skip("staged private NVIDIA two-tenant canary not on this host")
    assert STAGE.is_dir() and not STAGE.is_symlink()
    assert STAGE.stat().st_mode&0o077==0
    assert RECORD.stat().st_mode&0o077==0
    receipt=json.loads(RECORD.read_text())
    assert receipt["both_compose_projects_validated_from_final_paths"] is True
    assert receipt["containers_started"] is False
    assert receipt["production_data_admitted"] is False
    return receipt

def test_two_real_canary_sources_are_separate_sqlite_databases():
    staged()
    for label,_id,_front,_mcp,count in TENANTS:
        file=STAGE/f"tenant_{label}"/f"source_{label}.sqlite"
        assert file.stat().st_mode&0o077==0
        with sqlite3.connect("file:"+str(file)+"?mode=ro",uri=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            assert conn.execute("SELECT COUNT(*) FROM nvidia_tenant_isolation_canary"
                                " WHERE tenant_marker=?",(label,)).fetchone()[0]==count
            other="b" if label=="a" else "a"
            assert conn.execute("SELECT COUNT(*) FROM nvidia_tenant_isolation_canary"
                                " WHERE tenant_marker=?",(other,)).fetchone()[0]==0

def test_original_vendor_stack_compiled_at_actual_staged_final_paths():
    receipt=staged()
    instances=[]
    for label,tenant,frontend,mcp,count in TENANTS:
        dir=STAGE/f"tenant_{label}"
        env=dir/"tenant.env"
        source=dir/f"source_{label}.sqlite"
        config=dir/"compose.yaml"
        assert all(p.is_file() and p.stat().st_mode&0o077==0
                   for p in (env,source,config))
        stack=DedicatedNvidiaStack(tenant_id=tenant,
            project=f"nvidia-tenant-{label}-20261118",
            env_file=env,sqlite_file=source,
            frontend_port=frontend,mcp_port=mcp,
            source_digest=hashlib.sha256(source.read_bytes()).hexdigest())
        expected=compile_isolated_original_compose(ROOT/"compose.yaml",stack)
        assert yaml.safe_load(config.read_text())==expected
        assert receipt["tenants"][label]["source_path_is_final"] is True
        assert receipt["tenants"][label]["env_path_is_final"] is True
        assert receipt["tenants"][label]["manifest_sha256"]==hashlib.sha256(config.read_bytes()).hexdigest()
        instances.append(stack)
    validate_disjoint_stacks(*instances)

def test_docker_compose_static_validation_no_runtime_deployment():
    staged()
    for label,*_ in TENANTS:
        dir=STAGE/f"tenant_{label}"
        r=subprocess.run(["docker","compose","--env-file",str(dir/"tenant.env"),
            "-f",str(dir/"compose.yaml"),"config","--quiet"],
            capture_output=True,text=True,timeout=30)
        assert r.returncode==0

def test_canonical_pinned_image_and_host_loopback_policies():
    staged()
    for label,*_ in TENANTS:
        manifest=yaml.safe_load((STAGE/f"tenant_{label}"/"compose.yaml").read_text())
        services=manifest["services"]
        assert services["auto-ontology"]["image"]=="empire-nvidia-ontology-eval:3825917"
        assert services["auto-ontology-frontend"]["image"]=="empire-nvidia-ontology-frontend-eval:3825917"
        assert manifest["networks"]["sandbox"]["internal"] is True
        assert all(p.startswith("127.0.0.1:") for p in services["auto-ontology-frontend"]["ports"])
        assert services["postgres"]["ports"]==[]
        assert services["ingestion-service"]["ports"]==[]
        assert services["auto-ontology"]["ports"]==[]
