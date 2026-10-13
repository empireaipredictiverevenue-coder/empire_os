"""Read-only diagnostic for the failed private status backend release.

No systemd changes, key rotation, new token, payment or customer writes.
Test existing root-only credentials in memory; output stage names only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from empire_os import direct_bsc_buyer_checkout_release as checkout
from scripts import deploy_direct_bsc_buyer_status_release as release
from scripts.inspect_direct_bsc_status_logins_readonly import prove
from empire_os.direct_bsc_status_key_custody import read_key
from empire_os.direct_bsc_buyer_status_private_reader import PrivateBuyerStatusPostgresReader
from empire_os.direct_bsc_buyer_status_runtime import create_staged_private_status_app
from fastapi.testclient import TestClient


_BSC_NAMES = {
    "BSC_RPC_URL","BSC_TREASURY_ADDRESS",
    "BSC_USDT_TOKEN_CONTRACT","BSC_MIN_CONFIRMATIONS",
}
BSC_DROPIN = Path(
    "/etc/systemd/system/empire-self-serve-checkout.service.d/"
    "30-direct-bsc-readonly.conf"
)


def _systemd_bsc_env() -> dict[str,str]:
    """Read only the existing active BSC systemd drop-in, never DB secrets.

    This checkout uses Environment= directives from drop-in 30, NOT
    BSC_* entries in /etc/empire_os.env or /etc/empiredb.env.
    """
    import stat
    import subprocess
    import shlex
    path=BSC_DROPIN
    if path.is_symlink() or not path.is_file():
        raise ValueError("canonical BSC systemd drop-in missing")
    metadata=path.stat()
    if (not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid!=0 or metadata.st_mode & 0o022):
        raise ValueError("BSC drop-in ownership or permissions unsafe")
    check=subprocess.run(
        ["systemctl","show","empire-self-serve-checkout.service",
         "-p","DropInPaths","--value"],
        text=True,capture_output=True,check=False,timeout=5,
    )
    if check.returncode!=0 or str(path) not in check.stdout.split():
        raise ValueError("BSC drop-in is not the active service configuration")
    config={}
    for line in path.read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if not line or line.startswith(("#","[")):
            continue
        if not line.startswith("Environment="):
            continue
        try:
            assignments=shlex.split(line.split("=",1)[1],posix=True)
        except ValueError:
            raise ValueError("invalid systemd environment syntax") from None
        for entry in assignments:
            name,sep,value=entry.partition("=")
            if not sep or name not in _BSC_NAMES:
                continue
            if name in config or not value or any(c in value for c in ("\x00","\n","\r")):
                raise ValueError("duplicate or invalid BSC configuration")
            config[name]=value
    if not config.get("BSC_RPC_URL") or not config.get("BSC_TREASURY_ADDRESS"):
        raise ValueError("canonical BSC settings missing from active drop-in")
    if config.get("BSC_MIN_CONFIRMATIONS")!="12":
        raise ValueError("BSC confirmation minimum changed")
    return config


def diagnose() -> dict:
    if os.geteuid()!=0:
        raise ValueError("root-only readback required")
    stages={}
    def check(name,fn):
        try:
            result=fn()
            stages[name]="PASS" if result is not False else "HELD"
            return result
        except Exception as exc:
            stages[name]="HELD_"+type(exc).__name__
            return None
    check("committed_sources",release._reviewed)
    check("published_checkout",release._published_checkout_verified)
    check("existing_units",release._verify_unit_targets)
    check("existing_logins",release._verify_login_file)
    check("checkout_authority_unchanged",release.checkout_financial_execution_held)
    check("checkout_health",release._snapshot)
    check("fresh_independent_chain",release._chain_verified)
    check("installed_hmac_key",read_key)
    info=check("service_bsc_env_metadata",_systemd_bsc_env)
    config=None
    if info:
        with patch.dict(os.environ,info,clear=False):
            with patch.object(checkout,"_credential_dir",return_value=Path("/etc")):
                config=check("actual_status_runtime_config",checkout._config)
            if config:
                reader_dsn,issuer_dsn,key,treasury=config
                reader=PrivateBuyerStatusPostgresReader(reader_dsn)
                check("restricted_reader_nonexistent_fingerprint",
                      lambda:reader("0"*64) is None)
                check("service_env_chain",lambda:
                      checkout._chain_verified() is True)
                def unknown_token_test():
                    app=create_staged_private_status_app(
                        reader_dsn=reader_dsn,hmac_key=key,
                        treasury_address=treasury,
                        allow_request=lambda peer: True,
                        founder_release=lambda:True,
                        verified_chain=lambda:True,
                    )
                    response=TestClient(app).post(
                        "/v1/checkout/payment-status",
                        json={"token":"ecs1_"+"A"*43},
                        headers={
                            "Origin":"https://empire-ai.co.uk",
                            "Content-Type":"application/json",
                            "Sec-Fetch-Site":"same-origin",
                        },
                    )
                    return (response.status_code==404 and response.json()
                            =={"error":"payment_status_unavailable"})
                check("isolated_private_http_nonissued_bearer",unknown_token_test)
    return {
        "status":"DIRECT_BSC_STATUS_FAILED_RELEASE_READONLY_DIAGNOSTIC",
        "mode":"READ_ONLY",
        "stages":stages,
        "secrets_disclosed":False,
        "buyer_data_disclosed":False,
        "payment_execution":False,
        "new_payment_requests":False,
        "service_changes":False,
        "key_rotated":False,
    }


def main(args: list[str]|None=None)->int:
    args=sys.argv[1:] if args is None else args
    if args!=["--read-only"]:
        print(json.dumps({"status":"HELD_EXACT_READONLY_FLAG_REQUIRED"}))
        return 3
    try:
        result=diagnose()
    except Exception:
        print(json.dumps({"status":"HELD_DIAGNOSTIC_NO_WRITES",
                          "secrets_disclosed":False}))
        return 4
    print(json.dumps(result,sort_keys=True))
    return 0 if all(v=="PASS" for v in result["stages"].values()) else 2


if __name__=="__main__":
    raise SystemExit(main())
