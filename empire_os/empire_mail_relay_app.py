"""Loopback-only Empire Gmail relay.

Default state is OBSERVE and send-authority false.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from empire_os.gmail_api_transport import (
    build_gmail_message,
    send_with_gmail_api,
)
from empire_os.outbound_provider import OutboundProviderError


app = FastAPI(
    title="Empire Mail Relay",
    version="1.0",
)


def _mode() -> str:
    return str(
        os.getenv(
            "EMPIRE_MAIL_RELAY_MODE",
            "OBSERVE",
        )
    ).strip().upper()


def _send_authorized() -> bool:
    return (
        str(
            os.getenv(
                "EMPIRE_MAIL_RELAY_SEND_AUTHORIZED",
                "false",
            )
        ).strip().lower()
        == "true"
    )


def _sender() -> str:
    return str(
        os.getenv(
            "EMPIRE_GMAIL_SENDER",
            "",
        )
    ).strip()


def _reply_to() -> str:
    return str(
        os.getenv(
            "EMPIRE_MAIL_RELAY_REPLY_TO",
            "reply@mail.empire-ai.co.uk",
        )
    ).strip()


def _token_file() -> str:
    return str(
        os.getenv(
            "EMPIRE_GMAIL_TOKEN_FILE",
            "/srv/empire_os/runtime/secrets/"
            "google-workspace-token.json",
        )
    ).strip()


@app.get("/health")
def health() -> dict[str, Any]:
    token_path = Path(_token_file())
    sender_present = bool(_sender())
    token_present = token_path.is_file()
    config_present = sender_present and token_present
    # This is a local liveness probe, not an OAuth validation or a live
    # Gmail round trip. Never confuse available files with usable delivery.
    blockers = []
    if not sender_present:
        blockers.append("sender_not_configured")
    if not token_present:
        blockers.append("oauth_token_missing")
    if config_present:
        blockers.append("oauth_validation_not_performed")

    return {
        "ok": True,
        "mailbox_configuration_present": config_present,
        "oauth_verified": False,
        "mailbox_ready": False,
        "readiness_status": (
            "CONFIG_PRESENT_UNVERIFIED" if config_present
            else "BLOCKED_NOT_PROVISIONED"
        ),
        "readiness_blockers": blockers,
        "provider": "gmail_api",
        "transport": "https_443",
        "mode": _mode(),
        "send_authorized": _send_authorized(),
        "sender_configured": sender_present,
        "oauth_token_present": token_present,
        "reply_transport": "empire_inbound",
        "reply_domain": "mail.empire-ai.co.uk",
        "mutation_authorized": (
            _mode() == "GUARDED_EXECUTE"
            and _send_authorized()
        ),
    }


@app.post("/v1/prepare")
def prepare(payload: dict[str, Any]) -> dict[str, Any]:
    claim = payload.get("claim")

    if not isinstance(claim, dict):
        raise HTTPException(
            status_code=400,
            detail="canonical outbound claim required",
        )

    try:
        message = build_gmail_message(
            claim,
            sender=_sender(),
            reply_to=_reply_to(),
        )
    except OutboundProviderError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "ok": True,
        "intent_id": claim.get("intent_id"),
        "recipient": message["To"],
        "provider": "gmail_api",
        "transport": "https_443",
        "would_send": False,
        "mutation_authorized": False,
    }


@app.post("/v1/send")
def send(payload: dict[str, Any]) -> dict[str, Any]:
    # Two independent gates are deliberately required.
    if _mode() != "GUARDED_EXECUTE":
        raise HTTPException(
            status_code=409,
            detail="relay is OBSERVE only",
        )

    if not _send_authorized():
        raise HTTPException(
            status_code=409,
            detail="relay send authority is disabled",
        )

    claim = payload.get("claim")

    if not isinstance(claim, dict):
        raise HTTPException(
            status_code=400,
            detail="canonical outbound claim required",
        )

    try:
        result = send_with_gmail_api(
            claim,
            sender=_sender(),
            reply_to=_reply_to(),
            token_file=_token_file(),
        )
    except OutboundProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "ok": True,
        **result,
        "intent_id": claim.get("intent_id"),
        "actual_revenue": False,
    }
