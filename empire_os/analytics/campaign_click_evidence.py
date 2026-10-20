"""Offline, first-party campaign click evidence bridge for existing Empire Analytics.

No route, collector, redirect, pixel, recipient lookup, CRM mutation or outbound.
The token is an opaque signed pointer; a valid token proves neither that a
human clicked nor that tracking/marketing permission exists. A trusted,
server-side gateway and canonical purpose/consent/CRM policies must be supplied
by the respective existing owners before any live instrumentation.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import re
from typing import Any

SCHEMA = "empire.analytics.campaign_click_evidence.v1"
VERSION = "ecc1"
MAX_TTL = timedelta(days=30)
MAX_BATCH = 250
MAX_OBSERVATION_AGE = timedelta(hours=48)

_OPAQUE = re.compile(r"^[0-9a-f]{32}$")
_CAMPAIGN = re.compile(r"^campaign_[0-9a-f]{24}$")
_LINK = re.compile(r"^link_[0-9a-f]{16,32}$")
_TENANT = re.compile(r"^tenant_[a-z0-9]{8,40}$")
_TOKEN = re.compile(r"^ecc1\.([0-9a-f]{32})\.([0-9]{10})\.([0-9]{10})\.([A-Za-z0-9_-]{43})$")
_DESTINATIONS = frozenset({
    "/commercial", "/predictive-revenue", "/buy", "/industries", "/roofing",
    "/uk/roofing",
})
_CHANNELS = frozenset({"email", "linkedin", "organic_social", "youtube"})
_PERMISSIONS = frozenset({"permitted", "unknown", "suppressed", "revoked"})
_AUTOMATION = frozenset({"suspected_human", "scanner", "uncertain"})


class ClickEvidenceHeld(ValueError):
    """Refuse untrusted, ambiguous, out-of-scope or stale click evidence."""


@dataclass(frozen=True)
class CampaignLinkBinding:
    """Private owner-registry binding. Never embed this structure in a URL."""

    tenant_ref: str
    campaign_id: str
    link_id: str
    recipient_lookup_key: str
    destination_path: str
    channel: str
    contact_permission: str

    def validate(self) -> None:
        if (type(self.tenant_ref) is not str or not _TENANT.fullmatch(self.tenant_ref)
                or type(self.campaign_id) is not str
                or not _CAMPAIGN.fullmatch(self.campaign_id)
                or type(self.link_id) is not str or not _LINK.fullmatch(self.link_id)
                or type(self.recipient_lookup_key) is not str
                or not _OPAQUE.fullmatch(self.recipient_lookup_key)
                or self.recipient_lookup_key == "0" * 32
                or type(self.destination_path) is not str
                or self.destination_path not in _DESTINATIONS
                or type(self.channel) is not str or self.channel not in _CHANNELS
                or type(self.contact_permission) is not str
                or self.contact_permission not in _PERMISSIONS):
            raise ClickEvidenceHeld("CLICK_REGISTRY_BINDING_INVALID")


@dataclass(frozen=True)
class GatewayClickReceipt:
    """Must be sourced by a real first-party, server-trusted gateway, not JS."""

    gateway_event_id: str
    link_token: str
    observed_at: datetime
    automation_class: str
    gateway_provenance_verified: bool
    registry_binding_verified: bool


def _time(when: datetime) -> datetime:
    if type(when) is not datetime or when.tzinfo is None:
        raise ClickEvidenceHeld("CLICK_TIMEZONE_REQUIRED")
    return when.astimezone(timezone.utc)


def _key(secret: bytes) -> bytes:
    if type(secret) is not bytes or len(secret) < 32:
        raise ClickEvidenceHeld("CLICK_SIGNING_KEY_UNAVAILABLE")
    return secret


def _signed_body(binding: CampaignLinkBinding, nonce: str, iat: int, exp: int) -> bytes:
    # The HMAC covers the PRIVATE recipient and tenancy mapping; those values
    # are never serialized into the public click token.
    fields = (
        VERSION, nonce, str(iat), str(exp), binding.tenant_ref,
        binding.campaign_id, binding.link_id, binding.recipient_lookup_key,
        binding.destination_path, binding.channel,
    )
    return "|".join(fields).encode("ascii")


def _signature(key: bytes, body: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(key, body, hashlib.sha256).digest()).decode("ascii").rstrip("=")


def issue_offline_link_token(
    binding: CampaignLinkBinding, *, secret: bytes, nonce: str,
    issued_at: datetime, expires_at: datetime,
) -> str:
    """Produce a private-review link token; this does not publish/send a URL."""
    binding.validate()
    if binding.contact_permission != "permitted":
        raise ClickEvidenceHeld("CLICK_RECIPIENT_PERMISSION_NOT_CURRENT")
    _key(secret)
    if type(nonce) is not str or not _OPAQUE.fullmatch(nonce) or nonce == "0" * 32:
        raise ClickEvidenceHeld("CLICK_NONCE_INVALID")
    start, end = _time(issued_at), _time(expires_at)
    # Second-precision timestamps avoid accidentally extending lifetime.
    iat, exp = int(start.timestamp()), int(end.timestamp())
    if not 0 < exp - iat <= int(MAX_TTL.total_seconds()):
        raise ClickEvidenceHeld("CLICK_TOKEN_TTL_INVALID")
    sig = _signature(secret, _signed_body(binding, nonce, iat, exp))
    return f"{VERSION}.{nonce}.{iat}.{exp}.{sig}"


def token_nonce_untrusted(token: str) -> str:
    """Extract a LOOKUP ONLY key; the token is untrusted until verification."""
    if type(token) is not str or len(token) > 200:
        raise ClickEvidenceHeld("CLICK_TOKEN_MALFORMED")
    match = _TOKEN.fullmatch(token)
    if match is None:
        raise ClickEvidenceHeld("CLICK_TOKEN_MALFORMED")
    return match.group(1)


def verify_offline_link_token(
    token: str, binding: CampaignLinkBinding, *,
    secret: bytes, now: datetime,
) -> dict[str, bool]:
    binding.validate()
    _key(secret)
    match = _TOKEN.fullmatch(token) if type(token) is str and len(token) <= 200 else None
    if match is None:
        raise ClickEvidenceHeld("CLICK_TOKEN_MALFORMED")
    nonce, raw_iat, raw_exp, provided_sig = match.groups()
    iat, exp = int(raw_iat), int(raw_exp)
    if (not 0 < exp - iat <= int(MAX_TTL.total_seconds())
            or raw_iat != str(iat) or raw_exp != str(exp)):
        raise ClickEvidenceHeld("CLICK_TOKEN_TTL_INVALID")
    expected = _signature(secret, _signed_body(binding, nonce, iat, exp))
    if not hmac.compare_digest(provided_sig, expected):
        raise ClickEvidenceHeld("CLICK_TOKEN_SIGNATURE_MISMATCH")
    current = int(_time(now).timestamp())
    if current < iat or current >= exp:
        raise ClickEvidenceHeld("CLICK_TOKEN_OUTSIDE_WINDOW")
    return {
        "signature_verified": True,
        "human_click_verified": False,
        "recipient_presence_verified": False,
        "website_session_verified": False,
        "followup_authorized": False,
    }


def review_offline_click_receipts(
    event_ids: Sequence[str], *,
    resolve_server_receipt: Callable[[str], GatewayClickReceipt] | None,
    resolve_private_link_binding: Callable[[str], CampaignLinkBinding] | None,
    secret: bytes, now: datetime,
) -> dict[str, Any]:
    """Aggregate opaque, verified-by-caller gateway receipts for OWNER REVIEW.

    The caller's gateway and registry resolvers must themselves enforce
    authenticity, tenant scoping, suppression, provenance and idempotency.
    This function does not establish production verification or grant follow-up.
    """
    _key(secret)
    current = _time(now)
    if (type(event_ids) not in (list, tuple) or not 1 <= len(event_ids) <= MAX_BATCH
            or not callable(resolve_server_receipt)
            or not callable(resolve_private_link_binding)):
        raise ClickEvidenceHeld("CLICK_TRUSTED_GATEWAY_INPUT_REQUIRED")
    counts = {
        "reviewed_events": 0,
        "suspected_human_events": 0,
        "scanner_excluded_events": 0,
        "uncertain_events": 0,
        "permission_held_events": 0,
        "followup_review_candidates": 0,
        "multi_asset_review_groups": 0,
        "duplicate_event_ids_discarded": 0,
    }
    # Private in-memory grouping only. No identity leaves this offline review.
    assets_by_recipient: dict[tuple[str, str, str], set[str]] = {}
    seen: set[str] = set()
    for event_id in event_ids:
        if type(event_id) is not str or not _OPAQUE.fullmatch(event_id) or event_id == "0" * 32:
            raise ClickEvidenceHeld("CLICK_EVENT_ID_INVALID")
        if event_id in seen:
            counts["duplicate_event_ids_discarded"] += 1
            continue
        seen.add(event_id)
        try:
            receipt = resolve_server_receipt(event_id)
            if (type(receipt) is not GatewayClickReceipt
                    or receipt.gateway_event_id != event_id
                    or receipt.gateway_provenance_verified is not True
                    or receipt.registry_binding_verified is not True):
                raise ClickEvidenceHeld("CLICK_GATEWAY_PROVENANCE_UNVERIFIED")
            if receipt.automation_class not in _AUTOMATION:
                raise ClickEvidenceHeld("CLICK_AUTOMATION_CLASS_UNVERIFIED")
            observed = _time(receipt.observed_at)
            if not current - MAX_OBSERVATION_AGE <= observed <= current + timedelta(minutes=1):
                raise ClickEvidenceHeld("CLICK_EVENT_STALE_OR_FUTURE")
            nonce = token_nonce_untrusted(receipt.link_token)
            binding = resolve_private_link_binding(nonce)
            if type(binding) is not CampaignLinkBinding:
                raise ClickEvidenceHeld("CLICK_REGISTRY_BINDING_UNVERIFIED")
            verify_offline_link_token(receipt.link_token, binding, secret=secret, now=observed)
        except ClickEvidenceHeld:
            raise
        except Exception:
            # Never surface exception text: external resolvers may contain PII.
            raise ClickEvidenceHeld("CLICK_SERVER_EVIDENCE_UNAVAILABLE") from None
        counts["reviewed_events"] += 1
        if binding.contact_permission != "permitted":
            counts["permission_held_events"] += 1
        elif receipt.automation_class == "scanner":
            counts["scanner_excluded_events"] += 1
        elif receipt.automation_class == "uncertain":
            counts["uncertain_events"] += 1
        else:
            counts["suspected_human_events"] += 1
            counts["followup_review_candidates"] += 1
            group = (binding.tenant_ref, binding.campaign_id,
                     binding.recipient_lookup_key)
            assets_by_recipient.setdefault(group, set()).add(binding.link_id)
    counts["multi_asset_review_groups"] = sum(
        len(assets) > 1 for assets in assets_by_recipient.values()
    )
    return {
        "schema_version": SCHEMA,
        "status": "OFFLINE_SIGNED_CLICK_EVIDENCE_REVIEW_ONLY",
        "counts": counts,
        "production_click_collector_enabled": False,
        "live_clicks_verified": False,
        "individual_human_identity_verified": False,
        "retargeting_consent_verified": False,
        "crm_attribution_verified": False,
        "realised_revenue_verified": False,
        "automatic_followup_enabled": False,
        "website_or_cookies_changed": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }
