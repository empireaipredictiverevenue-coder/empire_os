"""Guarded one-shot direct BSC buyer-status release.

Never enables payment execution, revenue recognition, automatic approval,
outbound email or wallet transfers. Existing orders remain founder-authorised.
Only explicit --apply with exact founder release flag can modify systemd.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

from empire_os.direct_bsc_status_key_custody import (
    KEY_FILE,read_key,install_key,
)
from scripts.provision_direct_bsc_buyer_status_logins import (
    checkout_financial_execution_held,_verified_controlled_order_release
)

ROOT=Path("/srv/empire_os")
DROP_DIR=Path("/etc/systemd/system/empire-self-serve-checkout.service.d")
TARGET=DROP_DIR/"50-direct-bsc-buyer-status-release.conf"
LOGIN_FILE=Path("/etc/empire_direct_bsc_buyer_status.env")
APPROVAL="--approved-direct-bsc-buyer-status-release-only"
REVIEW_FILES=(
    "empire_os/direct_bsc_status_key_custody.py",
    "empire_os/direct_bsc_buyer_receipt_bridge.py",
    "empire_os/direct_bsc_buyer_checkout_release.py",
    "empire_os/direct_bsc_buyer_status_runtime.py",
    "empire_os/direct_bsc_buyer_status_http.py",
    "empire_os/direct_bsc_buyer_status_private_reader.py",
    "empire_os/direct_bsc_buyer_status_private_issuer.py",
    "empire_os/self_serve_checkout_api.py",
    "empire_os/public_gateway.py",
    "scripts/deploy_direct_bsc_buyer_status_release.py",
)
DROPIN=(
    "[Service]\n"
    "# Exact founder-gated first-party buyer-status release only.\n"
    "# NO payment approval, settlement, send, new role or treasury change.\n"
    "LoadCredential=empire_direct_bsc_buyer_status_hmac.key:"
    "/etc/empire_direct_bsc_buyer_status_hmac.key\n"
    "LoadCredential=empire_direct_bsc_buyer_status.env:"
    "/etc/empire_direct_bsc_buyer_status.env\n"
    "Environment=EMPIRE_DIRECT_BSC_BUYER_STATUS_RELEASE=ON\n"
)


def _run(*args: str, timeout: float=20)->str:
    result=subprocess.run(
        args,check=True,timeout=timeout,cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
    )
    return result.stdout.strip()


def _reviewed()->None:
    for filename in REVIEW_FILES:
        local=ROOT/filename
        if not local.is_file():
            raise ValueError("reviewed source missing")
        path_check=_run("git","-c",f"safe.directory={ROOT}","status",
                        "--porcelain","--",filename)
        if path_check:
            raise ValueError("reviewed source changed")
        sha=_run("git","-c",f"safe.directory={ROOT}","hash-object",filename)
        committed=_run("git","-c",f"safe.directory={ROOT}","rev-parse",
                       "HEAD:"+filename)
        if sha!=committed:
            raise ValueError("source does not match committed release")


def _health()->dict:
    request=urllib.request.Request("http://127.0.0.1:8098/health")
    with urllib.request.urlopen(request,timeout=5) as response:
        result=json.load(response)
    if not isinstance(result,dict):
        raise ValueError("invalid checkout health")
    return result


def _snapshot()->tuple:
    data=_health()
    return tuple(data.get(field) for field in (
        "status","checkout_settlement_mode",
        "payment_proposal_authorized",
        "binding_order_creation_authorized",
        "payment_execution","revenue_recognition",
    ))


def _verify_unit_targets()->None:
    if DROP_DIR.is_symlink() or not DROP_DIR.is_dir():
        raise ValueError("untrusted checkout drop-in directory")
    if TARGET.exists() or TARGET.is_symlink():
        raise ValueError("existing status drop-in requires reconciliation")
    unit=Path("/etc/systemd/system/empire-self-serve-checkout.service")
    gateway=Path("/etc/systemd/system/empire-public-gateway.service")
    for item in (unit,gateway):
        if item.is_symlink() or not item.is_file():
            raise ValueError("original unit missing")
    if not _verified_controlled_order_release():
        raise ValueError("existing founder-approved order release not verified")


def _verify_login_file()->None:
    if LOGIN_FILE.is_symlink() or not LOGIN_FILE.is_file():
        raise ValueError("dedicated DSN credential file absent")
    stat=LOGIN_FILE.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o777 != 0o600:
        raise ValueError("dedicated DSN credential unsafe")
    result=_run(sys.executable,"-m",
          "scripts.inspect_direct_bsc_status_logins_readonly",
          "--verify-only",timeout=20)
    data=json.loads(result)
    if data.get("status")!="DEDICATED_STATUS_LOGINS_LIVE_READBACK_VERIFIED":
        raise ValueError("dedicated login readback failed")


def _chain_verified()->dict:
    from empire_os.self_serve_payment_readiness import verify_checkout_bsc_chain
    from empire_os.bsc_usdt_verifier import BSC_USDT_CONTRACT,BscUsdtConfig
    config=BscUsdtConfig(
        rpc_url="https://bsc-dataseed.bnbchain.org",
        treasury_address="0x1339b487046B0ad924a10c20b1791608EA8595a8",
        token_contract=BSC_USDT_CONTRACT,
        min_confirmations=12,
    )
    result=verify_checkout_bsc_chain(config=config)
    if result.get("chain_verified") is not True or result.get("chain_id")!=56 or result.get("token_decimals")!=18:
        raise ValueError("chain / canonical token not independently verified")
    return {
        "chain_verified":True,"chain_id":56,"token_decimals":18,
        "fresh_block_anchor":True,
    }


def _status_probe()->None:
    # Correctly formatted but never-issued fixed bearer. No DB writes,
    # no order UUID, no buyer PII, no bearer disclosed to logs.
    unknown="ecs1_"+"A"*43
    payload=json.dumps({"token":unknown}).encode("utf-8")
    for url in ("http://127.0.0.1:8098/v1/checkout/payment-status",
                "http://127.0.0.1/v1/checkout/payment-status"):
        request=urllib.request.Request(
            url, data=payload,
            headers={"Origin":"https://empire-ai.co.uk",
                     "Sec-Fetch-Site":"same-origin",
                     "Content-Type":"application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request,timeout=15) as response:
                code=response.status
                body=json.load(response)
        except urllib.error.HTTPError as error:
            code=error.code
            body=json.loads(error.read())
        if code!=404 or body!={"error":"payment_status_unavailable"}:
            raise ValueError("status route not serving isolated unknown-token denial")


def _write_dropin()->None:
    fd,temp=tempfile.mkstemp(prefix=".empire-bsc-status-",dir=DROP_DIR)
    try:
        with os.fdopen(fd,"w") as file:
            file.write(DROPIN)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,TARGET)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def release()->dict:
    if os.geteuid()!=0:
        raise ValueError("root release operator required")
    _reviewed()
    _verify_unit_targets()
    _verify_login_file()
    checkout_financial_execution_held()
    original=_snapshot()
    evidence=_chain_verified()
    if KEY_FILE.exists() or KEY_FILE.is_symlink():
        read_key()
        key_action="EXISTING_KEY_VERIFIED"
    else:
        install_key()
        key_action="NEW_KEY_CREATED_0600"
    changed=False
    try:
        _write_dropin()
        changed=True
        _run("systemctl","daemon-reload")
        _run("systemctl","restart","empire-self-serve-checkout.service")
        _run("systemctl","restart","empire-public-gateway.service")
        if _snapshot()!=original:
            raise ValueError("checkout financial admission changed")
        checkout_financial_execution_held()
        _chain_verified()
        _status_probe()
    except Exception:
        if changed:
            # Restore the former systemd configuration, leaving the
            # key file for forensic reconciliation (never rotate).
            TARGET.unlink(missing_ok=True)
            try:
                _run("systemctl","daemon-reload")
                _run("systemctl","restart","empire-self-serve-checkout.service")
                _run("systemctl","restart","empire-public-gateway.service")
            except Exception:
                pass
        raise
    return {
        "status":"DIRECT_BSC_PRIVATE_BUYER_STATUS_RELEASE_VERIFIED",
        "key":key_action,
        "logins":"EXISTING_TWO_REUSED",
        "frontend_deployed":False,
        "status_token_issued":False,
        "public_status_route_unknown_token_denied":True,
        "order_gate_unchanged":True,
        "payment_execution":False,
        "revenue_recognition":False,
        **evidence,
    }


def main(argv: list[str]|None=None)->int:
    argv=sys.argv[1:] if argv is None else argv
    if argv!=["--apply",APPROVAL]:
        print(json.dumps({"status":"STAGED_NOT_APPLIED",
                          "separate_release_approval_required":True}))
        return 0 if not argv else 3
    try:
        result=release()
    except Exception:
        print(json.dumps({
            "status":"HELD_RELEASE_OR_ROLLBACK_NEEDS_READBACK",
            "no_secrets_printed":True,
            "do_not_retry_without_inspection":True,
        }))
        return 4
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
