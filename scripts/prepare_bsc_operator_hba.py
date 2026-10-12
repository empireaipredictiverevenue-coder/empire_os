#!/usr/bin/env python3
"""One-shot exact two-login SCRAM HBA plan for existing BSC financial roles.

--preflight is read-only. --apply requires distinct founder approval
--approved-exact-two-bsc-financial-hba-rules and separately reviewed clean
checked-in release. No LOGIN creation, financial grants, checkout activation,
payment requests, outbound, migrations, or PostgreSQL process restart.

Reuses established Empire CRM HBA atomic backup/reload helpers.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from empire_os.bsc_payment_operator_readiness import LOGIN_ROLES
from scripts import deploy_crm_hba_three_roles as prior

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = Path("/var/backups/empiredb/bsc-two-operator-hba")
LOCK = Path("/run/lock/empire-bsc-two-operator-hba.lock")
HEADER_BEGIN = "# BEGIN EMPIRE_BSC_TWO_FINANCIAL_OPERATORS_V1"
HEADER_END = "# END EMPIRE_BSC_TWO_FINANCIAL_OPERATORS_V1"
EXACT = (
    HEADER_BEGIN+"\n"
    "# Two exact local SCRAM identities; immutable existing pg_hba.conf tail.\n"
    "local   empiredb   empire_payment_approver_login   scram-sha-256\n"
    "local   empiredb   empire_escrow_verifier_login    scram-sha-256\n"
    +HEADER_END+"\n"
).encode("ascii")


def additive_hba_patch(original: bytes) -> bytes:
    """Pure byte-preserving prepend only; refuse duplicates/unexpected layout."""
    if not isinstance(original, bytes) or not original.strip() or b"\x00" in original:
        raise ValueError("invalid existing pg_hba.conf")
    if b"\r" in original:
        raise ValueError("unknown line endings in pg_hba.conf")
    if HEADER_BEGIN.encode() in original or HEADER_END.encode() in original:
        raise ValueError("exact HBA marker already present")
    # Duplicate role-specific rules anywhere in existing file require review.
    for line in original.decode("utf-8", "strict").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        parts = stripped.split("#")[0].split()
        if len(parts) >= 3 and any(role in parts[2].split(",") for role in LOGIN_ROLES):
            raise ValueError("pre-existing financial LOGIN HBA rule")
    return EXACT + original


def release_source_checked_in() -> None:
    relative="scripts/prepare_bsc_operator_hba.py"
    try:
        def git(*args: str) -> str:
            return subprocess.run(
                ["git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), *args],
                capture_output=True, text=True, timeout=5, check=True
            ).stdout.strip()
        if git("status","--porcelain","--",relative):
            raise RuntimeError("dirty source")
        if git("hash-object",str(ROOT/relative)) != git("rev-parse","HEAD:"+relative):
            raise RuntimeError("uncommitted source")
    except Exception as exc:
        raise RuntimeError("financial HBA operator source not reviewed") from None


def _report() -> dict:
    """Run privileged catalog-only inspection as postgres."""
    code = (
        "import json,psycopg;"
        "from empire_os.bsc_payment_operator_readiness import inspect_catalog;"
        "r=inspect_catalog(lambda:psycopg.connect("
        "'host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5'));"
        "print(json.dumps(r,sort_keys=True))"
    )
    result=subprocess.run(
        ["runuser","-u","postgres","--",sys.executable,"-c",code],
        cwd=str(ROOT),env={**os.environ,"PYTHONPATH":str(ROOT)},
        capture_output=True,text=True,timeout=13,check=True,
    )
    return json.loads(result.stdout)


def _backup(original: bytes) -> Path:
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BACKUPS.is_symlink():
        raise RuntimeError("backup directory symlink")
    when=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory=BACKUPS/when
    directory.mkdir(mode=0o700)
    target=directory/"pg_hba.conf.before"
    fd=os.open(target,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as out:
        out.write(original);out.flush();os.fsync(out.fileno())
    digest=hashlib.sha256(original).hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    fd=os.open(directory/"SHA256",os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        f.write(digest+"  pg_hba.conf.before\n")
        f.flush();os.fsync(f.fileno())
    return directory


def main() -> int:
    flags=sys.argv[1:]
    approved=flags==["--apply","--approved-exact-two-bsc-financial-hba-rules"]
    if flags not in (["--preflight"],["--apply","--approved-exact-two-bsc-financial-hba-rules"]):
        print("BSC_FINANCIAL_HBA_STATUS=BLOCKED_EXACT_FLAGS_REQUIRED")
        return 3
    if os.geteuid()!=0:
        print("BSC_FINANCIAL_HBA_STATUS=BLOCKED_ROOT_OPERATOR_REQUIRED")
        return 3
    try:
        with LOCK.open("a+") as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            prior.cluster_guard()
            attrs, original=prior.owner_and_content()
            before=_report()
            if before["status"]=="READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING":
                print("BSC_FINANCIAL_HBA_STATUS=ALREADY_READY_NO_CHANGE")
                return 0
            if before["status"]!="PREPARE_EXACT_TWO_LOCAL_SCRAM_HBA_RULES":
                print("BSC_FINANCIAL_HBA_STATUS=BLOCKED_DB_SECURITY_PREFLIGHT")
                return 2
            proposed=additive_hba_patch(original)
            print("BSC_FINANCIAL_HBA_SCOPE=EXACT_TWO_LOCAL_SCRAM_LOGIN_RULES")
            print("BSC_FINANCIAL_HBA_ORIGINAL_SHA256="+hashlib.sha256(original).hexdigest())
            print("BSC_FINANCIAL_HBA_ALL_EXISTING_BYTES_PRESERVED="+str(proposed.endswith(original)))
            print("BSC_FINANCIAL_HBA_WRITES_AUTHORIZED="+str(approved))
            if not approved:
                print("BSC_FINANCIAL_HBA_STATUS=READY_FOR_EXPLICIT_FOUNDER_APPROVAL")
                return 0
            release_source_checked_in()
            before_load_time=prior.invoke_psql(statement="SELECT pg_conf_load_time()")
            backup=_backup(original)
            print("BSC_FINANCIAL_HBA_BACKUP_SHA256=VERIFIED")
            print("BSC_FINANCIAL_HBA_BACKUP_PATH="+str(backup))
            if prior.HBA.is_symlink() or prior.HBA.read_bytes()!=original:
                raise RuntimeError("concurrent HBA edit")
            prior.atomic_write_hba(proposed, attrs)
            try:
                prior.reload()
                import time
                for _ in range(12):
                    final=_report()
                    if (final["status"]=="READY_FOR_SEPARATELY_APPROVED_TWO_LOGIN_PROVISIONING"
                            and prior.invoke_psql(statement="SELECT pg_conf_load_time()")!=before_load_time):
                        print("BSC_FINANCIAL_HBA_POST_RELOAD=EXACT_TWO_FIRST_MATCH_SCRAM_RULES_VERIFIED")
                        print("BSC_FINANCIAL_HBA_FINANCIAL_ROLES_AND_PASSWORDS_CHANGED=NO")
                        print("BSC_FINANCIAL_HBA_CHECKOUT_ACTIVATED=NO")
                        print("BSC_FINANCIAL_HBA_STATUS=EXACT_TWO_SCRAM_RULES_APPLIED")
                        return 0
                    time.sleep(.2)
                raise RuntimeError("post reload HBA verification failed")
            except Exception:
                if prior.HBA.read_bytes()==proposed:
                    prior.atomic_write_hba(original,attrs)
                    try:
                        prior.reload()
                        print("BSC_FINANCIAL_HBA_ROLLBACK=ORIGINAL_BYTES_RESTORED")
                    except Exception:
                        print("BSC_FINANCIAL_HBA_ROLLBACK=MANUAL_RECONCILIATION_REQUIRED")
                else:
                    print("BSC_FINANCIAL_HBA_ROLLBACK=BLOCKED_CONCURRENT_CHANGE")
                raise
    except Exception:
        print("BSC_FINANCIAL_HBA_STATUS=BLOCKED_REVIEW_REQUIRED_NO_BLIND_RETRY")
        return 4


if __name__=="__main__":
    raise SystemExit(main())
