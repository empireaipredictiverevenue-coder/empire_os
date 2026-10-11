#!/usr/bin/env python3
"""Read-only actual three-login proof after a committed CRM database transaction.

Never mutates canonical credential file or EmpireDB. Creates and removes a
temporary mode-0600 passfile with compatible host aliases, inside the
private service-account-owned directory. Prints only classified outcomes.
"""
from __future__ import annotations

import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tempfile

from scripts.repair_crm_login_passfile_lookup import (
    DIR, PASSFILE, ROLES, SOCKET, TENANT, inspect, patched,
)

def classify(stderr: str) -> str:
    message = str(stderr).lower()
    if "no password supplied" in message or "password is required" in message:
        return "PASSWORD_LOOKUP_MISSING"
    if "password authentication failed" in message:
        return "PASSWORD_REJECTED"
    if "role" in message and "not permitted to log in" in message:
        return "ROLE_NOT_LOGIN"
    if "permission denied for database" in message:
        return "DATABASE_CONNECT_DENIED"
    if "permission denied for schema" in message:
        return "SCHEMA_USAGE_DENIED"
    if "permission denied for table" in message:
        return "TABLE_PRIVILEGE_DENIED"
    if "permission denied" in message:
        return "OTHER_PERMISSION_DENIED"
    if "connection refused" in message or "no such file" in message:
        return "DATABASE_CONNECTION_UNAVAILABLE"
    if "could not translate" in message:
        return "INVALID_SOCKET_TARGET"
    return "UNCLASSIFIED_DATABASE_ERROR"


def psql(role: str, command: str, password_file: Path) -> tuple[int,str,str]:
    if role not in ROLES:
        raise ValueError("unapproved database role")
    env=dict(os.environ)
    env.pop("PGPASSWORD",None)
    env["PGPASSFILE"]=str(password_file)
    env["PGCONNECT_TIMEOUT"]="5"
    r=subprocess.run([
        "psql","-X","-w","-q","-At","-v","ON_ERROR_STOP=1",
        "-h",SOCKET,"-p","5432","-U",role,"-d","empiredb",
        "-c",command,
    ],env=env,capture_output=True,text=True,timeout=9)
    return r.returncode,r.stdout.strip(),classify(r.stderr)


def report(password_file: Path) -> dict[str,str]:
    result={}
    for role in ROLES:
        code,identity,reason=psql(role,"BEGIN READ ONLY; SELECT session_user; ROLLBACK;",password_file)
        result[role]="PASS" if code==0 and identity==role else (
            reason if code else "SESSION_IDENTITY_MISMATCH"
        )
    if result.get(ROLES[2])=="PASS":
        code,identity,reason=psql(
            ROLES[2],"BEGIN READ ONLY; SET LOCAL ROLE empire_revenue_crm_reader; "
            "SELECT public.empire_current_tenant_id(); ROLLBACK;",password_file,
        )
        result["founder_tenant"] = (
            "PASS" if code==0 and identity==TENANT
            else reason if code else "TENANT_IDENTITY_MISMATCH"
        )
        code,_,reason=psql(
            ROLES[2],
            "BEGIN READ ONLY; SELECT 1 FROM public.empire_tenant_role_bindings LIMIT 1; ROLLBACK;",
            password_file,
        )
        result["global_binding_table_denied"] = (
            "PASS" if code!=0 and reason=="TABLE_PRIVILEGE_DENIED"
            else "UNVERIFIED")
    else:
        result["founder_tenant"]="BLOCKED_ON_READER_LOGIN"
        result["global_binding_table_denied"]="BLOCKED_ON_READER_LOGIN"
    return result


def main() -> int:
    if sys.argv[1:] != ["--read-only"]:
        print("CRM_SESSION_DIAGNOSTIC=BLOCKED_EXACT_FLAG_REQUIRED")
        return 3
    if os.geteuid()!=pwd.getpwnam("ubuntu").pw_uid:
        print("CRM_SESSION_DIAGNOSTIC=BLOCKED_SERVICE_ACCOUNT_REQUIRED")
        return 3
    try:
        if DIR.is_symlink() or not DIR.is_dir() or PASSFILE.is_symlink() or not PASSFILE.is_file():
            raise ValueError("unexpected private passfile")
        uid=pwd.getpwnam("ubuntu").pw_uid
        if (DIR.stat().st_uid!=uid or stat.S_IMODE(DIR.stat().st_mode)!=0o700
            or PASSFILE.stat().st_uid!=uid
            or stat.S_IMODE(PASSFILE.stat().st_mode)!=0o600):
            raise ValueError("bad private passfile metadata")
        original=PASSFILE.read_bytes()
        state=inspect(original)
        if state not in {"ORIGINAL_THREE_ROWS","REPAIRED_SIX_ROWS"}:
            raise ValueError("bad private passfile format")
        compatible=patched(original) if state=="ORIGINAL_THREE_ROWS" else original
        fd,temp_name=tempfile.mkstemp(prefix=".crm-session-proof-",dir=DIR)
        try:
            with os.fdopen(fd,"wb") as output:
                os.fchmod(output.fileno(),0o600)
                output.write(compatible)
                output.flush()
                os.fsync(output.fileno())
            outcomes=report(Path(temp_name))
        finally:
            if os.path.lexists(temp_name):
                os.unlink(temp_name)
        for role in ROLES:
            print("CRM_SESSION_"+role.upper()+"="+outcomes[role])
        print("CRM_SESSION_FOUNDER_TENANT="+outcomes["founder_tenant"])
        print("CRM_SESSION_RAW_BINDING_DENIAL="+outcomes["global_binding_table_denied"])
        success=all(value=="PASS" for value in outcomes.values())
        print("CRM_SESSION_DIAGNOSTIC="+("ALL_PASS" if success else "PARTIAL_HOLD"))
        print("CRM_SESSION_PRODUCTION_DATABASE_WRITES=NONE")
        print("CRM_SESSION_CREDENTIAL_ROTATION=NONE")
        return 0 if success else 2
    except Exception:
        print("CRM_SESSION_DIAGNOSTIC=BLOCKED_NO_CHANGES")
        return 4


if __name__=="__main__":
    raise SystemExit(main())
