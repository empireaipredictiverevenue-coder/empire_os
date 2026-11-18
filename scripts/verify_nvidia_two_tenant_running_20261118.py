"""Verify real Docker execution separation for two original NVIDIA canaries.

Runs ONLY after the founder-controlled guarded Docker launch. Reads Docker
container metadata and executes SELECTs against the originally mounted
read-only SQLite connector path inside each existing NVIDIA backend worker.
Never opens application credentials, executes untrusted SQL, or reads customer
data. Does not certify semantic/NLP or cross-user production isolation.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from empire_os.nvidia_dedicated_compose import (
    DedicatedNvidiaStack,compile_isolated_original_compose,validate_disjoint_stacks,
)
import hashlib
from scripts.stage_nvidia_synthetic_resource_caps_20261118 import LIMITS

BASE=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
STAGE=BASE/"two_tenant_canary_20261118"
NAMES=(("a","10000000-0000-4000-8000-000000000001",33100,33500,2),
       ("b","20000000-0000-4000-8000-000000000002",33101,33501,7))


def docker(*args:str)->str:
    result=subprocess.run(["/usr/bin/docker",*args],capture_output=True,
                           text=True,timeout=30,check=False)
    if result.returncode:
        raise RuntimeError("protected Docker readback failed")
    return result.stdout.strip()


def _stack(label,tenant,frontend,mcp):
    folder=STAGE/("tenant_"+label)
    fixture=folder/f"source_{label}.sqlite"
    env=folder/"tenant.env"
    stack=DedicatedNvidiaStack(
        tenant_id=tenant,project=f"nvidia-tenant-{label}-20261118",
        env_file=env,sqlite_file=fixture,
        frontend_port=frontend,mcp_port=mcp,
        source_digest=hashlib.sha256(fixture.read_bytes()).hexdigest(),
    )
    stack.check()
    return stack


def _container(project,service,env,manifest):
    output=docker("compose","--project-name",project,"--env-file",str(env),
                  "-f",str(manifest),"ps","-q",service)
    ids=[x.strip() for x in output.splitlines() if x.strip()]
    if len(ids)!=1:
        raise RuntimeError("expected exactly one private container")
    return ids[0]


def inspect_live():
    if os.geteuid()!=0:
        raise PermissionError("guarded Docker operator privilege required")
    if not (STAGE/"stage_verified_final_paths_v2.json").is_file():
        raise RuntimeError("staged verified private manifests required")
    stacks=[_stack(*row[:4]) for row in NAMES]
    validate_disjoint_stacks(*stacks)
    for stack in stacks:
        manifest=STAGE/("tenant_"+stack.project.split("-")[2])/"compose.yaml"
        if not manifest.is_file():
            raise RuntimeError("private Compose manifest missing")
        import yaml
        if yaml.safe_load(manifest.read_text())!=compile_isolated_original_compose(BASE/"compose.yaml",stack):
            raise RuntimeError("original pinned Compose manifest drift")
    expected_networks=[]
    results={}
    for label,tenant,frontend,mcp,count in NAMES:
        stack=_stack(label,tenant,frontend,mcp)
        folder=STAGE/f"tenant_{label}"
        manifest=folder/"compose.yaml"
        backend=_container(stack.project,"auto-ontology",stack.env_file,manifest)
        front=_container(stack.project,"auto-ontology-frontend",stack.env_file,manifest)
        postgres=_container(stack.project,"postgres",stack.env_file,manifest)
        ingestion=_container(stack.project,"ingestion-service",stack.env_file,manifest)
        # Check effective Docker limits, not merely the static Compose input.
        for name,container in (
            ("postgres",postgres),("auto-ontology",backend),
            ("ingestion-service",ingestion),("auto-ontology-frontend",front),
        ):
            actual=docker("inspect","--format","{{.HostConfig.Memory}}",container)
            expected=int(LIMITS[name][:-1])*1024**3
            if not actual.isdigit() or int(actual)!=expected:
                raise RuntimeError("tenant canary runtime memory limit diverged")
        labels=json.loads(docker("inspect","--format","{{json .Config.Labels}}",backend))
        if labels.get("com.docker.compose.project")!=stack.project:
            raise RuntimeError("backend project label mismatch")
        mounts=json.loads(docker("inspect","--format","{{json .Mounts}}",backend))
        fixture_matches=[
            x for x in mounts
            if x.get("Destination")=="/reference/empire_graph.sqlite"
            and x.get("Source")==str(stack.sqlite_file)
            and x.get("RW") is False
            and x.get("Type")=="bind"
        ]
        if len(fixture_matches)!=1:
            raise RuntimeError("actual backend tenant source is not pinned read-only")
        networks=json.loads(docker("inspect","--format","{{json .NetworkSettings.Networks}}",backend))
        seen=set(networks)
        if seen!={stack.project+"_sandbox"}:
            raise RuntimeError("NVIDIA backend crossed tenant Docker network")
        expected_networks.append(seen)
        pg_mounts=json.loads(docker("inspect","--format","{{json .Mounts}}",postgres))
        if not any(
            x.get("Name")==stack.project+"_postgres_data"
            and x.get("Destination")=="/var/lib/postgresql/data"
            for x in pg_mounts
        ):
            raise RuntimeError("Postgres volume not unique to tenant project")
        ports=json.loads(docker("inspect","--format","{{json .NetworkSettings.Ports}}",front))
        entry=ports.get("3000/tcp")
        if (not isinstance(entry,list) or len(entry)!=1
            or entry[0].get("HostIp")!="127.0.0.1"
            or str(entry[0].get("HostPort"))!=str(frontend)):
            raise RuntimeError("frontend not bound to protected loopback port")
        query=(
            "import sqlite3,json;"
            "db=sqlite3.connect('file:/reference/empire_graph.sqlite?mode=ro',uri=True);"
            "a=db.execute('SELECT tenant_marker,COUNT(*) FROM "
            "nvidia_tenant_isolation_canary GROUP BY tenant_marker').fetchall();"
            "print(json.dumps(a))"
        )
        records=json.loads(docker("exec",backend,"python","-B","-c",query))
        if records!=[[label,count]]:
            raise RuntimeError("actual SQL in backend container accessed unexpected tenant data")
        results[label]={
            "actual_container_sql_rows":count,
            "other_tenant_rows":0,
            "single_exact_read_only_fixture_mount":True,
            "isolated_docker_network":True,
            "isolated_postgres_volume":True,
            "loopback_only_frontend":True,
            "real_container_memory_caps_enforced":True,
        }
    if expected_networks[0] & expected_networks[1]:
        raise RuntimeError("tenant Docker networks overlap")
    return {
        "status":"TWO_NVIDIA_SYNTHETIC_CONTAINER_SQL_SOURCES_ISOLATED",
        "original_vendor_compose_reused":True,
        "projects":results,
        "no_cross_tenant_mounted_rows":True,
        "customer_data_admitted":False,
        "signed_identity_crosswalk_issued":False,
        "semantic_nlp_cross_tenant_verified":False,
        "production_tenant_sql_approved":False,
    }


if __name__=="__main__":
    print(json.dumps(inspect_live(),sort_keys=True,indent=2))
