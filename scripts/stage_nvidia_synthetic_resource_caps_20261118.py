"""Bounded synthetic-only memory overlays for already-verified NVIDIA projects.

Only service mem_limit fields vary from original vendor Compose. Immutable
private test-only files; original production/evaluation Compose is unchanged.
No daemon calls, containers, keys or customer data accessed.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE=ROOT/"two_tenant_canary_20261118"
RECEIPT=BASE/"resource_caps_v1.json"
LIMITS={
    "postgres":"1g",
    "auto-ontology":"3g",
    "ingestion-service":"2g",
    "auto-ontology-frontend":"2g",
}


def pure_override():
    return {"services":{name:{"mem_limit":size} for name,size in LIMITS.items()}}


def check_cap_contract(candidate,original):
    if candidate!=pure_override():
        raise ValueError("synthetic resource overlay has unapproved extra fields")
    before=original["services"]
    for name,size in LIMITS.items():
        old=before[name].get("mem_limit")
        if old is None or not isinstance(old,str) or not old.endswith("g"):
            raise ValueError("original NVIDIA memory cap missing")
        if int(size[:-1])>int(old[:-1]):
            raise ValueError("canary cap exceeded original memory cap")


def write_once(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:f.write(data)


def main():
    if RECEIPT.exists():
        raise RuntimeError("existing capacity receipt must not be overwritten")
    orig=yaml.safe_load((ROOT/"compose.yaml").read_text())
    check_cap_contract(pure_override(),orig)
    written=[]
    for label in ("a","b"):
        folder=BASE/f"tenant_{label}"
        env=folder/"tenant.env"
        base=folder/"compose.yaml"
        overlay=folder/"resource_caps.yaml"
        if not all(p.is_file() and p.stat().st_mode&0o077==0
                   for p in (env,base)):
            raise RuntimeError("original private stage not validated")
        if overlay.is_symlink():
            raise RuntimeError("resource overlay symlink forbidden")
        if overlay.exists():
            if overlay.stat().st_mode & 0o077 or yaml.safe_load(overlay.read_text())!=pure_override():
                raise RuntimeError("existing overlay differs from exact approved test ceiling")
        else:
            data=yaml.safe_dump(pure_override(),sort_keys=False)
            write_once(overlay,data)
            written.append(overlay)
        if yaml.safe_load(overlay.read_text())!=pure_override():
            raise RuntimeError("resource overlay readback mismatch")
        cmd=["/usr/bin/docker","compose","--env-file",str(env),
             "-f",str(base),"-f",str(overlay),"config","--quiet"]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
        if result.returncode!=0:
            raise RuntimeError("Docker Compose rejected synthetic-only memory override")
        final=yaml.safe_load(subprocess.run(
            ["/usr/bin/docker","compose","--env-file",str(env),
             "-f",str(base),"-f",str(overlay),"config"],
            capture_output=True,text=True,timeout=35,check=True,
        ).stdout)
        for name,size in LIMITS.items():
            # Docker Compose converts human-friendly cap to SI byte count.
            mem=final["services"][name].get("mem_limit")
            if not isinstance(mem,(int,str)) or not str(mem).isdigit() or int(mem)>int(size[:-1])*1024**3:
                raise RuntimeError("actual merged resource cap higher than reviewed")
    report={
        "classification":"NVIDIA_TWO_TENANT_RESOURCE_CAPPED_SYNTHETIC_CANARY_V1",
        "only_memory_limits_modified":True,
        "separate_overlay_per_tenant":True,
        "pinned_original_service_images":True,
        "unchanged_original_vendor_compose":True,
        "existing_synthetic_sources_preserved":True,
        "per_tenant_memory_gib":sum(int(x[:-1]) for x in LIMITS.values()),
        "required_two_tenant_memory_gib_including_8g_reserve":
            2*sum(int(x[:-1]) for x in LIMITS.values())+8,
        "caps":LIMITS,
        "manifest_sha256":{label:hashlib.sha256(
            (BASE/f"tenant_{label}"/"resource_caps.yaml").read_bytes()
        ).hexdigest() for label in ("a","b")},
        "docker_daemon_used":False,
        "containers_started":False,
        "production_access_granted":False,
    }
    write_once(RECEIPT,json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({
        "status":report["classification"],
        "per_tenant_memory_gib":report["per_tenant_memory_gib"],
        "required_host_available_memory_gib":
            report["required_two_tenant_memory_gib_including_8g_reserve"],
        "staged_validated":True,
        "containers_started":False,
        "customer_access_granted":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
