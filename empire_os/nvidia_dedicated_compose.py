"""Tenant-dedicated deployments of the EXISTING NVIDIA Auto Ontology stack.

No new platform: clone the pinned original Compose architecture to an
independent per-tenant project, private authentication store, PostgreSQL
volume, networking, and exactly one tenant-specific SQLite bind mount.
This builds a reviewed candidate only. It never launches containers or
claims the actual backend has been deployed.

Use the original data-owner's verified connector and founder release
approval for deployment; a successful static Compose test alone is not
SQL tenant-isolation proof.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
import hmac
import re

import yaml

from empire_os.nvidia_ontology_tenant_policy import NvidiaTenantDenied

BASE_PROJECT="empire-nvidia-ontology-eval"
SERVICES=frozenset({
    "postgres","pgadmin","auto-ontology","ingestion-service",
    "auto-ontology-migrate","frontend-migrate","auto-ontology-frontend",
})
SOURCE_SERVICES=frozenset({"auto-ontology","ingestion-service"})
SECRET_KEYS=("AUTH_SECRET","POSTGRES_PASSWORD","AUTO_ONTOLOGY_ADMIN_PASSWORD")
REQUIRED_KEYS=set(SECRET_KEYS)|{
    "POSTGRES_USER","POSTGRES_DATABASE","CONNECTION_STRINGS","APP_URL",
    "REASONING_MODEL","AUTO_ONTOLOGY_MCP_PUBLIC_URL",
}


def _private_file(path:Path):
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
        or path.stat().st_mode & 0o077):
        raise NvidiaTenantDenied("PRIVATE_TENANT_SOURCE_OR_CONFIG_REQUIRED")


def _env(path:Path)->dict[str,str]:
    _private_file(path)
    out={}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise NvidiaTenantDenied("MALFORMED_TENANT_CONFIGURATION")
        k,v=line.split("=",1)
        if k in out or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}",k):
            raise NvidiaTenantDenied("DUPLICATE_TENANT_CONFIG_KEY")
        out[k]=v
    if not REQUIRED_KEYS.issubset(out):
        raise NvidiaTenantDenied("TENANT_CONFIG_INCOMPLETE")
    if any(len(out[k])<16 for k in SECRET_KEYS):
        raise NvidiaTenantDenied("WEAK_OR_MISSING_TENANT_SECRET")
    return out


@dataclass(frozen=True)
class DedicatedNvidiaStack:
    tenant_id:str
    project:str
    env_file:Path
    sqlite_file:Path
    frontend_port:int
    mcp_port:int
    source_digest:str

    def check(self)->None:
        import hashlib
        if (str(UUID(self.tenant_id))!=self.tenant_id
            or not re.fullmatch(r"nvidia-tenant-[a-z0-9-]{8,46}",self.project)):
            raise NvidiaTenantDenied("INVALID_TENANT_DEPLOYMENT_IDENTIFIERS")
        if not (33080<=self.frontend_port<=33399
                and 33400<=self.mcp_port<=33799):
            raise NvidiaTenantDenied("TENANT_PORT_OUT_OF_ISOLATED_RANGE")
        if self.frontend_port==self.mcp_port:
            raise NvidiaTenantDenied("TENANT_PORT_COLLISION")
        _private_file(self.env_file)
        _private_file(self.sqlite_file)
        if self.sqlite_file.suffix!=".sqlite":
            raise NvidiaTenantDenied("TENANT_SQLITE_SOURCE_REQUIRED")
        if hashlib.sha256(self.sqlite_file.read_bytes()).hexdigest()!=self.source_digest:
            raise NvidiaTenantDenied("TENANT_SOURCE_DIGEST_MISMATCH")
        current=_env(self.env_file)
        expected="sqlite:////reference/empire_graph.sqlite"
        if current["CONNECTION_STRINGS"]!=expected:
            raise NvidiaTenantDenied("TENANT_MUST_HAVE_EXACTLY_ONE_PINNED_SQLITE_SOURCE")
        if current["APP_URL"]!=f"http://localhost:{self.frontend_port}":
            raise NvidiaTenantDenied("TENANT_OWN_FRONTEND_ISSUER_REQUIRED")
        if current["AUTO_ONTOLOGY_MCP_PUBLIC_URL"]!=f"http://127.0.0.1:{self.mcp_port}":
            raise NvidiaTenantDenied("TENANT_OWN_MCP_RESOURCE_REQUIRED")


def validate_disjoint_stacks(a:DedicatedNvidiaStack,b:DedicatedNvidiaStack)->None:
    for stack in (a,b):stack.check()
    if (a.tenant_id==b.tenant_id
        or a.project==b.project
        or a.frontend_port==b.frontend_port
        or a.mcp_port==b.mcp_port
        or a.env_file.resolve()==b.env_file.resolve()
        or a.sqlite_file.resolve()==b.sqlite_file.resolve()):
        raise NvidiaTenantDenied("TENANT_DEPLOYMENT_OVERLAP")
    env_a=_env(a.env_file)
    env_b=_env(b.env_file)
    for key in SECRET_KEYS:
        if hmac.compare_digest(env_a[key],env_b[key]):
            raise NvidiaTenantDenied("TENANT_CREDENTIAL_REUSE")
    # Shared *inference service* may be explicitly approved separately,
    # but each tenant must have its own auth/DB secrets and data store.


def compile_isolated_original_compose(
    original_path:Path,stack:DedicatedNvidiaStack
)->dict:
    """Pure candidate compilation: do not spawn Docker or write secrets."""
    stack.check()
    raw=yaml.safe_load(original_path.read_text())
    if not isinstance(raw,dict) or raw.get("name")!=BASE_PROJECT:
        raise NvidiaTenantDenied("NVIDIA_ORIGINAL_STACK_NOT_PINNED")
    services=raw.get("services")
    if not isinstance(services,dict) or set(services)!=SERVICES:
        raise NvidiaTenantDenied("NVIDIA_ORIGINAL_STACK_CHANGED")
    networks=raw.get("networks")
    if not isinstance(networks,dict) or networks.get("sandbox",{}).get("internal") is not True:
        raise NvidiaTenantDenied("NVIDIA_ISOLATED_NETWORK_EXPECTED")
    copy=deepcopy(raw)
    copy["name"]=stack.project
    for name,service in copy["services"].items():
        if "env_file" in service:
            service["env_file"]=[str(stack.env_file)]
        # No service may expose a public host interface.
        if name=="auto-ontology-frontend":
            service["ports"]=[f"127.0.0.1:{stack.frontend_port}:3000"]
        elif "ports" in service:
            if service["ports"]:
                raise NvidiaTenantDenied("UNEXPECTED_SHARED_HOST_PORTS")
            service["ports"]=[]
        if name in SOURCE_SERVICES:
            mounts=service.get("volumes")
            if not isinstance(mounts,list) or len(mounts)!=1:
                raise NvidiaTenantDenied("SINGLE_TENANT_SOURCE_MOUNT_REQUIRED")
            original=mounts[0]
            if (original.get("type")!="bind"
                or original.get("target")!="/reference/empire_graph.sqlite"
                or original.get("read_only") is not True):
                raise NvidiaTenantDenied("ORIGINAL_READ_ONLY_SQLITE_MOUNT_CHANGED")
            service["volumes"]=[{
                "type":"bind","source":str(stack.sqlite_file),
                "target":"/reference/empire_graph.sqlite",
                "read_only":True,
            }]
        elif any(
            isinstance(m,dict) and m.get("type")=="bind"
            for m in service.get("volumes",[])
        ):
            raise NvidiaTenantDenied("UNEXPECTED_OTHER_TENANT_BIND_MOUNT")
    volumes=copy.get("volumes")
    if not isinstance(volumes,dict) or "postgres_data" not in volumes:
        raise NvidiaTenantDenied("ORIGINAL_POSTGRES_VOLUME_MISSING")
    if any(isinstance(x,dict) and (x.get("external") or x.get("name"))
           for x in volumes.values()):
        raise NvidiaTenantDenied("SHARED_EXTERNAL_VOLUME_NOT_ALLOWED")
    if any(isinstance(x,dict) and (x.get("external") or x.get("name"))
           for x in networks.values()):
        raise NvidiaTenantDenied("SHARED_EXTERNAL_NETWORK_NOT_ALLOWED")
    return copy
