"""Resend transactional confirmation transport for consented subscribers.

No default network send. Requires an explicitly provisioned scoped API key,
a currently verified domain, a dedicated consumer-send approval, and a fresh
purpose-specific suppression read before a provider request. This does NOT
provide list marketing, bulk send, customer promotion, or referral authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Any
from urllib import request, error

from empire_os.consumer_optin_confirmation_email import (
    render_first_party_confirmation,
)
from empire_os.consumer_optin_token_security import canonical_email


SenderRequest = Callable[..., dict[str, Any]]
SuppressionReader = Callable[[str], bool]


def _send_resend_https(*, key: str, payload: dict, dedupe_key: str) -> dict[str, Any]:
    """Default provider adapter, called only when all other gates pass."""
    wire = request.Request(
        url="https://api.resend.com/emails",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Idempotency-Key": dedupe_key,
        },
        method="POST",
    )
    try:
        with request.urlopen(wire, timeout=12) as response:
            if response.status not in (200, 201):
                raise RuntimeError("VERIFICATION_PROVIDER_REJECTED")
            raw = response.read(8193)
            if len(raw) > 8192:
                raise RuntimeError("VERIFICATION_PROVIDER_INVALID_RESPONSE")
            result = json.loads(raw)
    except (error.URLError, ValueError, TypeError) as ex:
        raise RuntimeError("VERIFICATION_PROVIDER_UNAVAILABLE") from ex
    if not isinstance(result, dict):
        raise RuntimeError("VERIFICATION_PROVIDER_BAD_JSON")
    return result


@dataclass
class ResendConsumerConfirmationSender:
    api_key: str = field(repr=False)
    verified_sender_domain: bool = False
    owner_approved_consumer_confirmation: bool = False
    sender_address: str = "updates@mail.empire-ai.co.uk"
    reply_to: str = "reply@mail.empire-ai.co.uk"
    current_suppression_clear: SuppressionReader | None = field(default=None,repr=False)
    provider: SenderRequest = field(default=_send_resend_https,repr=False)

    def provider_ready(self) -> bool:
        # Account domain verification is an independent original provider
        # readback, not a claim inferred from an env variable.
        return (
            self.verified_sender_domain is True
            and self.owner_approved_consumer_confirmation is True
            and isinstance(self.api_key, str) and self.api_key.startswith("re_")
            and len(self.api_key) >= 15
            and self.sender_address == "updates@mail.empire-ai.co.uk"
            and self.reply_to == "reply@mail.empire-ai.co.uk"
            and callable(self.current_suppression_clear)
            and callable(self.provider)
        )

    def send_verification(
        self, *, recipient: str, confirm_link: str, unsubscribe_link: str
    ) -> str | None:
        if not self.provider_ready():
            return None
        email = canonical_email(recipient)
        rendered = render_first_party_confirmation(
            recipient=email,
            confirm_link=confirm_link,
            unsubscribe_link=unsubscribe_link,
        )
        # Recheck the independently authorized suppression store at actual
        # provider dispatch. Fail closed on exceptions/unknown.
        try:
            if self.current_suppression_clear(email) is not True:
                return None
        except Exception:
            return None
        # Random opaque confirmation secret gives idempotency with no email.
        dedupe_key = "roofing-confirm/" + hashlib.sha256(
            confirm_link.encode("utf-8")
        ).hexdigest()
        payload={
            "from": "Empire AI <" + self.sender_address + ">",
            "to": [email],
            "reply_to": self.reply_to,
            "subject": rendered.subject,
            "text": rendered.text_body,
            "html": rendered.html_body,
            "tags": [{"name":"empire_purpose","value":"consumer_roofing_confirmation"}],
        }
        try:
            result=self.provider(
                key=self.api_key, payload=payload, dedupe_key=dedupe_key
            )
        except Exception:
            return None
        if not isinstance(result, dict):
            return None
        receipt = result.get("id")
        from uuid import UUID
        try:
            if not isinstance(receipt, str):
                return None
            parsed = UUID(receipt)
            if str(parsed) != receipt.lower():
                return None
        except (ValueError, AttributeError):
            return None
        return receipt
