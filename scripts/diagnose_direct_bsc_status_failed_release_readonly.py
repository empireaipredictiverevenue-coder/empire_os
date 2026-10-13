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


def _systemd_bsc_env() -> dict[str,str]:
    """Read ONLY the four named settings from existing service env files."""
    config={}
    for path in (Path("/etc/empire_os.env"),Path("/etc/empiredb.env")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing or untrusted service environment")
        for raw in path.read_text(encoding="utf-8").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name,value=line.split("=",1)
            name=name.strip()
            if name not in _BSC_NAMES or name in config:
                continue
            val=value.strip()
            if len(val)>1 and val[0]==val[-1] and val[0] in {"'","\""}:
                val=val[1:-1]
            config[name]=val
    if not config.get("BSC_RPC_URL") or not config.get("BSC_TREASURY_ADDRESS"):
        raise ValueError("checkout service BSC configuration unavailable")
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
