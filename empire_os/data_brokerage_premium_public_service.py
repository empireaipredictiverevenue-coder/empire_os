"""Public premium Data Brokerage enquiry as an additive uvicorn entrypoint.

Original public gateway routes, middleware, static assets and active sales
channels are unchanged. The root-owned release flags must all be present
before the two unpriced candidate routes are added.
"""
from __future__ import annotations
import os

from empire_os.public_gateway import app
from empire_os.owned_campaign_http import LIMITER
from empire_os.data_brokerage_premium_gateway_adapter import (
    make_reviewed_public_premium_gateway_router,
    forward_to_private_checkout,
)

if os.getenv("EMPIRE_BROKERAGE_PREMIUM_PUBLIC_RELEASE") == "ON":
    app.include_router(
        make_reviewed_public_premium_gateway_router(
            rate_limiter=lambda peer, kind: LIMITER.allow(peer, kind),
            forward=forward_to_private_checkout,
            founder_release_approved=True,
            existing_private_checkout_route_verified=(
                os.getenv("EMPIRE_BROKERAGE_PREMIUM_PRIVATE_VERIFIED") == "ON"
            ),
            astra_frontend_review_complete=(
                os.getenv("EMPIRE_BROKERAGE_PREMIUM_ASTRA_QA") == "ON"
            ),
        )
    )
