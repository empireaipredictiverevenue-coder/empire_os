"""Optional first-party status release wiring for existing checkout API.

DEFAULT OFF. No new gateway, database permissions, secret generation or
payment execution. Requires independent systemd-loaded credentials, explicit
feature flag and fresh independent BSC verification. A failed optional status
receipt MUST NOT convert a committed pending checkout order into a retry.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from psycopg.conninfo import conninfo_to_dict

from empire_os.direct_bsc_buyer_receipt_bridge import with_new_buyer_status_receipt
from empire_os.direct_bsc_buyer_status_private_issuer import PrivateBuyerIssuerPostgresWriter
from empire_os.direct_bsc_buyer_status_runtime import (
    create_staged_private_status_app,_bound_reader_identity,
)
from empire_os.owned_campaign_http import LIMITER
from empire_os.self_serve_payment_readiness import verify_checkout_bsc_chain
from empire_os.bsc_usdt_verifier import BscUsdtConfig
from scripts.provision_direct_bsc_buyer_status_logins import (
    READ_KEY,ISSUE_KEY,READ_LOGIN,ISSUE_LOGIN
)

ACTIVATION="EMPIRE_DIRECT_BSC_BUYER_STATUS_RELEASE"
CREDENTIAL_KEY="empire_direct_bsc_buyer_status_hmac.key"
CREDENTIAL_DSN="empire_direct_bsc_buyer_status.env"
CHECKOUT_CREDENTIAL_DIR=Path(
    "/run/credentials/empire-self-serve-checkout.service"
)

_LOG=logging.getLogger("empire.checkout.buyer_status")

class PrivateStatusConfigurationHeld(ValueError):
    """Carries only a fixed pre-declared stage, never credential contents."""
    def __init__(self,stage: str):
        self.stage=stage
        super().__init__("private_status_configuration_unavailable")



def _enabled()->bool:
    return os.getenv(ACTIVATION,"OFF")=="ON"


def _credential_dir()->Path:
    """Only the real checkout unit's private systemd credential directory."""
    dirname=os.environ.get("CREDENTIALS_DIRECTORY","")
    if dirname!=str(CHECKOUT_CREDENTIAL_DIR):
        raise ValueError("exact checkout systemd credential context required")
    path=CHECKOUT_CREDENTIAL_DIR
    if path.is_symlink() or not path.is_dir():
        raise ValueError("untrusted credential directory")
    # systemd protects 0444 credential copies through the private per-unit
    # directory, which must not be traversable by unrelated users.
    if path.stat().st_mode & 0o007:
        raise ValueError("untrusted credential directory traversal rights")
    return path


def _config()->tuple[str,str,bytes,str]:
    stage="credential_directory"
    try:
        folder=_credential_dir()
        stage="credential_files"
        key_path=folder/CREDENTIAL_KEY
        dsn_path=folder/CREDENTIAL_DSN
        for file in (key_path,dsn_path):
            if file.is_symlink() or not file.is_file():
                raise ValueError("systemd credential missing")
            # systemd's read-only copy is commonly 0444, unlike the
            # root-only 0600 source. The exact per-unit directory
            # above prevents unrelated users from traversing here.
            if file.stat().st_mode & 0o222:
                raise ValueError("systemd credential must be read-only")
        stage="signing_key"
        with key_path.open("rb") as file:
            key=file.read(33)
        if len(key)!=32:
            raise ValueError("bad HMAC key")
        stage="credential_format"
        lines=dsn_path.read_text(encoding="utf-8").splitlines()
        out={}
        for line in lines:
            k,sep,raw=line.partition("=")
            if not sep or k not in {READ_KEY,ISSUE_KEY} or k in out:
                raise ValueError("invalid credential entry")
            val=json.loads(raw)
            if type(val) is not str:
                raise ValueError("invalid DSN")
            out[k]=val
        if set(out)!={READ_KEY,ISSUE_KEY}:
            raise ValueError("missing DSN")
        stage="reader_identity"
        _bound_reader_identity(out[READ_KEY])
        stage="issuer_identity"
        issuer=conninfo_to_dict(out[ISSUE_KEY])
        if (issuer.get("user")!=ISSUE_LOGIN
            or issuer.get("dbname")!="empiredb"
            or issuer.get("host") not in (
                "127.0.0.1","localhost","::1","/var/run/postgresql")
            or issuer.get("hostaddr") not in (None,"","127.0.0.1","::1")
            or str(issuer.get("port") or "5432")!="5432"
            or not issuer.get("password")
            or issuer.get("options") or issuer.get("service")):
            raise ValueError("untrusted issuer")
        stage="independent_passwords"
        if conninfo_to_dict(out[READ_KEY])["password"] == issuer["password"]:
            raise ValueError("shared password denied")
        stage="bsc_configuration"
        cfg=BscUsdtConfig.from_env()
        if cfg.min_confirmations<12:
            raise ValueError("minimum chain confirmations below policy")
        return out[READ_KEY],out[ISSUE_KEY],key,cfg.treasury_address
    except Exception:
        # Exception cause and message may include private DSNs. Never print
        # them or attach an exception chain to service startup output.
        raise PrivateStatusConfigurationHeld(stage) from None


