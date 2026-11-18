"""Prepare two isolated NVIDIA Auto Ontology tenants for guarded Docker canary.

Uses the original pinned Compose + first-party isolated synthetic graph.
Creates separate valid SQLite databases, random private auth/database secrets,
per-tenant config and bounded Docker Compose manifests. Does NOT contact the
Docker daemon, spawn containers, publish ports or infer an OAuth tenant link.
No new model provider or paid model. Never prints .env secrets.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import yaml

from empire_os.nvidia_dedicated_compose import (
    DedicatedNvidiaStack,
    compile_isolated_original_compose,
    validate_disjoint_stacks,
)

ROOT=Path("/srv/empire_os")
BASE=ROOT/"runtime/nvidia_ontology_eval"
SOURCE=BASE/"empire_graph.sqlite"
ORIGINAL_ENV=BASE/".env"
COMPOSE=BASE/"compose.yaml"
DEST=BASE/"two_tenant_canary_20261118"
TENANTS=(
    ("a","10000000-0000-4000-8000-000000000001",33100,33500,2),
    ("b","20000000-0000-4000-8000-000000000002",33101,33501,7),
)
SECRET_KEYS=("AUTH_SECRET","POSTGRES_PASSWORD",
             "AUTO_ONTOLOGY_ADMIN_PASSWORD","PGADMIN_PASSWORD")


def private_file(path:Path):
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise RuntimeError("private source file required")


def source_env()->dict[str,str]:
    private_file(ORIGINAL_ENV)
    parsed={}
    for line in ORIGINAL_ENV.read_text().splitlines():
        if not line or line.startswith("#"):continue
        if "=" not in line:raise RuntimeError("original env malformed")
        k,v=line.split("=",1)
        if k in parsed:raise RuntimeError("duplicate original configuration")
        parsed[k]=v
    expected_free=("REASONING_MODEL","NON_REASONING_MODEL","DEFAULT_MODELS_MODEL")
    if not all(str(parsed.get(x,"")).endswith(":free") for x in expected_free):
        raise RuntimeError("unapproved or paid inference model; stage held")
    if parsed.get("CONNECTION_STRINGS")!="sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("original synthetic datasource changed")
    if parsed.get("APP_URL")!="http://localhost:33000":
        raise RuntimeError("original NVIDIA issuer changed")
    return parsed


def sqlite_tenant_fixture(path:Path,marker:str,count:int):
    # sqlite backup avoids modifying the owner/source file and is robust to
    # SQLite journals. New tables are only for synthetic isolation canaries.
    with sqlite3.connect("file:"+SOURCE.as_posix()+"?mode=ro",uri=True) as original:
        with sqlite3.connect(path) as copy:
            original.backup(copy)
            if copy.execute(
                "SELECT count(*) FROM sqlite_master WHERE name=?",
                ("nvidia_tenant_isolation_canary",)
            ).fetchone()[0]!=0:
                raise RuntimeError("canary table already exists in source")
            copy.execute(
                "CREATE TABLE nvidia_tenant_isolation_canary ("
                "record_key INTEGER PRIMARY KEY, tenant_marker TEXT NOT NULL)"
            )
            copy.executemany(
                "INSERT INTO nvidia_tenant_isolation_canary (tenant_marker) "
                "VALUES (?)", [(marker,)]*count
            )
            copy.commit()
            assert copy.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    path.chmod(0o600)


def prep_one(stage:Path,base:dict[str,str],label:str,tenant:str,
             frontend:int,mcp:int,count:int)->tuple[DedicatedNvidiaStack,dict]:
    folder=stage/("tenant_"+label)
    folder.mkdir(mode=0o700)
    db=folder/("source_"+label+".sqlite")
    sqlite_tenant_fixture(db,label,count)
    environment=dict(base)
    for name in SECRET_KEYS:environment[name]=secrets.token_urlsafe(48)
    environment.update({
        "POSTGRES_USER":"nvidia_canary_"+label,
        "POSTGRES_DATABASE":"nvidia_canary_"+label,
        "AUTO_ONTOLOGY_ADMIN_EMAIL":"nvidia-canary-"+label+"@example.invalid",
        "PGADMIN_EMAIL":"pgadmin-"+label+"@example.invalid",
        "APP_URL":f"http://localhost:{frontend}",
        "AUTO_ONTOLOGY_MCP_PUBLIC_URL":f"http://127.0.0.1:{mcp}",
        "CONNECTION_STRINGS":"sqlite:////reference/empire_graph.sqlite",
    })
    envfile=folder/"tenant.env"
    envfile.write_text("\n".join(f"{k}={v}" for k,v in environment.items())+"\n")
    envfile.chmod(0o600)
    project=f"nvidia-tenant-{label}-20261118"
    digest=hashlib.sha256(db.read_bytes()).hexdigest()
    stack=DedicatedNvidiaStack(
        tenant_id=tenant,project=project,env_file=envfile,sqlite_file=db,
        frontend_port=frontend,mcp_port=mcp,source_digest=digest,
    )
    manifest=folder/"compose.yaml"
    manifest.write_text(yaml.safe_dump(
        compile_isolated_original_compose(COMPOSE,stack),
        sort_keys=False,
    ))
    manifest.chmod(0o600)
    proc=subprocess.run(
        ["docker","compose","--env-file",str(envfile),"-f",str(manifest),
         "config","--quiet"],capture_output=True,text=True,timeout=35
    )
    if proc.returncode!=0:
        raise RuntimeError("Docker Compose rejected staged isolated tenant")
    with sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True) as conn:
        actual=conn.execute(
            "SELECT count(*) FROM nvidia_tenant_isolation_canary"
            " WHERE tenant_marker=?",(label,)
        ).fetchone()[0]
        opposite=conn.execute(
            "SELECT count(*) FROM nvidia_tenant_isolation_canary"
            " WHERE tenant_marker=?",("b" if label=="a" else "a",)
        ).fetchone()[0]
    if actual!=count or opposite!=0:
        raise RuntimeError("independent synthetic tenant fixture mismatch")
    return stack,{
        "project":project,"fixture_row_count":actual,
        "opposite_tenant_rows":opposite,
        "original_compose_cli_syntax_verified":True,
        "frontend_loopback_port":frontend,"mcp_loopback_port":mcp,
        "source_sha256":digest,
        "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "separate_private_configuration":True,
    }


def main():
    old_umask=os.umask(0o077)
    stage=None
    try:
        if DEST.exists() or DEST.is_symlink():
            raise RuntimeError("canary destination exists, do not overwrite")
        private_file(SOURCE)
        baseline=source_env()
        # Compose paths must refer to the FINAL immutable private directory.
        # Creating there (with rollback-on-error below) prevents stale temp
        # paths when a completed candidate is renamed into place.
        DEST.mkdir(mode=0o700)
        stage=DEST
        stacks=[]
        details={}
        for label,tenant,frontend,mcp,count in TENANTS:
            s,meta=prep_one(stage,baseline,label,tenant,frontend,mcp,count)
            stacks.append(s);details[label]=meta
        validate_disjoint_stacks(*stacks)
        for k in SECRET_KEYS:
            values=[]
            for s in stacks:
                d=dict(line.split("=",1) for line in s.env_file.read_text().splitlines()
                       if "=" in line)
                values.append(d[k])
            if len(set(values))!=2:
                raise RuntimeError("canary isolation secret reuse")
        report={
            "classification":"TWO_TENANT_NVIDIA_PRIVATE_SYNTHETIC_DOCKER_CANARY_STAGED",
            "source":"existing NVIDIA pinned vendor stack + synthetic owner graph",
            "two_distinct_tenant_projects":True,
            "two_distinct_sqlite_datasources":True,
            "two_distinct_postgres_volumes":True,
            "two_distinct_nvidia_auth_stores":True,
            "secrets_independently_generated":True,
            "provider_free_models_only":True,
            "no_new_model_provider":True,
            "manifest_cli_validation_pass":True,
            "tenants":details,
            "docker_daemon_contacted":False,
            "containers_started":False,
            "o_auth_subject_crosswalk_issued":False,
            "live_sql_tenant_isolation_verified":False,
            "customer_data_admitted":False,
            "post_stage_privileged_release_required":True,
            "no_credentials_reported":True,
        }
        receipt=stage/"stage_receipt.json"
        receipt.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
        receipt.chmod(0o600)
        stage=None  # Complete at the verified final path, not a moved temp path.
        print(json.dumps({
            "status":report["classification"],
            "projects":{k:v["project"] for k,v in details.items()},
            "synthetic_counts":{k:v["fixture_row_count"] for k,v in details.items()},
            "cli_validated":True,"independent_secrets":True,
            "containers_started":False,"production_data_admitted":False,
            "no_credentials_reported":True,
        },sort_keys=True))
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)
        os.umask(old_umask)


if __name__=="__main__":
    main()
