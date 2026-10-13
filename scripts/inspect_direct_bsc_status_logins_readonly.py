"""Read-only post-provision login proof for DIRECT BSC buyer status.

Runs as root only to read the 0600 credentials file. No payment/buyer rows
are returned; reader function receives a reserved syntactically valid digest
which must not exist. Never prints connection strings or passwords.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from psycopg.conninfo import conninfo_to_dict
import psycopg

from scripts.provision_direct_bsc_buyer_status_logins import (
    READ_LOGIN, ISSUE_LOGIN, READ_ROLE, ISSUE_ROLE,
    READ_KEY, ISSUE_KEY, FUNCTIONS, verify_login, dsn_for,
)

ENV_PATH = Path("/etc/empire_direct_bsc_buyer_status.env")


def _safe_env(path: Path) -> dict[str,str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("untrusted credential path")
    s=path.stat()
    if s.st_uid != 0 or s.st_mode & 0o777 != 0o600:
        raise ValueError("credential permissions unsafe")
    lines=path.read_text(encoding="utf-8").splitlines()
    if len(lines)!=2:
        raise ValueError("expected two credential entries")
    out={}
    for line in lines:
        name,sep,value=line.partition("=")
        if not sep or name not in (READ_KEY,ISSUE_KEY) or name in out:
            raise ValueError("unexpected credential configuration")
        parsed=json.loads(value)
        if type(parsed) is not str or not parsed:
            raise ValueError("invalid credential value")
        out[name]=parsed
    if set(out)!={READ_KEY,ISSUE_KEY}:
        raise ValueError("incomplete credential configuration")
    return out


def _identity(dsn: str, login: str) -> None:
    parts=conninfo_to_dict(dsn)
    if (parts.get("dbname")!="empiredb"
        or parts.get("user")!=login
        or parts.get("host") not in ("127.0.0.1","localhost","::1","/var/run/postgresql")
        or str(parts.get("port") or "5432")!="5432"
        or parts.get("hostaddr") not in (None,"","127.0.0.1","::1")
        or not parts.get("password")
        or parts.get("options") or parts.get("service")):
        raise ValueError("noncanonical dedicated login DSN")


def prove(*, path: Path=ENV_PATH, connect=None) -> dict:
    if os.geteuid()!=0:
        raise ValueError("root readback required")
    env=_safe_env(path)
    reader,issuer=env[READ_KEY],env[ISSUE_KEY]
    _identity(reader,READ_LOGIN)
    _identity(issuer,ISSUE_LOGIN)
    if conninfo_to_dict(reader)["password"]==conninfo_to_dict(issuer)["password"]:
        raise ValueError("shared dedicated login password denied")
    verify_login(reader,READ_ROLE,FUNCTIONS[READ_LOGIN],FUNCTIONS[ISSUE_LOGIN])
    verify_login(issuer,ISSUE_ROLE,FUNCTIONS[ISSUE_LOGIN],FUNCTIONS[READ_LOGIN])
    # The existing strict read-only reader function must deny a non-issued
    # fixed fingerprint without disclosing any buyer details.
    connect_factory = connect or psycopg.connect
    with connect_factory(reader,connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout='2500ms'")
            cursor.execute("SET LOCAL ROLE "+READ_ROLE)
            cursor.execute("SELECT public.read_direct_bsc_buyer_status(%s)",
                           ("0"*64,))
            row=cursor.fetchone()
            if row is None or len(row)!=1 or row[0] is not None:
                raise ValueError("unissued bearer fingerprint was disclosed")
            connection.rollback()
    return {
        "status":"DEDICATED_STATUS_LOGINS_LIVE_READBACK_VERIFIED",
        "mode":"READ_ONLY",
        "reader_login_verified":True,
        "issuer_login_verified":True,
        "independent_passwords":True,
        "unissued_fingerprint_denied":True,
        "buyer_records_exposed":False,
        "credentials_exposed":False,
        "token_issued":False,
        "public_endpoint_enabled":False,
        "payment_execution":False,
    }


def main(argv: list[str]|None=None)->int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["--verify-only"]:
        print(json.dumps({"status":"HELD_EXACT_READONLY_FLAG_REQUIRED"}))
        return 3
    try:
        result=prove()
    except Exception:
        print(json.dumps({
            "status":"HELD_DEDICATED_LOGIN_READBACK",
            "mode":"READ_ONLY",
            "credentials_exposed":False,
            "no_retry_of_provisioner":True,
        },sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
