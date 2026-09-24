"""Narrow internal API for Empire self-serve checkout."""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
        "payment_execution": False,
        "revenue_recognition": False,
    }


@app.get("/v1/catalog")
def catalog():
    return self_serve_catalog()


@app.post("/v1/orders")
def create_order(req: CheckoutRequest):
    try:
        order = prepare_checkout_order(
            product_code=req.product_code,
            business_name=req.business_name,
            email=req.email,
            target_domain=req.target_domain,
            payer_wallet=req.payer_wallet,
            terms_accepted=req.terms_accepted,
            idempotency_key=req.idempotency_key,
        )
        return create_payment_request_for_order(
            order,
            standing_authority=_proposal_authorized(),
        )
    except CheckoutError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"checkout_unavailable:{type(exc).__name__}",
        ) from exc
