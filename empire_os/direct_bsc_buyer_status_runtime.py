"""Prepared direct-BSC buyer status ASGI application; never auto-deployed.

This is an assembly layer for the installed restricted EmpireDB reader and
the previously-tested HTTP route. No imports or side effects in the live
gateway/checkout, no production env, key generation, port listener or send.
A public release must independently supply chain verification and explicit
founder status-route approval, both fail closed by default.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fastapi import FastAPI
from psycopg.conninfo import conninfo_to_dict

from empire_os.direct_bsc_buyer_status import ADDRESS_RE, deny
from empire_os.direct_bsc_buyer_status_http import create_private_buyer_status_router
from empire_os.direct_bsc_buyer_status_private_reader import (
    PrivateBuyerStatusPostgresReader,
)
from scripts.provision_direct_bsc_buyer_status_logins import READ_LOGIN

PUBLIC_ORIGIN="https://empire-ai.co.uk"


def _bound_reader_identity(dsn: str) -> None:
    if not isinstance(dsn,str) or not dsn.strip():
        deny()
    try:
        value=conninfo_to_dict(dsn)
        if (value.get("dbname")!="empiredb"
            or value.get("user")!=READ_LOGIN
            or value.get("host") not in (
                "127.0.0.1","localhost","::1","/var/run/postgresql")
            or value.get("hostaddr") not in (None,"","127.0.0.1","::1")
            or str(value.get("port") or "5432")!="5432"
            or not value.get("password")
            or value.get("service") or value.get("options")):
            deny()
    except Exception:
        deny()


def create_staged_private_status_app(
    *,
    reader_dsn: str,
    hmac_key: bytes,
    treasury_address: str,
    allow_request: Callable[[str],bool],
    founder_release: Callable[[],bool]|None=None,
    verified_chain: Callable[[],bool]|None=None,
    read_by_fingerprint: Callable[[str],Mapping[str,Any]|None]|None=None,
) -> FastAPI:
    """Assemble dependency-injected status app; no URL or process is started.

    verified_chain MUST be a fresh, independent BSC chain+USDT verification,
    not merely the checkout health's CONFIGURED_CHAIN_UNVERIFIED flag.
    Defaults are always OFF.
    """
    _bound_reader_identity(reader_dsn)
    if (not isinstance(hmac_key,bytes) or len(hmac_key)<32
        or not isinstance(treasury_address,str)
        or not ADDRESS_RE.fullmatch(treasury_address.lower())
        or treasury_address.lower()=="0x"+"0"*40
        or not callable(allow_request)):
        deny()
    if read_by_fingerprint is None:
        read_by_fingerprint=PrivateBuyerStatusPostgresReader(reader_dsn)
    if not callable(read_by_fingerprint):
        deny()
    app=FastAPI(
        title="Empire Direct BSC Private Buyer Status (STAGED)",
        docs_url=None,redoc_url=None,openapi_url=None,
    )
    def authorized()->bool:
        if not callable(founder_release) or not callable(verified_chain):
            return False
        # Order matters: cannot run public route checks or reader unless the
        # feature was explicitly released. HTTP router catches errors.
        return founder_release() is True and verified_chain() is True
    app.include_router(create_private_buyer_status_router(
        origin=PUBLIC_ORIGIN,
        authorized=authorized,
        allow_request=allow_request,
        hmac_key=hmac_key,
        read_by_fingerprint=read_by_fingerprint,
        approved_treasury=treasury_address,
    ))
    return app
