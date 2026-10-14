"""Live direct-BSC checkout smoke, strictly no customer/order or money writes.

Network: GET catalog and buy page; POST one reserved NON-issued token solely
to the status route. No POST /v1/checkout/orders, no DB or SMTP connection.
Safe to run repeatedly. Does NOT prove any genuine buyer paid.
"""
from __future__ import annotations

import json
from typing import Any
import urllib.request
import urllib.error

CATALOG="http://127.0.0.1/v1/checkout/catalog"
BUY="http://127.0.0.1/buy"
PRIVATE="http://127.0.0.1:8098/v1/checkout/payment-status"
PUBLIC="http://127.0.0.1/v1/checkout/payment-status"
HEALTH="http://127.0.0.1:8098/health"
ORIGIN="https://empire-ai.co.uk"
UNKNOWN="ecs1_"+"A"*43


def _get(url: str, *, page: bool=False):
    request=urllib.request.Request(
        url, method="GET", headers={"Host":"empire-ai.co.uk"},
    )
    with urllib.request.urlopen(request,timeout=8) as response:
        if response.status!=200:
            raise ValueError("HTTP health failure")
        if page:
            return response.read(800_000)
        return json.load(response)


def _unknown_denied(url: str)->bool:
    request=urllib.request.Request(
        url,
        method="POST",
        data=json.dumps({"token":UNKNOWN}).encode(),
        headers={"Content-Type":"application/json","Origin":ORIGIN,
                 "Sec-Fetch-Site":"same-origin"},
    )
    try:
        with urllib.request.urlopen(request,timeout=12) as response:
            code=response.status
            raw=response.read(300)
    except urllib.error.HTTPError as error:
        code=error.code
        raw=error.read(300)
    try:
        data=json.loads(raw)
    except (TypeError,ValueError):
        return False
    return code==404 and data=={"error":"payment_status_unavailable"}


def inspect(*, fetch=None, unknown_denied=None,
            chain=None)->dict[str,Any]:
    fetch=fetch or _get
    unknown_denied=unknown_denied or _unknown_denied
    from empire_os.self_serve_payment_readiness import (
        verify_checkout_bsc_chain,
    )
    from empire_os.bsc_usdt_verifier import BscUsdtConfig,BSC_USDT_CONTRACT
    from scripts.deploy_direct_bsc_buyer_status_release import (
        _published_checkout_verified,
    )
    evidence={
        "mode":"READ_ONLY",
        "real_orders_submitted":0,
        "status_tokens_issued":0,
        "buyer_data_disclosed":False,
        "payment_execution":False,
        "revenue_recognition":False,
        "email_sent":False,
    }
    stage="buy_page"
    try:
        html=fetch(BUY,page=True)
        if not isinstance(html,bytes) or b"<html" not in html.lower():
            raise ValueError("buy page not ready")
        stage="published_asset_integrity"
        # Verifies SHA256 against the checked-in manifest; no file changes.
        _published_checkout_verified()
        stage="catalog"
        catalog=fetch(CATALOG)
        if (type(catalog) is not dict
            or catalog.get("binding_order_creation_authorized") is not True
            or catalog.get("payment_proposal_authorized") is not True
            or catalog.get("checkout_settlement_mode")!="direct"
            or catalog.get("actual_revenue") is not False
            or type(catalog.get("products")) is not list
            or len(catalog["products"])!=4):
            raise ValueError("four-product catalog drift")
        stage="checkout_health"
        health=fetch(HEALTH)
        if (type(health) is not dict
            or health.get("status")!="online"
            or health.get("payment_execution") is not False
            or health.get("revenue_recognition") is not False
            or health.get("binding_order_creation_authorized") is not True
            or health.get("payment_proposal_authorized") is not True):
            raise ValueError("checkout financial hold drift")
        stage="private_nonissued_bearer"
        if unknown_denied(PRIVATE) is not True:
            raise ValueError("private unknown bearer not denied")
        stage="public_nonissued_bearer"
        if unknown_denied(PUBLIC) is not True:
            raise ValueError("public unknown bearer not denied")
        stage="fresh_bsc_chain"
        cfg=BscUsdtConfig(
            rpc_url="https://bsc-dataseed.bnbchain.org",
            treasury_address="0x1339b487046B0ad924a10c20b1791608EA8595a8",
            token_contract=BSC_USDT_CONTRACT,
            min_confirmations=12,
        )
        proof=(chain or verify_checkout_bsc_chain)(config=cfg)
        age=proof.get("block_age_seconds") if type(proof) is dict else None
        if (type(proof) is not dict or proof.get("chain_verified") is not True
            or proof.get("status")!="FRESH_BSC_MAINNET_USDT_ANCHOR"
            or proof.get("chain_id")!=56
            or proof.get("token_decimals")!=18
            or type(age) not in (int,float)
            or not -30 <= age <= 300):
            raise ValueError("chain proof incomplete")
    except Exception:
        evidence.update(
            status="CHECKOUT_BUYER_READONLY_CANARY_HELD",
            held_stage=stage,
        )
        return evidence
    evidence.update(
        status="CHECKOUT_BUYER_READONLY_CANARY_VERIFIED",
        catalog_products=4,
        pending_order_admission=True,
        private_unknown_token_denied=True,
        public_unknown_token_denied=True,
        chain_id=56,
        token_decimals=18,
        fresh_chain_anchor=True,
        next_proof="GENUINE_NEW_BUYER_ORDER_AND_SETTLEMENT",
    )
    return evidence


def main()->int:
    result=inspect()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="CHECKOUT_BUYER_READONLY_CANARY_VERIFIED" else 2


if __name__=="__main__":
    raise SystemExit(main())
