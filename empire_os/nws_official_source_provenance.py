"""Existing NOAA/NWS source -> original storm evidence -> universal custody.

Optional explicit one-shot public HTTPS read; otherwise pure offline review.
No storm scanning side effects, leads, publications, notifications, money,
tenant grants, Redis/DB writes, or new pipelines. All economic claims held.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from urllib.request import HTTPRedirectHandler, Request, build_opener

from empire_os.economic_signal_tenant_binding import (
    resolve_tenant_entity_binding, TenantEntityBindingError,
)
from empire_os.storm_predictor import (
    StormEvent as ExistingStormEvent, NWS_ALERTS_URL,
)
from empire_os.lead_sources.storm_alerts import UA as NWS_USER_AGENT
from empire_os.spatial_physical_adapters import event_evidence_from_storm_event
from empire_os.universal_source_custody_review import review_universal_observations

SCHEMA = "empire.nws_source_provenance_review.v1"
OFFICIAL_URL = "https://api.weather.gov/alerts/active"
# The nation-wide feed exceeded our 2MB cap. Use the documented fixed
# one-state filter for the original Chicago pilot; do not lift the cap.
PILOT_URL = OFFICIAL_URL + "?area=IL"
MAX_FEATURES = 80
MAX_RESPONSE_BYTES = 2_000_000
if NWS_ALERTS_URL != OFFICIAL_URL:
    raise RuntimeError("original NWS URL differs from reviewed source")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("NWS redirected response requires independent review")


def _time(value: Any, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{label} invalid ISO timestamp") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} requires timezone")
    return value.astimezone(timezone.utc)


def _record(feature: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    if not isinstance(feature, Mapping) or not isinstance(feature.get("properties"), Mapping):
        raise ValueError("NWS feature properties missing")
    props = feature["properties"]
    ident = feature.get("id")
    event = props.get("event")
    if type(ident) is not str or not ident.startswith(
        "https://api.weather.gov/alerts/"
    ) or len(ident) > 640:
        raise ValueError("invalid official NWS alert identifier")
    if type(event) is not str or not 1 <= len(event) <= 120:
        raise ValueError("bounded official alert type required")
    sent = _time(props.get("sent"), "NWS sent")
    if sent > now:
        raise ValueError("future NWS alert")
    # Reuse original spatial/evidence parser; no inferred damage or demand.
    allow = (
        "sent", "effective", "onset", "expires", "ends", "status",
        "messageType", "category", "severity", "certainty", "urgency",
        "response", "senderName", "event", "areaDesc",
    )
    fields = {k: props[k] for k in allow if k in props}
    fields["parameters"] = {}
    old = ExistingStormEvent(
        event_id=ident, event_type=event, occurred_at=props["sent"],
        expires_at=props.get("expires") if isinstance(props.get("expires"), str) else "",
        area_description=props.get("areaDesc") if isinstance(props.get("areaDesc"), str) else "",
        raw=fields, retrieved_at=now.isoformat(),
    )
    evidence = event_evidence_from_storm_event(old, retrieved_at=now)
    if not evidence.raw_evidence_hash:
        raise ValueError("original storm source evidence hash missing")
    return {
        "provider": "noaa_nws",
        "provider_record_id": sha256(ident.encode()).hexdigest(),
        "provider_url": PILOT_URL,
        "event_kind": "WEATHER_ALERT",
        "published_at": sent.isoformat(),
        "observed_at": now.isoformat(),
        "data_classification": "public_nonpersonal",
        "rights_claim": "public_reference",
    }


def review_nws_alert_payload(
    payload: Mapping[str, Any], *, observed_at: datetime,
    official_https_response_verified: bool = False,
) -> dict[str, Any]:
    now = _time(observed_at, "observation")
    if not isinstance(payload, Mapping) or type(payload.get("features")) is not list:
        raise ValueError("NWS GeoJSON features required")
    if len(payload["features"]) > MAX_FEATURES:
        raise ValueError("bounded NWS payload exceeded, cannot silently truncate")
    observations = []
    rejected = []
    for index, feature in enumerate(payload["features"]):
        try:
            observations.append(_record(feature, now=now))
        except (ValueError, KeyError, AttributeError, TypeError) as exc:
            if len(rejected) < 25:
                rejected.append({"index": index, "reason": str(exc)})
    custody = review_universal_observations(observations, as_of=now)
    for ref in custody["reviewed_sources"]:
        ref.update({
            "existing_storm_evidence_adapter_used": True,
            "official_https_transport_observed": official_https_response_verified is True,
            "canonical_source_registry_verified": False,
            "canonical_entity_tenant_binding_verified": False,
            "economic_signal_eligible": False,
        })
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "transport_observed": official_https_response_verified is True,
        "source_adapter": "existing_storm_predictor_and_spatial_physical_adapters",
        "universal_custody_review": custody,
        "shape_rejections": rejected,
        "canonical_source_registry_verified": False,
        "canonical_entity_tenant_binding_verified": False,
        "buyer_intent_verified": False,
        "property_damage_verified": False,
        "economic_signal_eligible": False,
        "recognized_revenue": False, "crm_written": False,
        "redis_written": False, "database_written": False,
        "notifications_sent": False, "outbound_sent": False,
        "gpu_spend_cents": 0, "execution_authority": "none",
        "blockers": [
            "SOURCE_CUSTODY_AND_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
            "CANONICAL_SOURCE_NOT_INDEPENDENTLY_BOUND",
            "CANONICAL_ENTITY_TENANT_BINDING_REQUIRED",
            "WEATHER_ALERT_CANNOT_BE_ASSUMED_MARKET_GAP",
            "NO_EVIDENCED_BUYER_INTENT_OR_REVENUE",
        ],
    }


def review_canonical_tenant_entity_binding(
    cursor: Any, *, tenant_id: str, entity_id: str, as_of: datetime,
) -> dict[str, Any]:
    """Optional canonical restricted read through original SQL resolver.

    A validated binding only proves entity scope in one tenant. It does NOT
    attach the weather alert to that entity or manufacture a market gap.
    No caller-controlled binding ref can bypass this read.
    """
    now = _time(as_of, "as_of")
    try:
        binding = resolve_tenant_entity_binding(
            cursor, tenant_id=tenant_id, entity_id=entity_id, as_of=now,
        )
    except (TenantEntityBindingError, ValueError):
        return {
            "canonical_tenant_entity_binding": "HELD",
            "economic_signal_eligible": False, "execution_authority": "none",
        }
    return {
        "canonical_tenant_entity_binding": "EXISTING_BINDING_CONFIRMED",
        "binding_kind": binding.binding_kind,
        "binding_ref_sha256": sha256(binding.binding_ref.encode()).hexdigest(),
        "weather_entity_causal_link_verified": False,
        "economic_signal_eligible": False, "execution_authority": "none",
    }


def fetch_nws_active_alerts_once(
    *, enable_official_read: bool = False, transport: Any = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """One opted-in official GET; no loops, notifications or database changes.

    An injected transport supports offline contract tests. HTTPS redirects
    blocked, no dynamically supplied URL, rate-free one request, byte cap.
    """
    if enable_official_read is not True:
        raise PermissionError("explicit original-source read authorization required")
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_RESPONSE_BYTES:
        raise ValueError("bounded NWS response byte cap required")
    req = Request(
        PILOT_URL,
        headers={"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"},
        method="GET",
    )
    opener = transport if transport is not None else build_opener(_NoRedirect())
    with opener.open(req, timeout=8) as response:
        if response.status != 200:
            raise ValueError("NWS non-success HTTP status")
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("NWS payload exceeds safety limit")
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("NWS response is not valid JSON") from exc
    return review_nws_alert_payload(
        payload, observed_at=datetime.now(timezone.utc),
        official_https_response_verified=True,
    )


def review_nws_to_existing_canonical_scope(
    payload: Mapping[str, Any], *, observed_at: datetime,
    trusted_canonical_cursor: Any = None,
    authenticated_tenant_id: str | None = None,
    canonical_entity_id: str | None = None,
) -> dict[str, Any]:
    """Join offline source review to original canonical entity scope checks.

    Only the existing authenticated caller may supply a genuine read-only
    cursor/tenant context. This function does not verify caller identity:
    the owner must use the existing signed CRM / EmpireDB reader first.
    Since NWS warnings are not economic signals, source + binding passing
    never authorises market_gap, customer records, trades or money.
    """
    review = review_nws_alert_payload(payload, observed_at=observed_at)
    counts = review["universal_custody_review"]
    if counts["source_count_structurally_reviewed"] == 0:
        state = {"canonical_tenant_entity_binding": "NOT_ATTEMPTED_NO_SOURCE_RECORD",
                 "economic_signal_eligible": False, "execution_authority": "none"}
    elif trusted_canonical_cursor is None:
        state = {"canonical_tenant_entity_binding": "HELD_AUTHENTICATED_CURSOR_REQUIRED",
                 "economic_signal_eligible": False, "execution_authority": "none"}
    elif not authenticated_tenant_id or not canonical_entity_id:
        state = {"canonical_tenant_entity_binding": "HELD_AUTHENTICATED_SCOPE_REQUIRED",
                 "economic_signal_eligible": False, "execution_authority": "none"}
    else:
        state = review_canonical_tenant_entity_binding(
            trusted_canonical_cursor, tenant_id=authenticated_tenant_id,
            entity_id=canonical_entity_id, as_of=observed_at,
        )
    return {
        "schema_version": "empire.nws_canonical_source_scope_review.v1",
        "source_review": review,
        "existing_empiredb_tenant_entity_scope_review": state,
        "canonical_source_provenance_verified": False,
        "storm_to_specific_entity_link_verified": False,
        "economic_signal_fabric_admission": "HELD_WEATHER_HAS_NO_EVIDENCED_ECONOMIC_SIGNAL",
        "opportunity_or_lead_created": False,
        "database_written": False,
        "buyer_verified": False, "revenue_verified": False,
        "execution_authority": "none",
    }
