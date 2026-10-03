"""Governed outbound e-mail provider transports.

Transport choice does not grant send authority. Callers must obtain the
canonical database-authorized outbound claim before invoking a transport.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from urllib import error, request
from urllib.parse import urlsplit

from empire_os.outbound_provider import OutboundProviderError, send_with_resend


class OutboundEmailTransport(Protocol):
    provider: str

    def send(self, payload: dict[str, Any]) -> str:
        ...


@dataclass(frozen=True)
class ResendEmailTransport:
    api_key: str
    resend_module: Any | None = None
    provider: str = "resend"

    def send(self, payload: dict[str, Any]) -> str:
        return send_with_resend(
            payload,
            api_key=self.api_key,
            resend_module=self.resend_module,
        )


@dataclass(frozen=True)
class PostalEmailTransport:
    base_url: str
    api_key: str
    timeout_seconds: float = 15.0
    opener: Callable[..., Any] | None = None
    provider: str = "postal"

    def send(self, payload: dict[str, Any]) -> str:
        if not self.api_key:
            raise OutboundProviderError("Postal API key required")
        if not isinstance(payload, dict) or not payload.get("_sender_address"):
            raise OutboundProviderError("validated outbound payload required")
        if not str(payload.get("_idempotency_key") or "").strip():
            raise OutboundProviderError("outbound idempotency key required")

        base_url = str(self.base_url or "").strip().rstrip("/")
        parsed = urlsplit(base_url)
        if not parsed.netloc or parsed.scheme not in {"http", "https"}:
            raise OutboundProviderError("valid Postal base URL required")
        if parsed.scheme != "https" and parsed.hostname not in {
            "localhost", "127.0.0.1", "::1"
        }:
            raise OutboundProviderError("HTTPS Postal base URL required")

        recipients = payload.get("to")
        if not isinstance(recipients, list) or len(recipients) != 1:
            raise OutboundProviderError("Postal transport requires one recipient")

        reply_values = payload.get("reply_to")
        if not isinstance(reply_values, list) or len(reply_values) != 1:
            raise OutboundProviderError("Postal transport requires one reply-to")

        headers = dict(payload.get("headers") or {})
        headers["X-Empire-Idempotency-Key"] = str(payload["_idempotency_key"])

        outbound: dict[str, Any] = {
            "to": recipients,
            "from": payload.get("from"),
            "reply_to": reply_values[0],
            "subject": str(payload.get("subject") or ""),
            "plain_body": str(payload.get("text") or ""),
            "headers": headers,
        }
        if payload.get("html"):
            outbound["html_body"] = payload["html"]

        for tag in payload.get("tags") or []:
            if isinstance(tag, dict) and tag.get("name") == "intent_id":
                value = str(tag.get("value") or "").strip()
                if value:
                    outbound["tag"] = value
                break

        req = request.Request(
            base_url + "/api/v1/send/message",
            data=json.dumps(outbound).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Server-API-Key": self.api_key,
            },
            method="POST",
        )

        open_fn = self.opener or request.urlopen
        response = None
        try:
            response = open_fn(req, timeout=self.timeout_seconds)
            raw = response.read()
        except error.HTTPError as exc:
            reason = exc.read().decode("utf-8", "replace")
            reason = self._sanitize(reason)
            raise OutboundProviderError(
                f"Postal send failed HTTP {exc.code}: {reason}"
            ) from exc
        except Exception as exc:
            reason = self._sanitize(str(exc))
            suffix = f": {reason}" if reason else ""
            raise OutboundProviderError(f"Postal send failed{suffix}") from exc
        finally:
            if response is not None:
                close = getattr(response, "close", None)
                if callable(close):
                    close()

        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OutboundProviderError("Postal returned invalid JSON") from exc

        if not isinstance(result, dict) or result.get("status") != "success":
            reason = self._sanitize(json.dumps(result, sort_keys=True))
            raise OutboundProviderError(f"Postal send rejected: {reason}")

        data = result.get("data")
        message_id = (
            str(data.get("message_id") or "").strip()
            if isinstance(data, dict)
            else ""
        )
        if not message_id:
            raise OutboundProviderError("Postal returned no message id")
        return message_id

    def _sanitize(self, value: str) -> str:
        text = str(value or "").replace(self.api_key, "[REDACTED_API_KEY]")
        text = re.sub(r"re_[A-Za-z0-9_-]+", "[REDACTED_API_KEY]", text)
        return text[:240]
