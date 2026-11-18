"""Read-only original EmpireDB CRM membership adapter for NVIDIA MCP.

The original CRM membership owner uses a different dependency environment
(FastAPI and psycopg). Call it in its pinned virtualenv as a bounded local
child, under the SAME unprivileged ubuntu UID. No secondary auth source:
the worker delegates to original EmpireDbCrmMembershipReader and the
dedicated original membership-only PostgreSQL login, never a privileged
database user or caller-selected DSN.

This adapter is imported into the original isolated FastMCP runtime when
the approved tenant identity/data plane bindings are activated. Importing
it does not grant access, initiate any login, or enable any customer data.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from uuid import UUID

from empire_os.saas_scale import TenantMembership

ROOT=Path("/srv/empire_os")
BINARY=ROOT/".venv/bin/python"
WORKER=ROOT/"scripts/nvidia_existing_crm_membership_worker_20261118.py"
MAX_REPLY_BYTES=256
VALID_SUBJECT=re.compile(r"^[A-Za-z0-9:@._/-]{1,128}$")
VALID_ROLE=frozenset({"owner","admin","operator","analyst","viewer"})


class ExistingCrmMembershipAdapter:
    """Adapter to canonical CRM membership; no cache, fail closed every read."""

    def __init__(self,runner=None):
        self._runner=runner or subprocess.run

    def __call__(self,user_id:str,tenant_id:str)->TenantMembership|None:
        if (not isinstance(user_id,str) or not VALID_SUBJECT.fullmatch(user_id)
            or ".." in user_id or user_id.startswith(("/", "."))):
            return None
        if not isinstance(tenant_id,str):
            return None
        try:
            if str(UUID(tenant_id))!=tenant_id:
                return None
        except (ValueError,TypeError,AttributeError):
            return None
        if (not BINARY.is_file() or not WORKER.is_file()
            or WORKER.is_symlink()):
            return None
        args=json.dumps({"subject":user_id,"tenant_id":tenant_id},
                        separators=(",",":"))
        # No credentials in argv, env or output; the worker loads original
        # private CRM config and password file under its existing ownership.
        environ={
            "PATH":"/usr/bin:/bin",
            "LANG":"C.UTF-8",
            "PYTHONDONTWRITEBYTECODE":"1",
            "HOME":"/home/ubuntu",
        }
        try:
            proc=self._runner(
                [str(BINARY),"-B","-m",
                 "scripts.nvidia_existing_crm_membership_worker_20261118"],
                input=args,cwd=str(ROOT),env=environ,
                capture_output=True,text=True,timeout=6,check=False,
            )
            if proc.returncode!=0 or len(proc.stdout)>MAX_REPLY_BYTES:
                return None
            reply=json.loads(proc.stdout)
            if (not isinstance(reply,dict)
                or set(reply)!={"verified","role"}
                or reply.get("verified") is not True
                or reply.get("role") not in VALID_ROLE):
                return None
            member=TenantMembership(
                tenant_id=tenant_id,user_id=user_id,
                role=reply["role"],status="active")
            return member if member.can("read") else None
        except (OSError,ValueError,subprocess.TimeoutExpired):
            return None
