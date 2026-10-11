#!/usr/bin/env python3
"""One-time founder-approved, pending first-party CRM invitation in EmpireDB.

No HTTP endpoint, no send, no new tenant/member/role, no account activation.
Token remains only in a private server-side, service-owned 0600 file.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
from datetime import datetime
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from empire_os.revenue_crm_first_party_login import (
    PreparedCrmInvitation, prepare_crm_invitation,
)
from empire_os.revenue_crm_pilot_operator import PostgresCrmInviteOperator

TENANT="708efd4b-53b2-43d7-961d-1cecab67f17a"
SUBJECT="founder:phil_livesley"
EMAIL="flavag83@gmail.com"
FOUNDER_PROOF="founder:approved-one-founder-crm-invite-20261011"
RECIPIENT_PROOF="verified-email:gmail-oauth-founder-profile-20261011"
IDENTITY_PROOF="person:connected-gmail-owner-verified-20261011"
STORE=Path("/var/lib/empire-crm-first-party")
INVITE_DIR=STORE/"founder_invitation"
TOKEN_FILE=INVITE_DIR/"pending_invitation.json"
LOCK=Path("/run/lock/empire-crm-founder-one-invite.lock")
DB_DSN="host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5"


def _catalog(expected_hash: bytes | None = None) -> dict:
    import psycopg
    with psycopg.connect(DB_DSN) as connection:
        with connection.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='5000ms'")
            cur.execute("SELECT current_database(),session_user,pg_is_in_recovery()")
            database,session,recovery=cur.fetchone()
            cur.execute(
                "SELECT count(*) FROM public.empire_crm_tenant_memberships "
                "WHERE subject=%s AND tenant_id=%s::uuid AND role='owner' "
                "AND status='active' AND verified_at<=clock_timestamp() "
                "AND revoked_at IS NULL "
                "AND (valid_until IS NULL OR valid_until>clock_timestamp()) "
                "AND NULLIF(BTRIM(evidence_ref),'') IS NOT NULL",
                (SUBJECT,TENANT),
            )
            member=cur.fetchone()[0]==1
            cur.execute(
                "SELECT count(*) FROM public.empire_crm_tenant_memberships "
                "WHERE subject=%s",(SUBJECT,),
            )
            unique_member=cur.fetchone()[0]==1
            cur.execute(
                "SELECT count(*) FROM public.empire_crm_login_credentials "
                "WHERE subject=%s OR login_email=%s OR invitation_tenant_id=%s::uuid",
                (SUBJECT,EMAIL,TENANT),
            )
            empty=cur.fetchone()[0]==0
            pending=False
            if expected_hash is not None:
                cur.execute(
                    "SELECT count(*),bool_and(status='pending' AND "
                    "password_change_required AND invitation_redeemed_at IS NULL "
                    "AND invitation_tenant_id=%s::uuid "
                    "AND invitation_expires_at>clock_timestamp() "
                    "AND invitation_token_hash=%s "
                    "AND position(%s in evidence_ref)>0 "
                    "AND position(%s in evidence_ref)>0) "
                    "FROM public.empire_crm_login_credentials "
                    "WHERE subject=%s AND login_email=%s",
                    (TENANT,expected_hash,FOUNDER_PROOF,RECIPIENT_PROOF,SUBJECT,EMAIL),
                )
                total,matching=cur.fetchone()
                pending=(total==1 and matching is True)
    canonical=database=="empiredb" and session=="postgres" and recovery is False
    return {
        "schema":"empire.crm.founder_single_invitation.v1",
        "canonical_operator_database":canonical,
        "one_existing_active_owner_membership":member and unique_member,
        "founder_account_slot_empty":empty,
        "pending_invitation_verified":pending,
        "status":("READY" if canonical and member and unique_member and empty
                  else "PENDING_VERIFIED" if canonical and member and unique_member and pending
                  else "BLOCKED"),
    }


def _read_back(payload: dict) -> dict:
    hashed=bytes.fromhex(payload["invitation_hash_sha256"])
    return _catalog(hashed)


def _as_postgres(mode: str,payload: dict | None=None) -> dict:
    cmd=["runuser","-u","postgres","--",sys.executable,str(Path(__file__).resolve()),mode]
    result=subprocess.run(cmd,input=json.dumps(payload) if payload else None,
                          capture_output=True,text=True,timeout=20)
    if result.returncode!=0:
        raise RuntimeError("privileged CRM founder invitation operation blocked")
    try:
        return json.loads(result.stdout)
    except Exception:
        raise RuntimeError("privileged CRM invitation response invalid") from None


def _check_store() -> None:
    owner=pwd.getpwnam("ubuntu")
    if STORE.is_symlink() or not STORE.is_dir():
        raise RuntimeError("private CRM directory unavailable")
    s=STORE.stat()
    if s.st_uid!=owner.pw_uid or stat.S_IMODE(s.st_mode)!=0o700:
        raise RuntimeError("private CRM directory metadata unsafe")
    if INVITE_DIR.exists() or INVITE_DIR.is_symlink() or TOKEN_FILE.exists():
        raise RuntimeError("an existing founder invitation vault must be reconciled")


def _release_guard() -> None:
    relative="scripts/provision_founder_crm_single_invitation.py"
    def git(*args):
        p=subprocess.run(["git","-c",f"safe.directory={ROOT}","-C",str(ROOT),*args],
                         capture_output=True,text=True,check=True,timeout=5)
        return p.stdout.strip()
    if (git("status","--porcelain","--",relative)
        or git("hash-object",str(Path(__file__).resolve()))
           !=git("rev-parse","HEAD:"+relative)):
        raise RuntimeError("founder invitation source is not the reviewed commit")


def _store_token(packet: PreparedCrmInvitation) -> None:
    owner=pwd.getpwnam("ubuntu")
    INVITE_DIR.mkdir(mode=0o700)
    os.chown(INVITE_DIR,owner.pw_uid,owner.pw_gid)
    if INVITE_DIR.is_symlink() or stat.S_IMODE(INVITE_DIR.stat().st_mode)!=0o700:
        raise RuntimeError("invitation directory security mismatch")
    content=json.dumps({
        "schema":"empire.crm.founder_invitation_server_secret.v1",
        "status":"PENDING_NOT_SENT",
        "login_email":EMAIL,
        "subject":SUBJECT,
        "tenant_id":TENANT,
        "token":packet.token,
        "expires_at_utc":packet.expires_at.isoformat(),
    },sort_keys=True).encode()
    fd=os.open(TOKEN_FILE,os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as output:
        os.fchmod(output.fileno(),0o600)
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    os.chown(TOKEN_FILE,owner.pw_uid,owner.pw_gid)
    if (TOKEN_FILE.is_symlink() or TOKEN_FILE.stat().st_uid!=owner.pw_uid
        or stat.S_IMODE(TOKEN_FILE.stat().st_mode)!=0o600):
        raise RuntimeError("invitation token metadata unsafe")


def _payload(packet: PreparedCrmInvitation) -> dict:
    return {
        "subject":packet.subject,
        "email":packet.login_email,
        "tenant_id":packet.invitation_tenant_id,
        "token":packet.token,
        "token_hash":base64.b64encode(packet.invitation_token_hash).decode(),
        "salt":base64.b64encode(packet.password_salt).decode(),
        "digest":base64.b64encode(packet.password_digest).decode(),
        "evidence_ref":packet.evidence_ref,
        "expires_at":packet.expires_at.isoformat(),
    }


def _insert_once(data: dict) -> dict:
    invitation=PreparedCrmInvitation(
        subject=data["subject"],login_email=data["email"],
        invitation_tenant_id=data["tenant_id"],token=data["token"],
        invitation_token_hash=base64.b64decode(data["token_hash"],validate=True),
        password_salt=base64.b64decode(data["salt"],validate=True),
        password_digest=base64.b64decode(data["digest"],validate=True),
        evidence_ref=data["evidence_ref"],
        expires_at=datetime.fromisoformat(data["expires_at"]),
    )
    if (invitation.subject!=SUBJECT or invitation.login_email!=EMAIL
        or invitation.invitation_tenant_id!=TENANT
        or invitation.evidence_ref!=IDENTITY_PROOF):
        raise RuntimeError("unexpected founder invitation identity")
    if _catalog()["status"]!="READY":
        raise RuntimeError("founder CRM invitation already provisioned or blocked")
    operator=PostgresCrmInviteOperator(DB_DSN)
    success=operator.provision(
        invitation,founder_approval_ref=FOUNDER_PROOF,
        verified_recipient_ref=RECIPIENT_PROOF,
    )
    if not success:
        raise RuntimeError("one-use invitation insert rejected")
    return {"status":"ONE_PENDING_ACCOUNT_INSERTED"}


def main() -> int:
    args=sys.argv[1:]
    if args in (["--internal-preflight"],["--internal-insert"],["--internal-readback"]):
        if os.geteuid()!=pwd.getpwnam("postgres").pw_uid:
            return 3
        try:
            if args==["--internal-preflight"]:
                response=_catalog()
            elif args==["--internal-insert"]:
                response=_insert_once(json.load(sys.stdin))
            else:
                response=_read_back(json.load(sys.stdin))
            print(json.dumps(response,sort_keys=True))
            return 0
        except Exception:
            return 4
    if args not in (["--preflight"],["--apply","--approved-one-founder-crm-invitation"]):
        print("CRM_INVITATION_RESULT=BLOCKED_EXACT_APPROVAL_FLAGS_REQUIRED")
        return 3
    if os.geteuid()!=0:
        print("CRM_INVITATION_RESULT=BLOCKED_PRIVILEGED_OPERATOR_REQUIRED")
        return 3
    try:
        with LOCK.open("a+") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
            baseline=_as_postgres("--internal-preflight")
            _check_store()
            if baseline.get("status")!="READY":
                print("CRM_INVITATION_RESULT=BLOCKED_EXISTING_OR_UNVERIFIED_ACCOUNT")
                return 2
            print("CRM_INVITATION_PREFLIGHT=ONE_ACTIVE_FOUNDER_NO_CREDENTIALS")
            if args==["--preflight"]:
                print("CRM_INVITATION_RESULT=PREFLIGHT_READY_NO_CHANGES")
                return 0
            _release_guard()
            packet=prepare_crm_invitation(
                subject=SUBJECT,email=EMAIL,tenant_id=TENANT,evidence_ref=IDENTITY_PROOF,
            )
            # Store secret before transaction, never write to stdout or argv.
            _store_token(packet)
            print("CRM_INVITATION_TOKEN=SECURED_ON_SERVER_NOT_SENT")
            inserted=_as_postgres("--internal-insert",_payload(packet))
            if inserted.get("status")!="ONE_PENDING_ACCOUNT_INSERTED":
                raise RuntimeError("invitation insert outcome uncertain")
            print("CRM_INVITATION_DB_TRANSACTION=ONE_PENDING_ROW_COMMITTED")
            proof=_as_postgres("--internal-readback",{
                "invitation_hash_sha256":hashlib.sha256(packet.token.encode("ascii")).hexdigest()
            })
            if proof.get("status")!="PENDING_VERIFIED":
                raise RuntimeError("founder pending-account readback unverified")
            print("CRM_INVITATION_POSTCOMMIT=ONE_PENDING_FOUNDER_VERIFIED")
            print("CRM_INVITATION_EMAIL_SENT=NO")
            print("CRM_INVITATION_HTTP_ACTIVATED=NO")
            print("CRM_INVITATION_RESULT=ONE_PENDING_INVITATION_VERIFIED")
            return 0
    except Exception:
        print("CRM_INVITATION_RESULT=BLOCKED_OR_UNVERIFIED_DO_NOT_BLINDLY_RETRY")
        return 4


if __name__=="__main__":
    raise SystemExit(main())
