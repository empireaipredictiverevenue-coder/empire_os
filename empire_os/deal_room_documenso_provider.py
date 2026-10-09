"""Documenso V2 authenticated READ-ONLY transport for the existing EmpireOS Deal Room.

Not another signing platform. API reads are allowed only for the instance
configured by EmpireOS, never for an address supplied by a requester.
No distribution, document creation, signing, DB writes or revenue changes.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from ipaddress import ip_address
from urllib.parse import urlsplit

import requests

MAX_RESPONSE_BYTES = 1024 * 1024
BASE_URL_DEFAULT = "https://app.documenso.com/api/v2"


def validate_origin(base_url: str, trusted_hostname: str) -> str:
    if not isinstance(base_url, str) or not isinstance(trusted_hostname, str):
        raise ValueError("DOCUMENSO_ORIGIN_NOT_CONFIGURED")
    try:
        url = urlsplit(base_url.strip())
    except ValueError as exc:
        raise ValueError("DOCUMENSO_ORIGIN_INVALID") from exc
    host = url.hostname
    if (url.scheme != "https" or not host or url.username or url.password or url.port
            or url.query or url.fragment or url.path.rstrip("/") != "/api/v2"
            or trusted_hostname.lower().strip() != host.lower()):
        raise ValueError("DOCUMENSO_ORIGIN_NOT_ALLOWLISTED")
    if host.lower() in {"localhost"} or host.endswith((".local", ".internal")):
        raise ValueError("DOCUMENSO_ORIGIN_PRIVATE")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("DOCUMENSO_IP_LITERAL_NOT_ALLOWED")
    return f"https://{host.lower()}/api/v2"


def envelope_id_valid(identifier: object) -> bool:
    if not isinstance(identifier, str):
        return False
    return identifier.startswith("envelope_") and len(identifier) <= 160 and len(identifier) > 10 and all(
        c.isascii() and (c.isalnum() or c in "-_") for c in identifier[9:]
    )


@dataclass(frozen=True)
class ReadOnlyDocumenso:
    api_base_url: str
    trusted_hostname: str
    api_token: str
    request_timeout: float = 6.0

    def get_envelope(self, envelope_id: str, *, session=None) -> dict:
        origin = validate_origin(self.api_base_url, self.trusted_hostname)
        if not envelope_id_valid(envelope_id):
            raise ValueError("DOCUMENSO_ENVELOPE_ID_INVALID")
        if (not isinstance(self.api_token, str) or not self.api_token.startswith("api_")
                or len(self.api_token) < 16):
            raise ValueError("DOCUMENSO_API_TOKEN_UNAVAILABLE")
        if not 1 <= self.request_timeout <= 10:
            raise ValueError("DOCUMENSO_UNBOUNDED_READ_TIMEOUT")
        transport = session
        if transport is None:
            transport = requests.Session()
            transport.trust_env = False
        response = transport.get(
            f"{origin}/envelope/{envelope_id}",
            headers={"Authorization": self.api_token, "Accept": "application/json"},
            timeout=self.request_timeout, allow_redirects=False,
            stream=True,
        )
        try:
            if response.status_code != 200:
                raise ValueError("DOCUMENSO_PROVIDER_READ_FAILED")
            size = response.headers.get("Content-Length", "") if isinstance(response.headers, Mapping) else ""
            if size.isdigit() and int(size) > MAX_RESPONSE_BYTES:
                raise ValueError("DOCUMENSO_RESPONSE_EXCEEDS_LIMIT")
            content = b""
            for block in response.iter_content(chunk_size=65536):
                content += block
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ValueError("DOCUMENSO_RESPONSE_EXCEEDS_LIMIT")
            try:
                import json
                body = json.loads(content)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("DOCUMENSO_RESPONSE_INVALID_JSON") from exc
            if not isinstance(body, dict) or body.get("id") != envelope_id:
                raise ValueError("DOCUMENSO_ENVELOPE_ID_MISMATCH")
            return body
        finally:
            response.close()


def _timestamp(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def reconcile_envelope_readback(
    provider_document: Mapping, *,
    envelope_id: str, agreement_external_id: str,
    signer_emails: tuple[str, str],
) -> dict:
    """Validate authenticated API payload; no signed PDF proof is inferred."""
    if not isinstance(provider_document, Mapping) or not envelope_id_valid(envelope_id):
        raise ValueError("DOCUMENSO_READBACK_INVALID")
    if (provider_document.get("id") != envelope_id
            or provider_document.get("externalId") != agreement_external_id
            or provider_document.get("type") != "DOCUMENT"):
        raise ValueError("DOCUMENSO_AGREEMENT_IDENTITY_MISMATCH")
    if (not isinstance(signer_emails, tuple) or len(signer_emails) != 2
            or any(not isinstance(x, str) or "@" not in x for x in signer_emails)
            or signer_emails[0].casefold() == signer_emails[1].casefold()):
        raise ValueError("DOCUMENSO_EXPECTED_SIGNER_BINDINGS_INVALID")
    recipients = provider_document.get("recipients")
    if not isinstance(recipients, list):
        raise ValueError("DOCUMENSO_RECIPIENTS_MISSING")
    signers = [x for x in recipients if isinstance(x, Mapping) and x.get("role") == "SIGNER"]
    observed_emails = {x.get("email", "").casefold() for x in signers if isinstance(x.get("email"), str)}
    if len(signers) != 2 or observed_emails != {s.casefold() for s in signer_emails}:
        raise ValueError("DOCUMENSO_SIGNERS_NOT_CONFIRMED")
    status = provider_document.get("status")
    if status not in {"DRAFT", "PENDING", "COMPLETED", "REJECTED", "CANCELLED"}:
        raise ValueError("DOCUMENSO_STATUS_NOT_RECOGNISED")
    complete = status == "COMPLETED"
    if complete and (
        not _timestamp(provider_document.get("completedAt"))
        or any(x.get("signingStatus") != "SIGNED"
               or not _timestamp(x.get("signedAt")) for x in signers)
    ):
        raise ValueError("DOCUMENSO_SIGNER_COMPLETION_NOT_VERIFIED")
    return {
        "schema": "empire.deal_room.documenso_readback.v1",
        "mode": "OBSERVE", "provider": "documenso",
        "envelope_id": envelope_id, "external_id": agreement_external_id,
        "provider_status": status, "all_required_signers_completed": complete,
        "signed_pdf_verified": False, "audit_trail_verified": False,
        "canonical_agreement_registered": False, "revenue_recognized": False,
        "distribution_authorized": False, "execution_authority": "none",
    }
