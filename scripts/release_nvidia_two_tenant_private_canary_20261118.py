"""Guarded founder-operated two-NVIDIA-tenant synthetic Docker canary.

Preflight is read-only, safe under the original ubuntu account. The sole
write action is an explicit root-only --apply-founder-approved, which
reuses two already-generated original NVIDIA Compose manifests and their
existing cached images; never builds/pulls images or restarts the original.
On failure only these newly created synthetic projects are taken down.
No customer data, account link, new provider or paid model execution.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import pwd
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from scripts.verify_nvidia_two_tenant_running_20261118 import inspect_live
from scripts.stage_nvidia_synthetic_resource_caps_20261118 import (
    LIMITS,pure_override,check_cap_contract,
)
BASE=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
STAGE=BASE/"two_tenant_canary_20261118"
TENANTS=(
    ("a","10000000-0000-4000-8000-000000000001",33100,33500,2),
    ("b","20000000-0000-4000-8000-000000000002",33101,33501,7),
)
from empire_os.nvidia_dedicated_compose import (
    DedicatedNvidiaStack,validate_disjoint_stacks,
)
import hashlib

RECEIPT=STAGE/"guarded_synthetic_docker_release_v1.json"
DOCKER="/usr/bin/docker"
CACHED_IMAGES=(
    "empire-nvidia-ontology-eval:3825917",
    "empire-nvidia-ontology-frontend-eval:3825917",
    "pgvector/pgvector:pg17",
)

def call(*argv,timeout=80):
    result=subprocess.run(argv,stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,timeout=timeout,
                          check=False)
    if result.returncode!=0:
        raise RuntimeError("guarded command failed")
    return result.returncode

def compose(label,*args):
    folder=STAGE/("tenant_"+label)
    project=f"nvidia-tenant-{label}-20261118"
    return (DOCKER,"compose","--project-name",project,
            "--env-file",str(folder/"tenant.env"),
            "-f",str(folder/"compose.yaml"),
            "-f",str(folder/"resource_caps.yaml"),*args)

def health(port:int):
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/health",
            timeout=5
        ) as response:
            if response.status!=200:return False
            payload=json.loads(response.read(4096))
            return payload.get("status")=="ok" and (
                payload.get("postgres") or {}).get("status")=="ok"
    except Exception:
        return False

def original_mcp_pid():
    """Exact original live service process, not an inferred success flag."""
    target=[b"/srv/empire_os/runtime/nvidia_ontology_eval/.mcp_venv/bin/python",
            b"-B",
            b"/srv/empire_os/scripts/nvidia_mcp_verified_issuer_20261117.py"]
    matches=[]
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():continue
        try:
            command=(path/"cmdline").read_bytes().rstrip(bytes([0])).split(bytes([0]))
        except (OSError,PermissionError):continue
        if command==target:matches.append(int(path.name))
    if len(matches)!=1:
        raise RuntimeError("exact original NVIDIA MCP owner process unavailable")
    return matches[0]


def free_port(port):
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:sock.bind(("127.0.0.1",port))
    except OSError as exc:raise RuntimeError("protected port in use") from exc
    finally:sock.close()

def required_memory_budget():
    """Two pinned synthetic resource overlays plus 8 GiB safety margin."""
    import yaml
    original=yaml.safe_load((BASE/"compose.yaml").read_text())
    check_cap_contract(pure_override(),original)
    return (2*sum(int(v[:-1]) for v in LIMITS.values())+8)*1024**3


def preflight(*,require_resource_headroom=True):
    if RECEIPT.exists():
        raise RuntimeError("existing canary release receipt; no second deployment")
    receipt=STAGE/"stage_verified_final_paths_v2.json"
    if not receipt.is_file() or receipt.is_symlink() or receipt.stat().st_mode & 0o077:
        raise RuntimeError("private verified stage unavailable")
    d=json.loads(receipt.read_text())
    if (d.get("classification")!="NVIDIA_TWO_TENANT_CANARY_FINAL_PATH_RECONCILED_V2"
        or d.get("both_compose_projects_validated_from_final_paths") is not True
        or d.get("containers_started") is not False):
        raise RuntimeError("unverified immutable synthetic stage")
    if not health(33000):
        raise RuntimeError("original NVIDIA frontend unhealthy")
    req=urllib.request.Request(
        "http://127.0.0.1:33013/.well-known/oauth-protected-resource/mcp"
    )
    with urllib.request.urlopen(req,timeout=8) as response:
        metadata=json.loads(response.read(4096))
    if metadata.get("authorization_servers")!=["http://localhost:33000/api/auth"]:
        raise RuntimeError("original OAuth issuer changed")
    resource_receipt=STAGE/"resource_caps_v1.json"
    if (not resource_receipt.is_file() or resource_receipt.is_symlink()
        or resource_receipt.stat().st_mode & 0o077):
        raise RuntimeError("reviewed synthetic memory overlays required")
    cap_evidence=json.loads(resource_receipt.read_text())
    if (cap_evidence.get("classification")!="NVIDIA_TWO_TENANT_RESOURCE_CAPPED_SYNTHETIC_CANARY_V1"
        or cap_evidence.get("caps")!=LIMITS):
        raise RuntimeError("canary resource budget evidence changed")
    import yaml
    stacks=[]
    for label,tenant,front,mcp,expected in TENANTS:
        folder=STAGE/("tenant_"+label)
        src=folder/("source_"+label+".sqlite")
        stack=DedicatedNvidiaStack(
            tenant_id=tenant,project=f"nvidia-tenant-{label}-20261118",
            env_file=folder/"tenant.env",sqlite_file=src,
            frontend_port=front,mcp_port=mcp,
            source_digest=hashlib.sha256(src.read_bytes()).hexdigest())
        stack.check()
        stacks.append(stack)
        overlay=folder/"resource_caps.yaml"
        if (not overlay.is_file() or overlay.is_symlink()
            or overlay.stat().st_mode & 0o077
            or yaml.safe_load(overlay.read_text())!=pure_override()
            or hashlib.sha256(overlay.read_bytes()).hexdigest()!=
               cap_evidence["manifest_sha256"][label]):
            raise RuntimeError("canary-only resource caps drifted")
        call(DOCKER,"compose","--env-file",str(stack.env_file),
             "-f",str(folder/"compose.yaml"),
             "-f",str(overlay),"config","--quiet",timeout=25)
        for port in (front,mcp):free_port(port)
    validate_disjoint_stacks(*stacks)
    mem={}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k,sep,v=line.partition(":")
        if sep and k=="MemAvailable":
            mem[k]=int(v.strip().split()[0])*1024
    required=required_memory_budget()
    if require_resource_headroom and mem.get("MemAvailable",0)<required:
        raise RuntimeError("insufficient available memory for two native NVIDIA stacks")
    st=os.statvfs(str(STAGE))
    if st.f_frsize*st.f_bavail<8*1024**3:
        raise RuntimeError("less than 8 GiB free disk, canary release held")
    return {
        "original_health_preserved":True,
        "original_mcp_pid":original_mcp_pid(),
        "static_compose_candidate_verified":True,
        "two_private_tenant_sources_pinned":True,
        "tenant_ports_available":True,
        "available_host_memory_preflight":mem.get("MemAvailable",0)>=required,
        "required_memory_gib":required//(1024**3),
        "observed_available_memory_gib":mem.get("MemAvailable",0)//(1024**3),
        "no_original_service_mutation":True,
        "customer_data_admission":False,
    }

def check_docker_runtime_empty():
    call(DOCKER,"info",timeout=20)
    for image in CACHED_IMAGES:
        call(DOCKER,"image","inspect",image,timeout=25)
    for label,*_ in TENANTS:
        project=f"nvidia-tenant-{label}-20261118"
        # Existing containers/volumes/networks are never reused or removed.
        for typ in ("container","volume","network"):
            r=subprocess.run(
                [DOCKER,typ,"ls",*(["--all"] if typ=="container" else []),"--filter",
                 f"label=com.docker.compose.project={project}",
                 "--format","{{.ID}}" if typ!="volume" else "{{.Name}}"],
                capture_output=True,text=True,timeout=15,check=False)
            if r.returncode!=0 or r.stdout.strip():
                raise RuntimeError("Docker project resources already exist")

def write_receipt(payload):
    fd=os.open(RECEIPT,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        f.write(json.dumps(payload,sort_keys=True,indent=2)+"\n")
        user=pwd.getpwnam("ubuntu")
        os.fchown(f.fileno(),user.pw_uid,user.pw_gid)

def rollback_only_new(started):
    for label in reversed(started):
        try:call(*compose(label,"down"),timeout=70)
        except Exception:pass

def activate():
    if os.geteuid()!=0:
        raise PermissionError("founder-operated root Docker activation required")
    if not STAGE.is_dir() or STAGE.is_symlink():
        raise RuntimeError("staging paths changed")
    import fcntl
    lockfd=os.open("/run/lock/nvidia-tenant-synthetic-20261118.lock",
                   os.O_CREAT|os.O_RDWR,0o600)
    try:
        fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=preflight()
        check_docker_runtime_empty()
        started=[]
        try:
            for label,*_ in TENANTS:
                started.append(label)
                call(*compose(label,"up","-d","--no-build","--pull","never"),
                     timeout=170)
            until=time.monotonic()+145
            while time.monotonic()<until:
                if all(health(front) for _label,_tenant,front,_mcp,_count in TENANTS):
                    break
                time.sleep(3)
            else:
                raise RuntimeError("tenant frontends did not reach health")
            result=inspect_live()
            if not health(33000) or original_mcp_pid()!=before["original_mcp_pid"]:
                raise RuntimeError("original shared NVIDIA service changed")
            result.update(before)
            result["guarded_docker_release_pass"]=True
            result["service_change_scope"]="new synthetic tenant projects only"
            result["original_services_restarted"]=False
            result["customer_data_admission"]=False
            result["signed_identity_link_issued"]=False
            result["semantic_tenant_nlp_canary_pending"]=True
            write_receipt(result)
        except Exception:
            rollback_only_new(started)
            raise
        print(json.dumps({
            "status":result["status"],
            "two_private_tenant_stacks_running":True,
            "synthetic_mount_sql_proof":True,
            "production_customer_access":False,
            "original_nvidia_service_untouched":True,
            "identity_link_still_required":True,
        },sort_keys=True))
    finally:
        os.close(lockfd)

def main():
    p=argparse.ArgumentParser()
    options=p.add_mutually_exclusive_group(required=True)
    options.add_argument("--check",action="store_true")
    options.add_argument("--apply-founder-approved",action="store_true")
    a=p.parse_args()
    try:
        if a.check:
            print(json.dumps({"status":"NVIDIA_TWO_TENANT_PRIVATE_DOCKER_PREFLIGHT_PASS",
                              **preflight()},sort_keys=True))
        else:activate()
    except Exception as exc:
        if isinstance(exc,RuntimeError) and (
            str(exc)=="insufficient available memory for two native NVIDIA stacks"
        ):
            available=0
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    available=int(line.split()[1])*1024
                    break
            print(json.dumps({
                "status":"NVIDIA_TWO_TENANT_MEMORY_SAFETY_HOLD",
                "required_available_gib":required_memory_budget()//(1024**3),
                "observed_available_gib":available//(1024**3),
                "original_nvidia_untouched":True,
                "customer_data_access":False,
                "containers_launched":False,
            },sort_keys=True))
        else:
            print("NVIDIA_TWO_TENANT_GUARDED_RELEASE_HOLD:"+type(exc).__name__,
                  file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
