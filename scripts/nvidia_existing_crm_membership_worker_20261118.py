"""Original canonical CRM membership probe for NVIDIA's staged tenant gate.

Called only by the existing EmpireOS adapter from a fixed binary/path.
Uses the founder-approved original CRM pilot private runtime + dedicated
membership-only PostgreSQL login. No memberships, passwords, keys, or tenant
identities are printed. Caller supplies exact subject and tenant for an
authoritative membership lookup, not a tenant binding or grant.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import UUID

from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader

ROOT=Path("/var/lib/empire-crm-first-party")
CONFIG=ROOT/"pilot-runtime.json"
PASSFILE=ROOT/"pgpass"


def _private(path:Path)->bool:
    import pwd
    uid=pwd.getpwnam("ubuntu").pw_uid
    return (path.is_file() and not path.is_symlink()
            and path.stat().st_uid==uid
            and path.stat().st_mode & 0o077 == 0)


def probe() -> dict:
    if not all(_private(x) for x in (CONFIG,PASSFILE)):
        return {"verified":False}
    try:
        raw=sys.stdin.buffer.read(1025)
        if len(raw)>1024:
            return {"verified":False}
        args=json.loads(raw)
        if not isinstance(args,dict) or set(args)!={"subject","tenant_id"}:
            return {"verified":False}
        subject=args["subject"];tenant=args["tenant_id"]
        if (not isinstance(subject,str) or not subject
            or len(subject)>128 or subject.strip()!=subject
            or not isinstance(tenant,str)
            or str(UUID(tenant))!=tenant):
            return {"verified":False}
        config=json.loads(CONFIG.read_text())
        dsn=config.get("membership_dsn")
        if (config.get("schema_version")!="empire.crm.pilot_runtime.v1"
            or not isinstance(dsn,str)
            or dsn!="host=/var/run/postgresql port=5432 dbname=empiredb user=empire_crm_membership_login"):
            return {"verified":False}
        os.environ["PGPASSFILE"]=str(PASSFILE)
        member=EmpireDbCrmMembershipReader(dsn)(subject,tenant)
        if (member is None or member.user_id!=subject
            or member.tenant_id!=tenant
            or not member.can("read")):
            return {"verified":False}
        return {"verified":True,"role":member.role}
    except Exception:
        return {"verified":False}


def main():
    # Status only. No subject, tenant ID, DSN, keys or SQL in stdout/stderr.
    result=probe()
    sys.stdout.write(json.dumps(result,separators=(",",":"))+"\n")
    return 0 if result.get("verified") is True else 2


if __name__=="__main__":
    raise SystemExit(main())
