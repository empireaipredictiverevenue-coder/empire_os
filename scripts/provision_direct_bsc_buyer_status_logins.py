"""Staged isolated 049/050 buyer status login provisioning. NO default writes.

Founder approval required separately from migrations 049/050. Secrets are
generated in-process, sent to psql on stdin, written only to root 0600 env.
No public status endpoint, token issuance, mail or payment feature is enabled.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import tempfile

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from empire_os.runtime_env import load_runtime_env

ENV_FILE = Path("/etc/empire_direct_bsc_buyer_status.env")
READ_LOGIN = "empire_direct_checkout_status_reader_login"
ISSUE_LOGIN = "empire_direct_checkout_status_issuer_login"
READ_ROLE = "empire_direct_checkout_status_reader"
ISSUE_ROLE = "empire_direct_checkout_status_issuer"
READ_KEY = "EMPIRE_DIRECT_BSC_BUYER_STATUS_READER_DSN"
ISSUE_KEY = "EMPIRE_DIRECT_BSC_STATUS_ISSUER_DSN"
APPROVAL = "--approved-isolated-bsc-status-logins-only"
FUNCTIONS = {
    READ_LOGIN: "public.read_direct_bsc_buyer_status(text)",
    ISSUE_LOGIN:
      "public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)",
}


def dsn_for(base_dsn: str, login: str, password: str) -> str:
    info = conninfo_to_dict(base_dsn)
    if info.get("dbname") != "empiredb":
        raise ValueError("canonical local database required")
    host = str(info.get("host") or "").strip()
    if host not in {"127.0.0.1", "localhost", "::1", "/var/run/postgresql"}:
        raise ValueError("remote database endpoint denied")
    if str(info.get("port") or "5432") != "5432":
        raise ValueError("noncanonical database port denied")
    if str(info.get("hostaddr") or "").strip() not in {"", "127.0.0.1", "::1"}:
        raise ValueError("remote hostaddr override denied")
    if login not in (READ_LOGIN, ISSUE_LOGIN):
        raise ValueError("unknown dedicated login")
    out = {k: v for k, v in info.items() if k not in (
        "user", "password", "options", "service", "application_name"
    )}
    return make_conninfo(
        **out, user=login, password=password,
        application_name=login, connect_timeout="5",
    )


def provision_sql(passwords: dict[str,str]) -> str:
    if set(passwords)!={READ_LOGIN, ISSUE_LOGIN}:
        raise ValueError("two exact dedicated login identities required")
    for password in passwords.values():
        if (not isinstance(password,str) or len(password)<40 or
            not password.replace("-", "").replace("_", "").isalnum()):
            raise ValueError("unsafe secret encoding")
    # Role names and secret alphabet are validated constants. All SQL
    # input passes only via stdin, never argv, environment or server logs.
    out=["BEGIN;", "SET LOCAL statement_timeout='10s';",
         "SET LOCAL lock_timeout='3s';"]
    for login,role in ((READ_LOGIN,READ_ROLE),(ISSUE_LOGIN,ISSUE_ROLE)):
        out.append(f"""
DO $guard$
BEGIN
 IF pg_catalog.to_regrole('{login}') IS NOT NULL THEN
  RAISE EXCEPTION 'DIRECT_STATUS_LOGIN_ALREADY_EXISTS_RECONCILE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
   WHERE r.rolname='{role}' AND NOT r.rolcanlogin
     AND NOT r.rolsuper AND NOT r.rolbypassrls
     AND NOT r.rolcreatedb AND NOT r.rolcreaterole)
   OR EXISTS (
      SELECT 1 FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles member ON member.oid=m.member
      JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
      WHERE member.rolname='{role}' OR granted.rolname='{role}')
   OR pg_catalog.to_regprocedure('{FUNCTIONS[login]}') IS NULL
 THEN RAISE EXCEPTION 'DIRECT_STATUS_049_050_ROLE_OR_FUNCTION_DRIFT'; END IF;
