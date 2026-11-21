#!/usr/bin/env python3
"""Exact guarded ONE tenant Mautic inbox writer release, no contact or ingress.

The standalone root operator ONLY provisions a LOGIN bound to the existing
founder tenant. No API mounts, customer import, SMTP, campaigns or contacts.
Uses live canonical role binding and audited single-tenant CRM config.
Preflight has NO writes. Apply backs up HBA, global roles + tenant binding,
and Mautic inbox; creates one 0600 credential, adds exactly one SCRAM HBA
line, and changes one database role+binding in a transaction. PostgreSQL
is RELOADED, never restarted. On failure, only this bounded delta is rolled
back if no inbox receipts exist. No passwords or first-party IDs in output.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import stat
import subprocess
import sys
from uuid import UUID

import psycopg
from psycopg import sql

from empire_os.mautic_crm_inbox import PostgresMauticEventInbox

UNIT = "empire-revenue-crm-pilot.service"
PG_UNIT = "postgresql@18-main.service"
HBA = Path("/etc/postgresql/18/main/pg_hba.conf")
BACKUP = Path("/var/backups/empiredb/mautic-writer-20261121")
VAULT = Path("/var/lib/empire-mautic-crm-private")
PASSFILE = VAULT / "mautic-writer.pgpass"
EVIDENCE = "founder:guarded-mautic-zero-contact-writer-20261121"
ROLE_GROUP = "empire_mautic_crm_inbox_writer"
DATABASE = "empiredb"
SOCKET = "/var/run/postgresql"
DBADMIN = "host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=4"


def process(argv: list[str], *, input: str | None = None, timeout: int = 25) -> subprocess.CompletedProcess:
    return subprocess.run(argv, input=input, capture_output=True, text=True, timeout=timeout, check=False)


def db_call(action: str, *, writer: str, tenant: str, verifier: str | None = None) -> dict:
    """Run PostgreSQL privileged steps ONLY as the established OS postgres."""
    code = r'''
import json, sys
import psycopg
from psycopg import sql
data=json.load(sys.stdin)
action=data["action"];role=data["writer"];tenant=data["tenant"]
if not role.startswith("empire_mautic_tenant_") or len(role)>64: raise RuntimeError("role_invalid")
con=psycopg.connect("host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5")
try:
 with con, con.cursor() as c:
  c.execute("SET LOCAL statement_timeout='8000ms'")
  c.execute("SET LOCAL lock_timeout='3000ms'")
  c.execute("SELECT current_database() = 'empiredb',pg_is_in_recovery()")
  db,recovery=c.fetchone()
  if not db or recovery: raise RuntimeError("canonical_db_unavailable")
  c.execute("SELECT rolname FROM pg_roles WHERE rolname=%s",(role,))
  existing=c.fetchone() is not None
  c.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='empire_mautic_crm_inbox_writer' AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolbypassrls), COALESCE((SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='public.empire_crm_mautic_event_inbox'::regclass),FALSE)")
  writer_group,rls=c.fetchone()
  c.execute("SELECT count(*) FROM public.empire_crm_mautic_event_inbox")
  rows=c.fetchone()[0]
  c.execute("SELECT count(*) FROM public.empire_tenant_role_bindings WHERE tenant_id=%s::uuid AND active AND role_name LIKE 'empire_crm_tenant_%%' AND evidence_ref IS NOT NULL",(tenant,))
  crm_binding=c.fetchone()[0]
  c.execute("SELECT count(*) FROM public.empire_tenant_role_bindings WHERE role_name=%s",(role,))
  writer_binding=c.fetchone()[0]
  if action=="preflight":
   print(json.dumps({"db":db,"writer_role_absent":not existing,"writer_binding_absent":writer_binding==0,"group_safe":writer_group,"force_rls":rls,"inbox_rows":rows,"existing_tenant_reader_binding_exactly_one":crm_binding==1}))
  elif action=="apply":
   if existing or writer_binding or not writer_group or not rls or rows or crm_binding!=1:raise RuntimeError("canonical_catalog_changed")
   v=data.get("verifier")
   if not isinstance(v,str) or not v.startswith("SCRAM-SHA-256$4096:"):raise RuntimeError("invalid_password_verifier")
   c.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Identifier(role),sql.Literal(v)))
   c.execute(sql.SQL("GRANT CONNECT ON DATABASE empiredb TO {}").format(sql.Identifier(role)))
   c.execute(sql.SQL("GRANT {} TO {} WITH INHERIT FALSE,SET TRUE").format(sql.Identifier("empire_mautic_crm_inbox_writer"),sql.Identifier(role)))
   c.execute("INSERT INTO public.empire_tenant_role_bindings (role_name,tenant_id,active,evidence_ref) VALUES (%s,%s::uuid,true,%s)",(role,tenant,"founder:guarded-mautic-zero-contact-writer-20261121"))
   print(json.dumps({"status":"writer_transaction_committed","new_login_count":1,"new_tenant_binding_count":1}))
  elif action=="rollback":
   if rows:raise RuntimeError("inbox_evidence_exists_no_rollback")
   if existing:
    c.execute(sql.SQL("REVOKE CONNECT ON DATABASE empiredb FROM {}").format(sql.Identifier(role)))
    c.execute(sql.SQL("REVOKE {} FROM {}").format(sql.Identifier("empire_mautic_crm_inbox_writer"),sql.Identifier(role)))
    c.execute("DELETE FROM public.empire_tenant_role_bindings WHERE role_name=%s AND tenant_id=%s::uuid",(role,tenant))
    c.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
   print(json.dumps({"status":"no_evidence_writer_role_rolled_back"}))
  elif action=="verify":
   if not existing or writer_binding!=1 or not writer_group or not rls:raise RuntimeError("writer_catalog_incomplete")
   c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s",(role,))
   attrs=c.fetchone()
   c.execute("SELECT COUNT(*) FROM pg_auth_members am JOIN pg_roles g ON g.oid=am.roleid JOIN pg_roles m ON m.oid=am.member WHERE m.rolname=%s AND g.rolname=%s AND NOT am.inherit_option AND am.set_option",(role,"empire_mautic_crm_inbox_writer"))
   groups=c.fetchone()[0]
   c.execute("SELECT COUNT(*) FROM pg_auth_members am JOIN pg_roles m ON m.oid=am.member WHERE m.rolname=%s",(role,))
   total=c.fetchone()[0]
   c.execute("SELECT pg_catalog.has_database_privilege(%s,'empiredb','CONNECT')",(role,))
   connects=c.fetchone()[0]
   if attrs!=(True,False,False,False,False,False,False) or groups!=1 or total!=1 or not connects:raise RuntimeError("writer_role_has_unsafe_privileges")
   print(json.dumps({"status":"writer_catalog_and_tenant_binding_verified","writer_role_safe":True,"writer_only_one_group":True,"inbox_rows":rows}))
  else:raise RuntimeError("unknown_action")
finally:con.close()
'''
    payload = json.dumps({"action": action, "writer": writer, "tenant": tenant, "verifier": verifier})
    cp = process(["/usr/sbin/runuser", "-u", "postgres", "--",
                  "/srv/empire_os/.venv/bin/python", "-B", "-c", code],
                 input=payload, timeout=22)
    if cp.returncode or len(cp.stdout)>1800:
        raise RuntimeError("privileged_canonical_db_" + action + "_failed")
    return json.loads(cp.stdout)


def identities() -> tuple[str, str]:
    p = process(["systemctl","show",UNIT,"--value","-p","MainPID"],timeout=4)
    pid = int(p.stdout.strip())
    if pid <= 1 or process(["systemctl","is-active",UNIT],timeout=4).stdout.strip()!="active":
        raise RuntimeError("original_crm_not_running")
    data = dict(v.split(b"=",1) for v in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if b"=" in v)
    configured = data.get(b"EMPIRE_CRM_PILOT_CONFIG_FILE")
    if not configured:
        raise RuntimeError("original_crm_config_unavailable")
    owner = json.loads(Path(configured.decode()).read_text())
    dsns = owner.get("tenant_dsns")
    if not isinstance(dsns,dict) or len(dsns)!=1:
        raise RuntimeError("original_crm_requires_exact_one_tenant")
    tenant,dsn=next(iter(dsns.items()))
    if str(UUID(tenant))!=tenant or not isinstance(dsn,str):
        raise RuntimeError("original_crm_untrusted_tenant")
    expected_reader="empire_crm_tenant_"+tenant.replace("-","")[:12]
    if psycopg.conninfo.conninfo_to_dict(dsn).get("user")!=expected_reader:
        raise RuntimeError("original_crm_reader_role_mismatch")
    return tenant,"empire_mautic_tenant_"+tenant.replace("-","")[:12]


def hba_ready(writer: str) -> tuple[bytes, int, int, int, bytes]:
    if HBA.is_symlink():
        raise RuntimeError("postgres_auth_file_symlink")
    meta=HBA.stat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o022 or meta.st_uid!=pwd.getpwnam("postgres").pw_uid:
        raise RuntimeError("postgres_auth_file_not_trusted")
    raw=HBA.read_bytes()
    if b"empire_mautic_tenant_" in raw:
        raise RuntimeError("existing_mautic_hba_requires_reconciliation")
    match=re.search(rb"(?m)^local\s+all\s+all\s+peer\s*$",raw)
    if match is None:
        raise RuntimeError("unknown_postgresql_hba_order")
    line=f"local   empiredb   {writer}   scram-sha-256\n".encode()
    return raw,meta.st_uid,meta.st_gid,stat.S_IMODE(meta.st_mode),raw[:match.start()]+line+raw[match.start():]


def scram_verifier(pw: str) -> str:
    salt=secrets.token_bytes(16);rounds=4096
    salted=__import__("hashlib").pbkdf2_hmac("sha256",pw.encode(),salt,rounds)
    stored=sha256(hmac.new(salted,b"Client Key","sha256").digest()).digest()
    server=hmac.new(salted,b"Server Key","sha256").digest()
    b=lambda v:base64.b64encode(v).decode()
    return f"SCRAM-SHA-256${rounds}:{b(salt)}${b(stored)}:{b(server)}"


def dump_private(path: Path, argv: list[str]) -> None:
    cp = subprocess.run(["/usr/sbin/runuser","-u","postgres","--",*argv],
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
    if cp.returncode or not cp.stdout:
        raise RuntimeError("canonical_pre_change_backup_failed")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(cp.stdout);out.flush();os.fsync(out.fileno())


def backups(raw: bytes, tenant: str) -> dict[str,str]:
    BACKUP.mkdir(mode=0o700,parents=True,exist_ok=False)
    os.chown(BACKUP,0,0);BACKUP.chmod(0o700)
    (BACKUP/"hba.original").write_bytes(raw)
    (BACKUP/"hba.original").chmod(0o600)
    dump_private(BACKUP/"roles.globals.sql",["/usr/bin/pg_dumpall","--globals-only","-w"])
    dump_private(BACKUP/"mautic-inbox.dump",["/usr/bin/pg_dump","-Fc","-w","-d","empiredb","-t","public.empire_crm_mautic_event_inbox"])
    dump_private(BACKUP/"tenant-bindings.dump",["/usr/bin/pg_dump","-Fc","-w","-d","empiredb","-t","public.empire_tenant_role_bindings"])
    hashes={}
    for file in BACKUP.iterdir():
        hashes[file.name]=sha256(file.read_bytes()).hexdigest()
        if file.stat().st_mode & 0o077:raise RuntimeError("backup_file_permissions_invalid")
    return hashes


def replace_hba(data: bytes, uid: int, gid: int, mode: int) -> None:
    temp=HBA.parent/(".pg_hba.empire-mautic-"+secrets.token_hex(5))
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chown(temp,uid,gid);os.chmod(temp,mode)
        os.replace(temp,HBA)
    finally:
        temp.unlink(missing_ok=True)


def reload_pg() -> None:
    if process(["systemctl","reload",PG_UNIT],timeout=16).returncode:
        raise RuntimeError("postgresql_config_reload_failed")
    if process(["systemctl","is-active",PG_UNIT],timeout=5).stdout.strip()!="active":
        raise RuntimeError("postgresql_not_active_after_reload")


def check_login(tenant: str, writer: str) -> bool:
    # Connecting using a dedicated, local SCRAM-only login proves HBA,
    # SCRAM verifier, NOINHERIT, role membership and tenant binding.
    dsn=(f"host={SOCKET} port=5432 dbname={DATABASE} user={writer} "
         f"passfile={PASSFILE} connect_timeout=5")
    from empire_os.mautic_crm_inbox import MauticInboxUnavailable
    writer_api=PostgresMauticEventInbox(dsn,authenticated_tenant_id=tenant)
    try:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            writer_api._authority(cur)
    except MauticInboxUnavailable as exc:
        # These are fixed application error codes; no credentials or IDs.
        raise RuntimeError("mautic_writer_authority_failed_"+str(exc)) from None
    except psycopg.Error as exc:
        # Diagnose transport without returning DSN, user, password or HBA.
        reason=str(exc).lower()
        category=next((name for needle,name in (
            ("password authentication failed","PASSWORD_REJECTED"),
            ("no password supplied","PASSWORD_NOT_SUPPLIED"),
            ("no pg_hba.conf entry","NO_HBA_MATCH"),
            ("permission denied for database","DATABASE_CONNECT_NOT_GRANTED"),
            ("permission denied","PATH_PERMISSION_DENIED"),
            ("connection refused","SOCKET_REFUSED"),
            ("could not translate host","HOST_UNREACHABLE"),
            ("connection timeout","CONNECTION_TIMEOUT"),
        ) if needle in reason),"UNCLASSIFIED_CONNECT_ERROR")
        raise RuntimeError("mautic_writer_connect_"+category) from None
    try:
        accepted=writer_api.reserve_new(
            tenant_id=tenant,source_id="mautic-private-empty",
            evidence_hmacs=[],reviews=[],now=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc),
        )
    except MauticInboxUnavailable:
        raise RuntimeError("mautic_writer_second_transaction_probe_failed") from None
    return accepted==set()


def execute(*, apply: bool) -> dict[str,object]:
    if os.geteuid()!=0:
        raise RuntimeError("host_root_approver_required")
    tenant,writer=identities()
    raw,uid,gid,mode,updated=hba_ready(writer)
    state=db_call("preflight",writer=writer,tenant=tenant)
    if state!={"db":True,"writer_role_absent":True,"writer_binding_absent":True,
               "group_safe":True,"force_rls":True,"inbox_rows":0,
               "existing_tenant_reader_binding_exactly_one":True}:
        raise RuntimeError("canonical_writer_preflight_not_safe")
    if not apply:
        return {"status":"READY_TO_PROVISION","canonical_db_bound":True,
                "one_existing_verified_tenant":True,
                "single_exact_scram_hba_rule_required":True,
                "no_existing_writer_login":True,
                "prior_recovery_backup_present":BACKUP.exists(),
                "marketing_authorized":False,"database_writes":False}
    if VAULT.exists():
        raise RuntimeError("writer_secret_vault_already_exists")
    if BACKUP.exists():
        verified = (BACKUP/"hba.original").read_bytes() == raw
        backups_ok = all(
            (BACKUP/name).is_file() and (BACKUP/name).stat().st_mode & 0o077 == 0
            and (BACKUP/name).stat().st_size > 0
            for name in ("hba.original","roles.globals.sql",
                         "mautic-inbox.dump","tenant-bindings.dump")
        )
        if not verified or not backups_ok:
            raise RuntimeError("previous_rollback_backup_not_verified")
        hashes = {f.name:sha256(f.read_bytes()).hexdigest()
                  for f in BACKUP.iterdir() if f.is_file()}
    else:
        hashes=backups(raw,tenant)
    owner=pwd.getpwnam("ubuntu")
    VAULT.mkdir(mode=0o700)
    os.chown(VAULT,owner.pw_uid,owner.pw_gid);VAULT.chmod(0o700)
    password=secrets.token_hex(48)
    verifier=scram_verifier(password)
    fd=os.open(PASSFILE,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"w") as out:
        # libpq also searches localhost for the server default Unix socket
        # directory. Pin BOTH exact local identities, never wildcard host.
        out.write(f"{SOCKET}:5432:{DATABASE}:{writer}:{password}\n")
        out.write(f"localhost:5432:{DATABASE}:{writer}:{password}\n")
        out.flush();os.fsync(out.fileno())
    os.chown(PASSFILE,owner.pw_uid,owner.pw_gid)
    PASSFILE.chmod(0o600)
    state_changed=False
    try:
        replace_hba(updated,uid,gid,mode)
        state_changed=True
        reload_pg()
        db_call("apply",writer=writer,tenant=tenant,verifier=verifier)
        if db_call("verify",writer=writer,tenant=tenant)["status"]!="writer_catalog_and_tenant_binding_verified":
            raise RuntimeError("writer_postcommit_verification_failed")
        if not check_login(tenant,writer):
            raise RuntimeError("writer_live_pg_authenticated_empty_read_failed")
        receipt={
            "status":"EXACT_FOUNDER_TENANT_WRITER_PROVISIONED_NO_SOURCE_SEND",
            "role_scope":"single existing verified founder CRM tenant",
            "login_scram_verified":True,
            "writer_inbox_db_role_verified":True,
            "writer_forced_rls_verified":True,
            "zero_event_producer_canary":True,
            "source_binding_or_marketing_consent_claimed":False,
            "no_customer_events_inserted":True,
            "no_webhooks_or_campaigns_enabled":True,
            "no_service_restart":True,
            "postgresql_reload_only":True,
            "backup_sha256":hashes,
            "hba_before_sha256":sha256(raw).hexdigest(),
            "hba_after_sha256":sha256(updated).hexdigest(),
            "login_role_name":writer,
            "vault_path":str(PASSFILE),
            "rollback_scope":"Only empty Mautic writer and exact HBA line; never remove existing inbox",
        }
        (BACKUP/"release.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
        (BACKUP/"release.json").chmod(0o600)
        return {k:v for k,v in receipt.items() if k not in (
            "backup_sha256","hba_before_sha256","hba_after_sha256","vault_path","login_role_name")}
    except Exception:
        if state_changed:
            try: db_call("rollback",writer=writer,tenant=tenant)
            except Exception: pass
            replace_hba(raw,uid,gid,mode)
            reload_pg()
        try: PASSFILE.unlink(missing_ok=True)
        except Exception: pass
        try: VAULT.rmdir()
        except Exception: pass
        raise




def verify_installed() -> dict[str,object]:
    """Second independent readback, with no DDL, HBA changes or customer rows."""
    if os.geteuid()!=0:
        raise RuntimeError("root_verification_required")
    tenant,writer=identities()
    r=db_call("verify",writer=writer,tenant=tenant)
    if r.get("status")!="writer_catalog_and_tenant_binding_verified" or r.get("inbox_rows")!=0:
        raise RuntimeError("writer_role_or_inbox_changed")
    receipt=json.loads((BACKUP/"release.json").read_text())
    if receipt.get("status")!="EXACT_FOUNDER_TENANT_WRITER_PROVISIONED_NO_SOURCE_SEND":
        raise RuntimeError("writer_release_receipt_missing")
    raw=(BACKUP/"hba.original").read_bytes()
    if HBA.is_symlink() or HBA.stat().st_uid!=pwd.getpwnam("postgres").pw_uid:
        raise RuntimeError("postgres_hba_owner_changed")
    line=f"local   empiredb   {writer}   scram-sha-256\n".encode()
    if HBA.read_bytes().count(line)!=1:
        raise RuntimeError("exact_scram_rule_absent_or_duplicate")
    if sha256(HBA.read_bytes()).hexdigest()!=receipt["hba_after_sha256"]:
        raise RuntimeError("postgres_hba_unexpected_mutation")
    if sha256(raw).hexdigest()!=receipt["hba_before_sha256"]:
        raise RuntimeError("postgres_hba_rollback_not_pinned")
    owner=pwd.getpwnam("ubuntu")
    for path,mode in ((VAULT,0o700),(PASSFILE,0o600)):
        st=path.lstat()
        if path.is_symlink() or st.st_uid!=owner.pw_uid or stat.S_IMODE(st.st_mode)!=mode:
            raise RuntimeError("private_writer_secret_permissions_changed")
    if len(PASSFILE.read_text().splitlines())!=2:
        raise RuntimeError("unexpected_private_pgpass_shape")
    if not check_login(tenant,writer):
        raise RuntimeError("actual_writer_authenticated_zero_event_canary_failed")
    if process(["systemctl","is-active",PG_UNIT],timeout=5).stdout.strip()!="active":
        raise RuntimeError("postgresql_unavailable")
    if process(["systemctl","is-active",UNIT],timeout=5).stdout.strip()!="active":
        raise RuntimeError("original_crm_unavailable")
    http=process(["curl","--silent","--output","/dev/null","--max-time","3","--write-out","%{http_code}",
                  "http://127.0.0.1:8783/v1/revenue-crm/integrations/mautic/inbox/reviews"],timeout=5)
    if http.returncode or http.stdout.strip()!="401":
        raise RuntimeError("original_crm_inbox_auth_not_proven")
    return {
        "status":"LIVE_WRITER_PRIVILEGES_AND_PRIVATE_AUTH_VERIFIED",
        "single_existing_tenant_login":True,
        "writer_membership_only":True,
        "writer_forced_rls":True,
        "private_scram_login_works":True,
        "credentials_owner_only":True,
        "hba_exact_rule_and_rollback_hashes":True,
        "inbox_rows":0,
        "unauthenticated_inbox_http":401,
        "source_and_contact_bindings_authorized":False,
        "outbound_authorized":False,
        "service_restarted":False,
        "database_writes":False,
        "customer_identifiers_disclosed":False,
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight",action="store_true")
    g.add_argument("--verify-installed",action="store_true")
    g.add_argument("--apply-founder-approved-exact-empty-source-writer",action="store_true")
    args=parser.parse_args()
    try:
        result = verify_installed() if args.verify_installed else execute(
            apply=args.apply_founder_approved_exact_empty_source_writer)
        print(json.dumps(result,sort_keys=True))
    except Exception as exc:
        print("MAUTIC_WRITER_RELEASE=HOLD_"+str(exc),file=sys.stderr)
        raise SystemExit(3)


if __name__=="__main__":
    main()