def _chain_verified()->bool:
    try:
        return verify_checkout_bsc_chain().get("chain_verified") is True
    except Exception:
        return False


def _pending_request(request_id: str)->Mapping[str,Any]|None:
    from empire_os.sb import request_json
    from empire_os.direct_bsc_buyer_status import uid
    rid=uid(request_id)
    rows=request_json(
        "GET",
        "/rest/v1/bsc_payment_requests"
        "?select=id,fulfilment_order_id,settlement_mode,status,created_at,expires_at"
        "&id=eq."+rid+"&limit=1",
    )
    if type(rows) is not list or len(rows)!=1 or type(rows[0]) is not dict:
        return None
    raw=rows[0]
    from datetime import datetime
    return {
        "id":raw.get("id"),
        "fulfilment_order_id":raw.get("fulfilment_order_id"),
        "settlement_mode":raw.get("settlement_mode"),
        "status":raw.get("status"),
        "created_at":datetime.fromisoformat(raw["created_at"].replace("Z","+00:00")),
        "expires_at":datetime.fromisoformat(raw["expires_at"].replace("Z","+00:00")),
    }


def add_status_receipt_if_released(response: Mapping[str,Any])->dict[str,Any]:
    # The existing payment-request transaction already completed; no retries.
    if not _enabled():
        return dict(response)
    try:
        reader_dsn,issuer_dsn,key,treasury=_config()
        if _chain_verified() is not True:
            raise ValueError("fresh BSC verification required")
        return with_new_buyer_status_receipt(
            response,
            enabled=True,
            hmac_key=key,
            request_lookup=_pending_request,
            persist_fingerprint=PrivateBuyerIssuerPostgresWriter(issuer_dsn),
        )
    except Exception:
        output=dict(response)
        output["buyer_status_unavailable"]=True
        output["buyer_status_token_delivered"]=False
        return output


def mount_status_if_released(app: FastAPI)->bool:
    if not _enabled():
        return False
    # If credentials unavailable, do NOT mount public HTTP endpoint.
    phase="credentials"
    try:
        reader_dsn,issuer_dsn,key,treasury=_config()
        assert issuer_dsn
        phase="status_assembly"
        status=create_staged_private_status_app(
            reader_dsn=reader_dsn,
            hmac_key=key,
            treasury_address=treasury,
            allow_request=lambda peer: LIMITER.allow(peer,"buyer_status"),
            founder_release=_enabled,
            verified_chain=_chain_verified,
        )
        phase="status_mount"
        app.include_router(status.router)
        _LOG.info("DIRECT_BSC_STATUS_MOUNT=READY")
        return True
    except PrivateStatusConfigurationHeld as held:
        _LOG.warning("DIRECT_BSC_STATUS_MOUNT=HELD stage=%s", held.stage)
        return False
    except Exception:
        _LOG.warning("DIRECT_BSC_STATUS_MOUNT=HELD stage=%s", phase)
        return False