END
$guard$;""")
        out.extend((
            f"CREATE ROLE {login} LOGIN NOINHERIT NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS "
            f"PASSWORD '{passwords[login]}';",
            f"ALTER ROLE {login} SET statement_timeout='3s';",
            f"GRANT CONNECT ON DATABASE empiredb TO {login};",
            f"GRANT {role} TO {login} "
            "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;",
        ))
    out.append("COMMIT;")
    return "\n".join(out)+"\n"


def _role_name(value: object) -> str:
    if isinstance(value, bytes):
        try:
            value=value.decode("ascii",errors="strict")
        except UnicodeDecodeError:
            return ""
    return value if isinstance(value,str) else ""


def verify_login(dsn: str, role: str, own_function: str,
                 other_function: str) -> None:
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            observed_login=_role_name(cur.execute("SELECT session_user").fetchone()[0])
            # NOINHERIT login must have no raw financial table privileges.
            login_can_table=cur.execute(
                "SELECT pg_catalog.has_table_privilege(session_user,"
                "'public.direct_bsc_buyer_capabilities','SELECT'),"
                " pg_catalog.has_table_privilege(session_user,"
                "'public.direct_bsc_buyer_capabilities','INSERT'),"
                " pg_catalog.has_table_privilege(session_user,"
                "'public.bsc_payment_requests','SELECT'),"
                " pg_catalog.has_table_privilege(session_user,"
                "'public.fulfilment_orders','SELECT')"
            ).fetchone()
            login_can_functions=cur.execute(
                "SELECT pg_catalog.has_function_privilege(session_user,%s,'EXECUTE'),"
                " pg_catalog.has_function_privilege(session_user,%s,'EXECUTE')",
                (own_function,other_function),
            ).fetchone()
            cur.execute("SET LOCAL ROLE "+role)
            effective=_role_name(cur.execute("SELECT current_user").fetchone()[0])
            can_execute=cur.execute(
                "SELECT pg_catalog.has_function_privilege(current_user,%s,'EXECUTE'),"
                " pg_catalog.has_function_privilege(current_user,%s,'EXECUTE')",
                (own_function,other_function),
            ).fetchone()
            can_table=cur.execute(
                "SELECT pg_catalog.has_table_privilege(current_user,"
                "'public.direct_bsc_buyer_capabilities','SELECT'),"
                " pg_catalog.has_table_privilege(current_user,"
                "'public.direct_bsc_buyer_capabilities','INSERT'),"
                " pg_catalog.has_table_privilege(current_user,"
                "'public.direct_bsc_buyer_capabilities','UPDATE'),"
                " pg_catalog.has_table_privilege(current_user,"
                "'public.direct_bsc_buyer_capabilities','DELETE')"
            ).fetchone()
            cur.execute("SELECT 1")
            conn.rollback()
    expected_login = (READ_LOGIN if role==READ_ROLE else ISSUE_LOGIN)
    if (observed_login!=expected_login or effective!=role or
        tuple(can_execute)!=(True,False) or any(can_table) or
        any(login_can_table) or any(login_can_functions)):
        raise ValueError("dedicated login privilege proof failed")


def _write_env(path: Path, content: str) -> None:
    if path.is_symlink() or path.exists():
        raise ValueError("existing env requires separate rotation/reconciliation")
    if not path.parent.is_dir():
        raise ValueError("secret directory missing")
    fd,temporary=tempfile.mkstemp(prefix=".direct-bsc-status-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            os.fchmod(handle.fileno(),0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)



def existing_contracts_verified() -> None:
    """Pure catalog readback before any credential/role mutation."""
    for version,total,path in (
        ("049",12,"scripts/inspect_direct_bsc_private_reader_049_postcommit.sql"),
        ("050",10,"scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql"),
    ):
        if not Path(path).is_file():
            raise ValueError("existing private role verification missing")
        checked=subprocess.run(
            ["runuser","-u","postgres","--","psql","-X","-w",
             "-v","ON_ERROR_STOP=1","-d","empiredb","-f",path],
            text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=20,check=False,
        )
        if checked.returncode:
            raise ValueError("installed buyer roles could not be verified")
        records=[
            line for line in checked.stdout.splitlines()
            if re.fullmatch(r"(?:0[1-9]|1[0-2])_[a-z0-9_]+\|(?:PASS|FAIL)",line)
        ]
        if (len(records)!=total or
            any(not line.endswith("|PASS") for line in records)):
            raise ValueError("installed buyer role security contract drift")


CONTROLLED_ORDER_RELEASE = Path(
    "/etc/systemd/system/empire-self-serve-checkout.service.d/"
    "40-direct-bsc-controlled-release.conf"
)


def _verified_controlled_order_release() -> bool:
    """Accept only the already-deployed root-owned, active release drop-in."""
    import stat
    path = CONTROLLED_ORDER_RELEASE
    try:
        if path.is_symlink() or not path.is_file():
            return False
        metadata = path.stat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
                or metadata.st_mode & 0o022):
            return False
        body = path.read_text(encoding="utf-8")
        lines = body.splitlines()
        if "# Founder-approved four-product direct BSC order admission." not in lines:
            return False
        for name in (
            "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED",
            "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED",
        ):
            if lines.count("Environment=" + name + "=ON") != 1:
                return False
        process = subprocess.run(
            ["systemctl","show","empire-self-serve-checkout.service",
             "-p","DropInPaths","--value"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,check=False,timeout=5,
        )
        return (process.returncode == 0
                and str(path) in process.stdout.split())
    except Exception:
        return False


def validate_checkout_admission(
    snapshot: dict, *, controlled_release_verified: bool
) -> None:
    """Order admission is not payment execution or revenue recognition."""
    if (not isinstance(snapshot, dict)
            or snapshot.get("status") != "online"
            or snapshot.get("checkout_settlement_mode") != "direct"
            or snapshot.get("payment_execution") is not False
            or snapshot.get("revenue_recognition") is not False):
        raise ValueError("payment or revenue authority not held")
    proposal = snapshot.get("payment_proposal_authorized")
    orders = snapshot.get("binding_order_creation_authorized")
    if proposal is False and orders is False:
        return
    if proposal is True and orders is True and controlled_release_verified is True:
        return
    raise ValueError("unverified or inconsistent checkout order release")


def checkout_financial_execution_held() -> None:
    import urllib.request
    try:
        request=urllib.request.Request("http://127.0.0.1:8098/health")
        with urllib.request.urlopen(request,timeout=4) as response:
            result=json.load(response)
    except Exception:
        raise ValueError("local checkout health unavailable") from None
    active = (
        isinstance(result,dict)
        and result.get("payment_proposal_authorized") is True
        and result.get("binding_order_creation_authorized") is True
    )
    validate_checkout_admission(
        result,
        controlled_release_verified=(
            _verified_controlled_order_release() if active else False
        ),
    )


def apply() -> dict:
    if os.geteuid()!=0:
        raise ValueError("root operator required")
    if ENV_FILE.exists() or ENV_FILE.is_symlink():
        raise ValueError("existing credential file must be reconciled")
    os.chdir("/srv/empire_os")
    existing_contracts_verified()
    checkout_financial_execution_held()
    env=load_runtime_env("/etc/empiredb.env")
    base=str(env.get("EMPIREDB_DSN") or "")
    passwords={
        READ_LOGIN:secrets.token_urlsafe(42),
        ISSUE_LOGIN:secrets.token_urlsafe(42),
    }
    reader_dsn=dsn_for(base,READ_LOGIN,passwords[READ_LOGIN])
    issuer_dsn=dsn_for(base,ISSUE_LOGIN,passwords[ISSUE_LOGIN])
    sql=provision_sql(passwords)
    # Postgres system login reads SQL from stdin, never prints passwords.
    p=subprocess.run(
        ["runuser","-u","postgres","--","psql","-X","-q",
         "-v","ON_ERROR_STOP=1","-d","empiredb"],
        input=sql,text=True,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,timeout=45,check=False,
    )
    if p.returncode:
        raise ValueError("dedicated role transaction failed")
    # Do not use any live order, token, or buyer fingerprint to verify.
    verify_login(reader_dsn,READ_ROLE,FUNCTIONS[READ_LOGIN],FUNCTIONS[ISSUE_LOGIN])
    verify_login(issuer_dsn,ISSUE_ROLE,FUNCTIONS[ISSUE_LOGIN],FUNCTIONS[READ_LOGIN])
    values={READ_KEY:reader_dsn,ISSUE_KEY:issuer_dsn}
    body="".join(k+"="+json.dumps(v)+"\n" for k,v in values.items())
    checkout_financial_execution_held()
    _write_env(ENV_FILE,body)
    return {
        "status":"two_login_connections_verified",
        "env_path":str(ENV_FILE),
        "file_mode":"0600","secrets_printed":False,
        "role_memberships":"dedicated_only",
        "buyer_status_endpoint_activated":False,
        "payment_execution":False,
    }


def main(argv: list[str]|None=None) -> int:
    args=argv if argv is not None else __import__("sys").argv[1:]
    if not args:
        print(json.dumps({
            "status":"STAGED_LOGIN_PROVISIONING_NOT_APPLIED",
            "founder_approval_required":True,
            "issuer_login_created":False,"reader_login_created":False,
            "buyer_status_endpoint_activated":False,
        },sort_keys=True))
        return 0
    if args!=["--apply",APPROVAL]:
        print(json.dumps({"status":"HELD_SEPARATE_LOGIN_APPROVAL_REQUIRED"}))
        return 3
    try:
        state=apply()
    except Exception:
        print(json.dumps({
            "status":"HELD_DEDICATED_LOGIN_PROVISIONING_OR_VERIFICATION",
            "do_not_retry_without_readback":True,
            "secrets_printed":False,
        },sort_keys=True))
        return 4
    print(json.dumps(state,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
