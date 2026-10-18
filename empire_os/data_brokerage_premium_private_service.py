"""Private premium Data Brokerage route as an additive uvicorn app entrypoint.

This module preserves the entire existing self-serve checkout application.
Only the explicit root-owned systemd release flag adds a new first-party
premium *enquiry* route; checkout/payments configuration is not modified.
"""
from __future__ import annotations
import os

from empire_os.self_serve_checkout_api import app
from empire_os.owned_campaign_http import LIMITER
from empire_os.data_brokerage_premium_enquiry import make_private_discovery_router

if os.getenv("EMPIRE_BROKERAGE_PREMIUM_PRIVATE_RELEASE") == "ON":
    app.include_router(
        make_private_discovery_router(
            rate_limiter=lambda peer, kind: LIMITER.allow(peer, kind)
        )
    )
