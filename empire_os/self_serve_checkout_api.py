"""Narrow internal API for Empire self-serve checkout."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from empire_os.exchange_self_serve import (
    ExchangeInterestError,
    exchange_tier_catalog,
    record_exchange_interest,
)
from empire_os.predictive_revenue_products import (
    predictive_revenue_product_catalog,
)
from empire_os.predictive_revenue_self_serve import (
    PredictiveRevenueInterestError,
    record_predictive_revenue_interest,
)
from empire_os.first_party_sales_interest import (
    CommercialInterestError,
    founder_led_commercial_offers,
    record_founder_led_interest,
)
from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.escrow_mainnet_role_readiness import (
    EscrowRoleConfig,
    role_config_snapshot,
    verify_escrow_runtime_roles_and_backing,
)
from empire_os.self_serve_escrow_bridge import (
    escrow_config_snapshot,
    escrow_mainnet_activation_flag,
    settlement_mode,
    verify_escrow_checkout_contract,
    verify_escrow_operator_memberships,
)
from empire_os.self_serve_payment_readiness import (
    CheckoutPaymentPreflightHold,
    checkout_bsc_config_snapshot,
    verify_checkout_bsc_chain,
)
from empire_os.self_serve_checkout import (
    CheckoutError,
    create_payment_request_for_order,
    prepare_checkout_order,
    self_serve_catalog,
)


app = FastAPI(
    title="Empire Self-Serve Checkout",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _proposal_authorized() -> bool:
    return os.getenv(
        "EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED",
        "OFF",
    ).strip().upper() in {"1", "ON", "TRUE", "YES"}


def _settlement_snapshot() -> dict[str, Any]:
    try:
        mode = settlement_mode()
    except CheckoutPaymentPreflightHold:
        return {
            "mode": "unsupported",
            "configured": False,
            "status": "UNSUPPORTED_CHECKOUT_SETTLEMENT_MODE",
        }
    if mode == "escrow":
        result = escrow_config_snapshot()
        if not result["configured"]:
            return {"mode": mode, **result}
        if not escrow_mainnet_activation_flag():
            return {
                "mode": "escrow", "configured": False,
                "status": "ESCROW_MAINNET_ACTIVATION_HELD",
            }
        roles = role_config_snapshot()
        if not roles["configured"]:
            return {"mode": mode, **roles}
        return {"mode": mode, **result}
    return {"mode": mode, **checkout_bsc_config_snapshot()}


def _orders_authorized() -> bool:
    # Both founder flags AND the selected mode's deployment admission are
    # needed. A configured RPC or a historic escrow build is never enough.
    return (
        os.getenv(
            "EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED", "OFF"
        ).strip().upper() in {"1", "ON", "TRUE", "YES"}
        and _proposal_authorized()
        and _settlement_snapshot()["configured"] is True
    )


class PredictiveRevenueInterestRequest(BaseModel):
    product_code: str = Field(min_length=1, max_length=120)
    business_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    domain: str = Field(min_length=3, max_length=253)
    industry: str = Field(min_length=1, max_length=120)
    geography: str = Field(min_length=1, max_length=160)
    annual_revenue_band: str = Field(default="unknown", max_length=40)
    desired_outcome: str = Field(min_length=1, max_length=1200)
    systems: list[str] = Field(default_factory=list, max_length=20)
    contact_consent: bool
    website: str = Field(default="", max_length=300)
    idempotency_key: str = Field(min_length=8, max_length=128)


class FounderLedCommercialInterestRequest(BaseModel):
    product_code: str = Field(min_length=1, max_length=120)
    business_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    domain: str = Field(min_length=3, max_length=253)
    industry: str = Field(min_length=1, max_length=120)
    geography: str = Field(min_length=1, max_length=160)
    desired_outcome: str = Field(min_length=12, max_length=1200)
    contact_consent: bool
    idempotency_key: str = Field(min_length=8, max_length=128)
    website: str = Field(default="", max_length=300)
    organic_touch: dict[str, str] | None = None
    claimed_entry_page: str | None = Field(default=None, max_length=80)
    source_campaign_key: str | None = Field(default=None, max_length=32)
    source_landing_url: str | None = Field(default=None, max_length=2048)


class ExchangeInterestRequest(BaseModel):
    tier_code: str = Field(min_length=1, max_length=100)
    business_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    domain: str = Field(min_length=3, max_length=253)
    niche: str = Field(min_length=1, max_length=120)
    territory: str = Field(min_length=1, max_length=160)
    daily_capacity: int = Field(ge=1, le=10000)
    delivery_preference: str = Field(min_length=3, max_length=40)
    exclusivity_interest: bool = False


class CheckoutRequest(BaseModel):
    product_code: str = Field(min_length=1, max_length=100)
    business_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    target_domain: str = Field(min_length=3, max_length=253)
    payer_wallet: str = Field(min_length=42, max_length=42)
    terms_accepted: bool
    idempotency_key: str = Field(min_length=8, max_length=128)


@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "empire-self-serve-checkout",
        "payment_proposal_authorized": _proposal_authorized(),
        "binding_order_creation_authorized": _orders_authorized(),
        "bsc_payment_configuration_status": _settlement_snapshot()["status"],
        "checkout_settlement_mode": _settlement_snapshot()["mode"],
        "escrow_creation_automated": False,
        "founder_led_commercial_interest_enabled": True,
        "payment_execution": False,
        "revenue_recognition": False,
    }


@app.get("/v1/catalog")
def catalog():
    return {
        **self_serve_catalog(),
        "binding_order_creation_authorized": _orders_authorized(),
        "payment_proposal_authorized": _proposal_authorized(),
        "bsc_payment_configuration_status": _settlement_snapshot()["status"],
        "checkout_settlement_mode": _settlement_snapshot()["mode"],
    }


@app.post("/v1/orders")
def create_order(req: CheckoutRequest):
    if not _orders_authorized():
        raise HTTPException(status_code=503, detail="binding_orders_not_authorized")
    try:
        # Read BSC mainnet chain, canonical USDT precision and a fresh anchor
        # BEFORE buyer or accepted fulfilment order is written to EmpireDB.
        mode = settlement_mode()
        if mode == "escrow":
            verify_escrow_checkout_contract()
            # Verify distinct administrator / requester / arbiter / pauser
            # holders, approved decision delay and contract backing before
            # any buyer or accepted-order row can be written.
            verify_escrow_runtime_roles_and_backing(
                deployment=BscEscrowConfig.from_env(),
                roles=EscrowRoleConfig.from_env(),
            )
            # No money or accepted-order write until independent approval
            # and escrow verifier roles have operative DB login memberships.
            verify_escrow_operator_memberships()
        else:
            verify_checkout_bsc_chain()
        order = prepare_checkout_order(
            product_code=req.product_code,
            business_name=req.business_name,
            email=req.email,
            target_domain=req.target_domain,
            payer_wallet=req.payer_wallet,
            terms_accepted=req.terms_accepted,
            idempotency_key=req.idempotency_key,
            settlement_mode=mode,
        )
        result = create_payment_request_for_order(
            order,
            standing_authority=_proposal_authorized(),
            settlement_mode=mode,
        )
        # First-party status receipt is optional and DEFAULT OFF.
        # A failure never repeats an already-committed payment request.
        from empire_os.direct_bsc_buyer_checkout_release import (
            add_status_receipt_if_released,
        )
        return add_status_receipt_if_released(result)
    except CheckoutPaymentPreflightHold as exc:
        # No RPC URL, treasury, or chain internals leak into public replies.
        raise HTTPException(
            status_code=503, detail="bsc_payment_preflight_unavailable"
        ) from exc
    except CheckoutError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"checkout_unavailable:{type(exc).__name__}",
        ) from exc



@app.get("/v1/exchange/tiers")
def exchange_tiers():
    return exchange_tier_catalog()


@app.post("/v1/exchange/interests")
def exchange_interest(req: ExchangeInterestRequest):
    try:
        return record_exchange_interest(
            tier_code=req.tier_code,
            business_name=req.business_name,
            email=req.email,
            domain=req.domain,
            niche=req.niche,
            territory=req.territory,
            daily_capacity=req.daily_capacity,
            delivery_preference=req.delivery_preference,
            exclusivity_interest=req.exclusivity_interest,
        )
    except ExchangeInterestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"exchange_intake_unavailable:{type(exc).__name__}",
        ) from exc



@app.get("/v1/predictive-revenue/products")
def predictive_revenue_products():
    return predictive_revenue_product_catalog()


@app.post("/v1/predictive-revenue/interests")
def predictive_revenue_interest(req: PredictiveRevenueInterestRequest):
    if req.contact_consent is not True or req.website:
        raise HTTPException(status_code=422, detail="specific_contact_consent_required")
    try:
        return record_predictive_revenue_interest(
            product_code=req.product_code,
            business_name=req.business_name,
            email=req.email,
            domain=req.domain,
            industry=req.industry,
            geography=req.geography,
            annual_revenue_band=req.annual_revenue_band,
            desired_outcome=req.desired_outcome,
            systems=req.systems,
            contact_consent=req.contact_consent,
            website=req.website,
            idempotency_key=req.idempotency_key,
        )
    except (PredictiveRevenueInterestError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"predictive_revenue_intake_unavailable:{type(exc).__name__}",
        ) from exc


@app.get("/v1/commercial/offers")
def commercial_offers():
    return founder_led_commercial_offers()


@app.post("/v1/commercial/interests")
def commercial_interest(req: FounderLedCommercialInterestRequest):
    if req.contact_consent is not True or req.website:
        raise HTTPException(status_code=422, detail="specific_contact_consent_required")
    try:
        return record_founder_led_interest(
            product_code=req.product_code,
            business_name=req.business_name,
            email=req.email,
            domain=req.domain,
            industry=req.industry,
            geography=req.geography,
            desired_outcome=req.desired_outcome,
            contact_consent=req.contact_consent,
            idempotency_key=req.idempotency_key,
            website=req.website,
            organic_touch=req.organic_touch,
            claimed_entry_page=req.claimed_entry_page,
            source_campaign_key=req.source_campaign_key,
            source_landing_url=req.source_landing_url,
        )
    except CommercialInterestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Database/connector internals are not customer-facing information.
        raise HTTPException(
            status_code=503, detail="commercial_enquiry_temporarily_unavailable"
        ) from exc

# Mount the buyer-held status endpoint ONLY when the separately authorised
# first-party release is supplied with verified systemd credentials.
# Normal production imports remain unchanged, with no status route.
from empire_os.direct_bsc_buyer_checkout_release import mount_status_if_released
mount_status_if_released(app)
