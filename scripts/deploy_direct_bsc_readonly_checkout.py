#!/usr/bin/env python3
"""One-shot DIRECT BSC READ-ONLY checkout runtime configuration deployment.

Does not enable orders, approve a payment, collect USDT, modify the database,
touch wallet secrets or use the escrow contract. Production service restart
requires a separately explicit founder flag. --preflight makes no writes.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

from empire_os.bsc_usdt_verifier import BSC_USDT_CONTRACT, BscUsdtConfig
from empire_os.self_serve_payment_readiness import verify_checkout_bsc_chain

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "deploy/systemd/30-direct-bsc-readonly.conf"
SOURCE_REL = "deploy/systemd/30-direct-bsc-readonly.conf"
SCRIPT_REL = "scripts/deploy_direct_bsc_readonly_checkout.py"
TARGET_DIR = Path("/etc/systemd/system/empire-self-serve-checkout.service.d")
TARGET = TARGET_DIR / "30-direct-bsc-readonly.conf"
UNIT = Path("/etc/systemd/system/empire-self-serve-checkout.service")
OLDER_OVERRIDE = TARGET_DIR / "20-empiredb-reader.conf"
SERVICE = "empire-self-serve-checkout.service"
BACKUP_BASE = Path("/var/backups/empire-os/direct-bsc-readonly-checkout")
LOCK = Path("/run/lock/empire-direct-bsc-readonly-checkout.lock")
RPC = "https://bsc-dataseed.bnbchain.org"
TREASURY = "0x1339b487046B0ad924a10c20b1791608EA8595a8"
EXPECTED = (
    "[Service]\n"
    "# Empire AI: direct USDT on BSC, first-party custody, public read-only RPC.\n"
    "# STAGED ONLY: This file must not be installed until deployment approval.\n"
    'Environment="EMPIRE_SELF_SERVE_SETTLEMENT_MODE=direct"\n'
    f'Environment="BSC_RPC_URL={RPC}"\n'
    f'Environment="BSC_TREASURY_ADDRESS={TREASURY}"\n'
    'Environment="BSC_MIN_CONFIRMATIONS=12"\n'
    "# Retain fail-closed financial gates until separately verified.\n"
    'Environment="EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF"\n'
    'Environment="EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF"\n'
).encode("ascii")


def _run(*cmd: str) -> str:
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, timeout=18)
    return result.stdout.strip()


def _checked_source():
    if SOURCE.read_bytes() != EXPECTED:
        raise RuntimeError("reviewed direct checkout source drift")
    def git(*args):
        return _run("git", "-c", f"safe.directory={ROOT}", "-C", str(ROOT), *args)
    for rel in (SCRIPT_REL, SOURCE_REL):
        if git("status", "--porcelain", "--", rel):
            raise RuntimeError("dirty deployment source")
        if git("hash-object", str(ROOT / rel)) != git("rev-parse", "HEAD:" + rel):
            raise RuntimeError("uncommitted deployment source")


def _health() -> dict:
    req = urllib.request.Request("http://127.0.0.1:8098/health",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as res:
        body = json.load(res)
    if not isinstance(body, dict) or body.get("status") != "online":
        raise RuntimeError("checkout service unhealthy")
    return body


def _financial_gates_off(health: dict) -> bool:
    return (health.get("payment_proposal_authorized") is False and
            health.get("binding_order_creation_authorized") is False and
            health.get("payment_execution") is False and
            health.get("revenue_recognition") is False)


def _public_chain_probe() -> dict:
    cfg = BscUsdtConfig(rpc_url=RPC, treasury_address=TREASURY,
                        token_contract=BSC_USDT_CONTRACT, min_confirmations=12)
    result = verify_checkout_bsc_chain(config=cfg)
    if result.get("chain_verified") is not True:
        raise RuntimeError("direct BSC read-only chain verification held")
    return {key: result[key] for key in
            ("status", "chain_verified", "chain_id", "token_decimals", "block_age_seconds")}


def _catalog_verifier() -> dict:
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", sys.executable, "-m",
         "scripts.inspect_direct_bsc_verifier_readiness", "--preflight"],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
             "PYTHONPATH": str(ROOT), "HOME": "/var/lib/postgresql"})
    if result.returncode:
        raise RuntimeError("direct verifier catalog preflight failed")
    report = json.loads(result.stdout)
    if (report.get("status") !=
            "DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"):
        raise RuntimeError("direct verifier catalog incomplete")
    return {
        "catalog_status": report["status"],
        "exact_direct_role_membership": report.get("exact_noninherited_role_membership"),
        "connect_only": report.get("database_connect_only"),
        "effective_scram": report.get("effective_local_scram"),
    }


def _target_safe() -> None:
    if not TARGET_DIR.is_dir() or TARGET_DIR.is_symlink():
        raise RuntimeError("unexpected unit drop-in directory")
    if TARGET.exists() or TARGET.is_symlink():
        raise RuntimeError("direct BSC drop-in already exists: reconcile, do not overwrite")
    for p in (UNIT, OLDER_OVERRIDE):
        if p.is_symlink() or not p.is_file():
            raise RuntimeError("unexpected preexisting unit configuration")
    base = UNIT.read_text()
    previous = OLDER_OVERRIDE.read_text()
    if ("Environment=EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF" not in base
            or "Environment=EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF" not in previous
            or "Environment=EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF" not in previous):
        raise RuntimeError("previous explicit checkout financial gates drift")


def _verify_existing() -> dict:
    _target_safe()
    _checked_source()
    if _run("systemctl", "is-active", SERVICE) != "active":
        raise RuntimeError("checkout service not active")
    health = _health()
    if not _financial_gates_off(health):
        raise RuntimeError("existing financial gates unexpectedly ON")
    if health.get("checkout_settlement_mode") != "direct":
        raise RuntimeError("existing service settlement mode not direct")
    if health.get("bsc_payment_configuration_status") != "BSC_CONFIG_MISSING":
        raise RuntimeError("unexpected existing BSC checkout configuration")
    role = _catalog_verifier()
    chain = _public_chain_probe()
    return {"status": "READY_FOR_SEPARATELY_APPROVED_READONLY_BSC_CONFIG_DEPLOYMENT",
            "mode": "READ_ONLY", "payment_activation": False,
            "checkout_service": "online", "settlement": "direct",
            "all_financial_gates_off": True, "direct_verifier": role,
            "mainnet_read": chain}


def _backup() -> Path:
    BACKUP_BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = BACKUP_BASE.lstat()
    if BACKUP_BASE.is_symlink() or st.st_uid != 0 or st.st_mode & 0o777 != 0o700:
        raise RuntimeError("backup base permission drift")
    folder = BACKUP_BASE / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(mode=0o700)
    checks = []
    for p in (UNIT, OLDER_OVERRIDE):
        payload = p.read_bytes()
        dest = folder / p.name
        fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(payload); out.flush(); os.fsync(out.fileno())
        digest = hashlib.sha256(payload).hexdigest()
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise RuntimeError("backup integrity mismatch")
        checks.append(f"{digest}  {dest.name}")
    checksum = folder / "SHA256"
    checksum.write_text("\n".join(checks) + "\n")
    os.chmod(checksum, 0o600)
    return folder


def _postcheck() -> dict:
    if TARGET.read_bytes() != EXPECTED:
        raise RuntimeError("installed drop-in bytes mismatch")
    health = _health()
    if not _financial_gates_off(health) or health.get("checkout_settlement_mode") != "direct":
        raise RuntimeError("postrestart checkout financial gate drift")
    if health.get("bsc_payment_configuration_status") != "BSC_CONFIGURED_CHAIN_UNVERIFIED":
        raise RuntimeError("configured runtime readback mismatch")
    chain = _public_chain_probe()
    return {"status": "DIRECT_READONLY_BSC_RUNTIME_CONFIG_VERIFIED",
            "service": health["status"], "checkout_settlement_mode": "direct",
            "payment_proposal_authorized": False,
            "binding_order_creation_authorized": False,
            "payment_execution": False, "revenue_recognition": False,
            "chain": chain}


def _root_main(args: list[str]) -> int:
    approved = args == ["--apply", "--approved-direct-bsc-readonly-config-and-checkout-restart"]
    if args not in (["--preflight"],
                    ["--apply", "--approved-direct-bsc-readonly-config-and-checkout-restart"]) or os.geteuid() != 0:
        print("DIRECT_BSC_RUNTIME_STATUS=HELD_EXACT_ROOT_APPROVAL_REQUIRED")
        return 3
    installed = False
    try:
        with LOCK.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            status = _verify_existing()
            print(json.dumps(status, sort_keys=True))
            if not approved:
                return 0
            backup = _backup()
            print("DIRECT_BSC_RUNTIME_BACKUP_SHA256=VERIFIED")
            print("DIRECT_BSC_RUNTIME_BACKUP_DIRECTORY=" + str(backup))
            _target_safe()
            fd = os.open(TARGET, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
            with os.fdopen(fd, "wb") as f:
                f.write(EXPECTED); f.flush(); os.fsync(f.fileno())
            installed = True
            _run("systemctl", "daemon-reload")
            _run("systemctl", "restart", SERVICE)
            for _ in range(10):
                try:
                    post = _postcheck()
                    print(json.dumps(post, sort_keys=True))
                    print("DIRECT_BSC_RUNTIME_STATUS=READONLY_CONFIG_INSTALLED_PAYMENT_FLAGS_OFF")
                    return 0
                except (OSError, RuntimeError):
                    time.sleep(.3)
            raise RuntimeError("checkout readback postrestart held")
    except Exception:
        if installed:
            try:
                if TARGET.read_bytes() != EXPECTED:
                    raise RuntimeError("concurrent drop-in edit")
                TARGET.unlink()
                _run("systemctl", "daemon-reload")
                _run("systemctl", "restart", SERVICE)
                if not _financial_gates_off(_health()):
                    raise RuntimeError("rollback financial gate drift")
                print("DIRECT_BSC_RUNTIME_ROLLBACK=ORIGINAL_SERVICE_CONFIGURATION_RESTORED")
            except Exception:
                print("DIRECT_BSC_RUNTIME_ROLLBACK=MANUAL_RECONCILIATION_REQUIRED")
        print("DIRECT_BSC_RUNTIME_STATUS=HELD_NO_BLIND_RETRY")
        return 4


if __name__ == "__main__":
    raise SystemExit(_root_main(sys.argv[1:]))
