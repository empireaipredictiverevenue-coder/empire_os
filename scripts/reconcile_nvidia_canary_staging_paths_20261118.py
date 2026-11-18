"""One-time bounded repair and final-path readback of staged NVIDIA canaries.

The first private stage created valid data and secrets, but manifests
contained absolute paths from the temporary build directory. Preserve the
existing private files and secrets, rewrite only the generated Compose
manifests from the trusted pinned original; validate those files in place.
Create a distinct immutable v2 receipt without erasing earlier evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml

from empire_os.nvidia_dedicated_compose import (
    DedicatedNvidiaStack,compile_isolated_original_compose,validate_disjoint_stacks
)

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
DEST=ROOT/"two_tenant_canary_20261118"
OUT=DEST/"stage_verified_final_paths_v2.json"
TENANTS=(
    ("a","10000000-0000-4000-8000-000000000001",33100,33500,2),
    ("b","20000000-0000-4000-8000-000000000002",33101,33501,7),
)

def main():
    if OUT.exists():raise RuntimeError("final-path v2 receipt already exists")
    if DEST.is_symlink() or not DEST.is_dir() or DEST.stat().st_mode&0o077:
        raise RuntimeError("staging root is not a private owned directory")
    original=json.loads((DEST/"stage_receipt.json").read_text())
    if original.get("classification")!="TWO_TENANT_NVIDIA_PRIVATE_SYNTHETIC_DOCKER_CANARY_STAGED":
        raise RuntimeError("original staged candidate identity changed")
    compiled={}
    stacks=[]
    for label,tenant,frontend,mcp,count in TENANTS:
        folder=DEST/f"tenant_{label}"
        env=folder/"tenant.env"
        fixture=folder/f"source_{label}.sqlite"
        manifest=folder/"compose.yaml"
        if any(not p.is_file() or p.is_symlink() or p.stat().st_mode&0o077
               for p in (env,fixture,manifest)):
            raise RuntimeError("private staged files missing")
        previous=yaml.safe_load(manifest.read_text())
        if not isinstance(previous,dict) or previous.get("name")!=f"nvidia-tenant-{label}-20261118":
            raise RuntimeError("prior private generated manifest not original")
        digest=hashlib.sha256(fixture.read_bytes()).hexdigest()
        if digest!=original["tenants"][label]["source_sha256"]:
            raise RuntimeError("existing fixture changed, do not repair")
        stack=DedicatedNvidiaStack(tenant_id=tenant,
            project=f"nvidia-tenant-{label}-20261118",env_file=env,
            sqlite_file=fixture,frontend_port=frontend,mcp_port=mcp,
            source_digest=digest)
        expected=compile_isolated_original_compose(ROOT/"compose.yaml",stack)
        # Compare the earlier material except absolute manifest source/env path.
        previous_normalized=json.loads(json.dumps(previous))
        for service_name,service in previous_normalized["services"].items():
            if "env_file" in service:
                old=service["env_file"]
                if (not isinstance(old,list) or len(old)!=1
                    or Path(old[0]).name!="tenant.env"
                    or not old[0].startswith(str(ROOT)+"/nvidia-private-canary-")):
                    raise RuntimeError("unexpected original env path drift")
                service["env_file"]=[str(env)]
            if service_name in ("auto-ontology","ingestion-service"):
                old=service["volumes"][0]["source"]
                if (Path(old).name!=fixture.name
                    or not old.startswith(str(ROOT)+"/nvidia-private-canary-")):
                    raise RuntimeError("unexpected original SQLite path drift")
                service["volumes"][0]["source"]=str(fixture)
        if previous_normalized!=expected:
            raise RuntimeError("generated Compose contents drift beyond moved paths")
        stacks.append(stack)
        compiled[label]=(manifest,expected,env,digest,count)
    validate_disjoint_stacks(*stacks)
    # All verification completed before writing the two exact manifests.
    receipt={
        "classification":"NVIDIA_TWO_TENANT_CANARY_FINAL_PATH_RECONCILED_V2",
        "unmodified_tenant_secrets":True,
        "unmodified_tenant_sqlite_sources":True,
        "manifest_diff_only_path_retarget":True,
        "both_compose_projects_validated_from_final_paths":False,
        "containers_started":False,
        "production_data_admitted":False,
        "original_stage_receipt_preserved":True,
        "tenants":{},
    }
    for label,(manifest,expected,env,digest,count) in compiled.items():
        manifest.write_text(yaml.safe_dump(expected,sort_keys=False))
        manifest.chmod(0o600)
        parsed=yaml.safe_load(manifest.read_text())
        if parsed!=expected:raise RuntimeError("final manifest readback failed")
        cmd=["docker","compose","--env-file",str(env),"-f",str(manifest),
             "config","--quiet"]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
        if result.returncode!=0:
            raise RuntimeError("Docker Compose rejected final-path candidate")
        receipt["tenants"][label]={
            "project":expected["name"],
            "sqlite_sha256":digest,
            "synthetic_rows":count,
            "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "env_path_is_final":all(
                f["env_file"]==[str(env)] for f in expected["services"].values()
                if "env_file" in f
            ),
            "source_path_is_final":all(
                expected["services"][name]["volumes"][0]["source"]==
                str(DEST/f"tenant_{label}"/f"source_{label}.sqlite")
                for name in ("auto-ontology","ingestion-service")
            ),
            "docker_compose_config_exit_zero":True,
        }
    receipt["both_compose_projects_validated_from_final_paths"]=True
    fd=os.open(OUT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps({
        "classification":receipt["classification"],
        "compilation_valid":True,
        "both_final_paths_verified":True,
        "source_and_secret_reused":True,
        "containers_started":False,
        "production_data_admitted":False,
    },sort_keys=True))

if __name__=="__main__":
    main()
