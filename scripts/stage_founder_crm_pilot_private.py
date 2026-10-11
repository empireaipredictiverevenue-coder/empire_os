#!/usr/bin/env python3
"""Stage private EmpireOS founder CRM pilot material, without service activation.

Owner: ubuntu. Exactly three first-party database identities, one founder tenant.
No invite redemption, token read, SMTP, HTTP listener, or database writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import stat
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path("/var/lib/empire-crm-first-party")
KEY = ROOT / "pilot-signing.pem"
CONFIG = ROOT / "pilot-runtime.json"
ENV = ROOT / "pilot-staged.env"
PASSFILE = ROOT / "pgpass"
PENDING = ROOT / "founder_invitation/pending_invitation.json"
TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"
BASE = "host=/var/run/postgresql port=5432 dbname=empiredb user="
CONFIG_SCHEMA = "empire.crm.pilot_runtime.v1"


def exact_private(path: Path, mode: int=0o600) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    info=path.stat()
    return info.st_uid==pwd.getpwnam("ubuntu").pw_uid and stat.S_IMODE(info.st_mode)==mode


def prerequisites() -> str:
    if (ROOT.is_symlink() or not ROOT.is_dir() or
        ROOT.stat().st_uid!=pwd.getpwnam("ubuntu").pw_uid or
        stat.S_IMODE(ROOT.stat().st_mode)!=0o700 or
        not exact_private(PASSFILE) or not exact_private(PENDING)):
        return "BLOCKED_PRIVATE_ARTIFACTS"
    try:
        record=json.loads(PENDING.read_text(encoding="utf-8"))
        if (record.get("schema")!="empire.crm.founder_invitation_server_secret.v1"
            or record.get("status")!="PENDING_NOT_SENT"
            or record.get("login_email")!="flavag83@gmail.com"
            or record.get("subject")!="founder:phil_livesley"
            or record.get("tenant_id")!=TENANT
            or not isinstance(record.get("token"),str)
            or not record["token"].startswith("EI1_")
            or len(record["token"])!=47
            or datetime.fromisoformat(record["expires_at_utc"])<=datetime.now(timezone.utc)):
            return "BLOCKED_INVITATION_NOT_CURRENT"
    except Exception:
        return "BLOCKED_INVITATION_UNVERIFIED"
    if all(exact_private(p) for p in (KEY,CONFIG,ENV)):
        try:
            cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
            expected={
                "schema_version":CONFIG_SCHEMA,
                "founder_approval_ref":"founder:approved-private-crm-loopback-20261011",
                "key_id":"empire-crm-founder-20261011-v1",
                "signing_private_key_file":str(KEY),
                "auth_dsn":BASE+"empire_crm_auth_login",
                "membership_dsn":BASE+"empire_crm_membership_login",
                "tenant_dsns":{TENANT:BASE+"empire_crm_tenant_708efd4b53b2"},
            }
            expected_env=(
                "EMPIRE_CRM_PILOT_MODE=APPROVED_READ_ONLY_PILOT\n"
                f"EMPIRE_CRM_PILOT_CONFIG_FILE={CONFIG}\n"
                f"PGPASSFILE={PASSFILE}\n"
            )
            if cfg==expected and ENV.read_text(encoding="ascii")==expected_env:
                return "ALREADY_STAGED"
        except Exception:
            pass
        return "BLOCKED_STAGED_CONTENT_MISMATCH"
    if any(p.exists() or p.is_symlink() for p in (KEY,CONFIG,ENV)):
        return "BLOCKED_PARTIALLY_STAGED"
    return "READY"


def _create_private(path: Path,payload: bytes) -> None:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as output:
        os.fchmod(output.fileno(),0o600)
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def stage() -> None:
    key=Ed25519PrivateKey.generate()
    pem=key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    data={
        "schema_version":CONFIG_SCHEMA,
        "founder_approval_ref":"founder:approved-private-crm-loopback-20261011",
        "key_id":"empire-crm-founder-20261011-v1",
        "signing_private_key_file":str(KEY),
        "auth_dsn":BASE+"empire_crm_auth_login",
        "membership_dsn":BASE+"empire_crm_membership_login",
        "tenant_dsns":{TENANT:BASE+"empire_crm_tenant_708efd4b53b2"},
    }
    staged_env=(
        "EMPIRE_CRM_PILOT_MODE=APPROVED_READ_ONLY_PILOT\n"
        f"EMPIRE_CRM_PILOT_CONFIG_FILE={CONFIG}\n"
        f"PGPASSFILE={PASSFILE}\n"
    )
    _create_private(KEY,pem)
    _create_private(CONFIG,(json.dumps(data,sort_keys=True)+"\n").encode("utf-8"))
    _create_private(ENV,staged_env.encode("ascii"))
    if not all(exact_private(p) for p in (KEY,CONFIG,ENV)):
        raise RuntimeError("private file metadata not exact")


def offline_check() -> bool:
    from fastapi.testclient import TestClient
    from empire_os.revenue_crm_pilot_service import build_revenue_crm_pilot_service
    from empire_os.revenue_crm_first_party_login import PostgresCrmPasswordLogin
    from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    original={name:os.environ.get(name) for name in
              ("EMPIRE_CRM_PILOT_MODE","EMPIRE_CRM_PILOT_CONFIG_FILE","PGPASSFILE")}
    try:
        os.environ.update({
            "EMPIRE_CRM_PILOT_MODE":"APPROVED_READ_ONLY_PILOT",
            "EMPIRE_CRM_PILOT_CONFIG_FILE":str(CONFIG),
            "PGPASSFILE":str(PASSFILE),
        })
        service=build_revenue_crm_pilot_service()
        client=TestClient(service)
        if client.get("/health").status_code!=200:
            return False
        if client.get("/openapi.json").status_code!=404:
            return False
        for path in ("/v1/revenue-crm/prospects","/v1/revenue-crm/buyers"):
            if client.get(path,headers={"X-Role":"owner","X-Tenant-ID":TENANT}).status_code!=401:
                return False
        auth_dsn=BASE+"empire_crm_auth_login"
        membership_dsn=BASE+"empire_crm_membership_login"
        reader_dsn=BASE+"empire_crm_tenant_708efd4b53b2"
        member=EmpireDbCrmMembershipReader(membership_dsn)(
            "founder:phil_livesley", TENANT
        )
        if member is None or not member.can("read"):
            return False
        if PostgresCrmPasswordLogin(auth_dsn).active_account("founder:phil_livesley"):
            return False  # must remain pending, not a live human login
        repo=PostgresRevenueCrmRepository(reader_dsn,tenant_id=TENANT)
        return len(repo.prospects(limit=1))<=1 and len(repo.buyers(limit=1))<=1
    except Exception:
        return False
    finally:
        for name,value in original.items():
            if value is None:
                os.environ.pop(name,None)
            else:
                os.environ[name]=value


def main() -> int:
    if sys.argv[1:] not in (["--preflight"],["--stage-once"],["--verify"]):
        print("CRM_PRIVATE_STAGE=BLOCKED_FLAGS")
        return 3
    if os.geteuid()!=pwd.getpwnam("ubuntu").pw_uid:
        print("CRM_PRIVATE_STAGE=BLOCKED_SERVICE_IDENTITY")
        return 3
    current=prerequisites()
    if sys.argv[1:]==["--preflight"]:
        print("CRM_PRIVATE_STAGE="+current)
        return 0 if current in ("READY","ALREADY_STAGED") else 2
    if sys.argv[1:]==["--stage-once"] and current=="READY":
        try:
            stage()
        except Exception:
            print("CRM_PRIVATE_STAGE=UNVERIFIED_RECONCILE_NO_RETRY")
            return 4
        current=prerequisites()
    if current!="ALREADY_STAGED":
        print("CRM_PRIVATE_STAGE="+current)
        return 2
    if not offline_check():
        print("CRM_PRIVATE_STAGE=OFFLINE_RUNTIME_PROOF_FAILED_NO_START")
        return 4
    print("CRM_PRIVATE_STAGE=CONFIG_SIGNER_PGPASS_OFFLINE_VERIFIED")
    print("CRM_PRIVATE_HTTP_LISTENER_STARTED=NO")
    print("CRM_PRIVATE_SENDER_USED=NO")
    print("CRM_PRIVATE_FOUNDER_ACCOUNT_REDEEMED=NO")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
