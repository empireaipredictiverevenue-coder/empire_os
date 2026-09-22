"""Vonage Voice transport for governed outbound calls.

Live execution is fail-closed. Building/previewing a provider request is always
safe; actually creating a call requires BOTH explicit code-level authorization
and EMPIRE_PHONE_LIVE_AUTHORITY=true plus complete provider configuration.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import jwt

from empire_os.buyer_deferred_enrichment import canonical_phone
from empire_os.phone_quality import phone_digits

VONAGE_CALLS_URL = "https://api.nexmo.com/v1/calls/"


class VonageCallTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class VonageCallConfig:
    application_id: str
    private_key: str
    virtual_number: str
    answer_url: str
    event_url: str
    live_authority: bool

    @classmethod
    def from_env(cls) -> "VonageCallConfig":
        private_key = str(
            os.getenv("VONAGE_APPLICATION_PRIVATE_KEY") or ""
        ).strip()
        key_path = str(
            os.getenv("VONAGE_APPLICATION_PRIVATE_KEY_PATH") or ""
        ).strip()
        if not private_key and key_path:
            try:
                private_key = Path(key_path).read_text(encoding="utf-8")
            except OSError:
                private_key = ""
        return cls(
            application_id=str(
                os.getenv("VONAGE_APPLICATION_ID") or ""
            ).strip(),
            private_key=private_key,
            virtual_number=str(
                os.getenv("VONAGE_VIRTUAL_NUMBER") or ""
            ).strip(),
            answer_url=str(
                os.getenv("EMPIRE_VONAGE_ANSWER_URL") or ""
            ).strip(),
            event_url=str(
                os.getenv("EMPIRE_VONAGE_EVENT_URL") or ""
            ).strip(),
            live_authority=str(
                os.getenv("EMPIRE_PHONE_LIVE_AUTHORITY") or ""
            ).strip().lower() in {"1", "true", "yes", "on"},
        )

    def readiness(self) -> dict[str, Any]:
        missing = []
        if not self.application_id:
            missing.append("VONAGE_APPLICATION_ID")
        if not self.private_key:
            missing.append("VONAGE_APPLICATION_PRIVATE_KEY")
        if not self.virtual_number:
            missing.append("VONAGE_VIRTUAL_NUMBER")
        if not self.answer_url:
            missing.append("EMPIRE_VONAGE_ANSWER_URL")
        if not self.event_url:
            missing.append("EMPIRE_VONAGE_EVENT_URL")
        if not str(os.getenv("EMPIRE_VONAGE_WEBHOOK_TOKEN") or "").strip():
            missing.append("EMPIRE_VONAGE_WEBHOOK_TOKEN")
        if not str(os.getenv("EMPIRE_VOICE_WS_TOKEN") or "").strip():
            missing.append("EMPIRE_VOICE_WS_TOKEN")
        return {
            "provider": "vonage",
            "configured": not missing,
            "missing": missing,
            "live_authority": self.live_authority,
            "execution_allowed": bool(
                not missing and self.live_authority
            ),
        }


def _context_url(
    url: str,
    *,
    intent_id: str,
    prospect_id: str,
    token: str,
) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({
        "intent_id": intent_id,
        "prospect_id": prospect_id,
        "token": token,
    })
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(query),
        parsed.fragment,
    ))


def _provider_number(value: Any) -> str:
    phone = canonical_phone(value)
    if not phone:
        raise VonageCallTransportError("commercially usable E.164 phone required")
    return phone_digits(phone)


class VonageCallTransport:
    def __init__(
        self,
        config: VonageCallConfig | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or VonageCallConfig.from_env()
        self.client = client or httpx.Client(timeout=12.0)

    def build_request(
        self,
        plan: Mapping[str, Any],
    ) -> dict[str, Any]:
        to_number = _provider_number(plan.get("phone"))
        from_number = _provider_number(self.config.virtual_number)
        if not self.config.answer_url:
            raise VonageCallTransportError("Vonage answer URL required")
        intent_id = str(plan.get("intent_id") or "").strip()
        prospect_id = str(plan.get("prospect_id") or "").strip()
        webhook_token = str(
            os.getenv("EMPIRE_VONAGE_WEBHOOK_TOKEN") or ""
        ).strip()
        if not intent_id or not prospect_id:
            raise VonageCallTransportError(
                "voice intent and prospect context required"
            )
        if not webhook_token:
            raise VonageCallTransportError(
                "EMPIRE_VONAGE_WEBHOOK_TOKEN required"
            )
        answer_url = _context_url(
            self.config.answer_url,
            intent_id=intent_id,
            prospect_id=prospect_id,
            token=webhook_token,
        )
        body: dict[str, Any] = {
            "to": [{"type": "phone", "number": to_number}],
            "from": {"type": "phone", "number": from_number},
            "answer_url": [answer_url],
        }
        if self.config.event_url:
            body["event_url"] = [
                _context_url(
                    self.config.event_url,
                    intent_id=intent_id,
                    prospect_id=prospect_id,
                    token=webhook_token,
                )
            ]
        return body

    def _jwt(self) -> str:
        if not self.config.application_id or not self.config.private_key:
            raise VonageCallTransportError(
                "Vonage application credentials required"
            )
        now = int(time.time())
        claims = {
            "application_id": self.config.application_id,
            "iat": now,
            "nbf": now,
            "exp": now + 120,
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(
            claims,
            self.config.private_key,
            algorithm="RS256",
            headers={"typ": "JWT"},
        )
        return str(token)

    def preview(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        readiness = self.config.readiness()
        destination = None
        destination_error = None
        try:
            destination = _provider_number(plan.get("phone"))
        except Exception as exc:
            destination_error = f"{type(exc).__name__}:{exc}"

        body = None
        body_error = None
        if readiness["configured"]:
            try:
                body = self.build_request(plan)
            except Exception as exc:
                body_error = f"{type(exc).__name__}:{exc}"

        return {
            "provider": "vonage",
            "plan_prospect_id": str(plan.get("prospect_id") or ""),
            "destination_ready": bool(destination),
            "destination_error": destination_error,
            "request_body": body,
            "request_body_error": body_error,
            "readiness": readiness,
            "execution_allowed": False,
            "provider_request_sent": False,
        }

    def create_call(
        self,
        plan: Mapping[str, Any],
        *,
        authorized: bool = False,
    ) -> dict[str, Any]:
        if not authorized:
            raise VonageCallTransportError(
                "explicit live-call authorization required"
            )
        readiness = self.config.readiness()
        if readiness["execution_allowed"] is not True:
            raise VonageCallTransportError(
                "live phone authority/provider configuration incomplete"
            )
        if plan.get("execution_allowed") is not True:
            raise VonageCallTransportError(
                "call plan is not execution-authorized"
            )
        body = self.build_request(plan)
        response = self.client.post(
            VONAGE_CALLS_URL,
            json=body,
            headers={
                "Authorization": f"Bearer {self._jwt()}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "provider": "vonage",
            "provider_request_sent": True,
            "provider_response": payload,
            "actual_revenue": False,
            "terms_accepted": False,
            "funds_moved": False,
        }
