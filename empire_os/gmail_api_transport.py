"""Governed Gmail API transport for Empire outbound.

Transport only. It grants no approval or send authority.
A canonical database-authorized outbound claim is required.
"""
from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from empire_os.outbound_provider import (
    OutboundProviderError,
    build_resend_send,
)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SCOPES = [GMAIL_SEND_SCOPE]


def build_gmail_message(
    claim: dict[str, Any],
    *,
    sender: str,
    reply_to: str,
) -> EmailMessage:
    # Reuse the existing production outbound safety contract:
    # authorised claim, one recipient, sender domain, governed reply alias,
    # visible opt-out and approved postal footer.
    safe = build_resend_send(
        claim,
        sender=sender,
        reply_to=reply_to,
    )

    intent_id = str(claim.get("intent_id") or "").strip()

    message = EmailMessage()
    message["From"] = safe["from"]
    message["To"] = safe["to"][0]
    message["Reply-To"] = safe["reply_to"][0]
    message["Subject"] = safe["subject"]
    message["List-Unsubscribe"] = safe["headers"]["List-Unsubscribe"]
    message["X-Empire-Intent-ID"] = intent_id
    message["Message-ID"] = (
        f"<empire-{intent_id}@mail.empire-ai.co.uk>"
    )

    message.set_content(safe["text"])

    if safe.get("html"):
        message.add_alternative(
            str(safe["html"]),
            subtype="html",
        )

    return message


def _write_token(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value, encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def load_gmail_credentials(
    token_file: str | Path,
):
    path = Path(token_file)

    if not path.is_file():
        raise OutboundProviderError(
            "Gmail OAuth token file required"
        )

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise OutboundProviderError(
            "Google Gmail API libraries are required"
        ) from exc

    try:
        # Preserve the authorised token's actual scope set on refresh. Forcing
        # gmail.send here would silently strip a separately consented
        # gmail.readonly scope and break the founder's Workspace inbox.
        credentials = Credentials.from_authorized_user_file(str(path))

        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            _write_token(path, credentials.to_json())

    except Exception as exc:
        raise OutboundProviderError(
            "Gmail OAuth credentials could not be loaded"
        ) from exc

    if not credentials.valid:
        raise OutboundProviderError(
            "Gmail OAuth credentials are not valid"
        )

    granted = set(credentials.scopes or [])
    if GMAIL_SEND_SCOPE not in granted:
        raise OutboundProviderError(
            "gmail.send scope required"
        )

    return credentials


def build_gmail_service(credentials):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundProviderError(
            "Google Gmail API client is required"
        ) from exc

    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def send_with_gmail_api(
    claim: dict[str, Any],
    *,
    sender: str,
    reply_to: str,
    token_file: str | Path | None = None,
    service: Any | None = None,
) -> dict[str, str]:
    message = build_gmail_message(
        claim,
        sender=sender,
        reply_to=reply_to,
    )

    if service is None:
        if token_file is None:
            raise OutboundProviderError(
                "Gmail OAuth token file required"
            )

        credentials = load_gmail_credentials(token_file)
        service = build_gmail_service(credentials)

    # Re-read the commercial reply state at the physical send boundary.
    from empire_os.commercial_outbound_holds import (
        require_no_commercial_hold, CommercialOutboundHoldError,
    )
    try:
        require_no_commercial_hold(message["To"])
    except CommercialOutboundHoldError as exc:
        raise OutboundProviderError("commercial_fit_outbound_held") from exc

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("ascii")

    try:
        result = (
            service.users()
            .messages()
            .send(
                userId="me",
                body={"raw": raw},
            )
            .execute()
        )
    except Exception as exc:
        raise OutboundProviderError(
            "Gmail API send failed"
        ) from exc

    message_id = str(
        (result or {}).get("id") or ""
    ).strip()

    if not message_id:
        raise OutboundProviderError(
            "Gmail API returned no message id"
        )

    return {
        "provider": "gmail",
        "provider_message_id": message_id,
        "provider_thread_id": str(
            (result or {}).get("threadId") or ""
        ),
    }
