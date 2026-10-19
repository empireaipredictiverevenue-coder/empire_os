"""Sanitised read-only use of the EXISTING Empire Tag Intelligence monitor.

It observes static page markup only. Never concludes delivery, website
consent validity, live visitor sessions, cookies, CRM or revenue proof.
Never returns tag IDs, URLs with query strings, visitor data or secrets.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
from typing import Any

SOURCE_SCHEMA = "empire.tag_intelligence.monitor.v1"
SCHEMA = "empire.analytics.collection_readiness.v1"
MONITOR = Path("/srv/empire_os/runtime/tag_intelligence/latest.json")
MAX_BYTES = 256 * 1024
MAX_STALE = timedelta(hours=48)
HOST = "https://empire-ai.co.uk"


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "status": "HELD_TAG_SOURCE_UNVERIFIED",
        "source": "existing_empire_tag_intelligence_monitor",
        "reason": reason,
        "static_homepage_observation_verified": False,
        "tag_firing_or_delivery_verified": False,
        "lawful_website_analytics_consent_verified": False,
        "website_sessions_verified": False,
        "first_party_collector_activation_verified": False,
        "crm_attribution_verified": False,
        "realised_revenue_verified": False,
        "mode": "READ_ONLY",
        "database_writes": False,
        "outbound_sent": False,
        "public_site_changed": False,
        "execution_authority": "NONE",
    }


def review_snapshot(snapshot: Any, *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != SOURCE_SCHEMA:
        return _held("TAG_SOURCE_SCHEMA_NOT_ATTESTED")
    if (snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"
            or snapshot.get("measurement_platform_write") is not False
            or snapshot.get("automatic_tag_mutation") is not False):
        return _held("TAG_SOURCE_OBSERVATION_MODE_INVALID")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        return _held("MONITOR_CLOCK_UNVERIFIED")
    ts = snapshot.get("generated_at")
    if type(ts) is not str or len(ts) > 40:
        return _held("TAG_SOURCE_TIMESTAMP_MISSING")
    try:
        observed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("naive")
        age = now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
    except ValueError:
        return _held("TAG_SOURCE_TIMESTAMP_INVALID")
    if age < timedelta(minutes=-5) or age > MAX_STALE:
        return _held("TAG_SOURCE_STALE_OR_FUTURE")
    targets = snapshot.get("targets")
    if not isinstance(targets, list) or len(targets) > 50:
        return _held("TAG_SOURCE_TARGETS_INVALID")
    matches = [row for row in targets if isinstance(row, Mapping)
               and row.get("url") in (HOST, HOST + "/")]
    if len(matches) != 1 or matches[0].get("available") is not True:
        return _held("EMPIRE_HOMEPAGE_STATIC_OBSERVATION_MISSING")
    row = matches[0]
    tags = row.get("measurement_tags")
    if not isinstance(tags, Mapping):
        return _held("TAG_MEASUREMENT_SURFACE_MISSING")
    limits = row.get("limitations")
    if not isinstance(limits, list) or "static_markup_observation_only" not in limits:
        return _held("STATIC_OBSERVATION_LIMITATIONS_NOT_DECLARED")
    def present(name: str) -> bool:
        value = tags.get(name)
        return isinstance(value, list) and bool(value)
    # Configured evidence is not proof of runtime firing, delivery or
    # valid UK website analytics consent. Never accept browser's "true".
    consent = tags.get("consent_mode_enabled")
    static_consent = ("CONFIG_FLAG_PRESENT_NOT_LEGAL_PROOF" if consent is True
                      else "NOT_VERIFIED_FROM_STATIC_OBSERVATION")
    return {
        "schema_version": SCHEMA,
        "status": "STATIC_HOMEPAGE_TAG_SOURCE_OBSERVED_COLLECTOR_HELD",
        "source": "existing_empire_tag_intelligence_monitor",
        "source_schema_version": SOURCE_SCHEMA,
        "source_generated_at_utc": observed.astimezone(timezone.utc).isoformat(),
        "site": "empire-ai.co.uk",
        "static_homepage_observation_verified": True,
        "static_ga4_tag_declared": present("ga4_measurement_ids"),
        "static_gtm_tag_declared": present("gtm_container_ids"),
        "static_google_tag_declared": present("google_tag_ids"),
        "static_consent_configuration": static_consent,
        "tag_firing_or_delivery_verified": False,
        "lawful_website_analytics_consent_verified": False,
        "website_sessions_verified": False,
        "first_party_collector_activation_verified": False,
        "crm_attribution_verified": False,
        "realised_revenue_verified": False,
        "mode": "READ_ONLY",
        "database_writes": False,
        "outbound_sent": False,
        "public_site_changed": False,
        "execution_authority": "NONE",
    }


def review_existing_monitor(path: Path = MONITOR, *,
                            now: datetime | None = None) -> dict[str, Any]:
    # Fixed local read. Caller can't choose a URL, so there are no probes,
    # external sends or filesystem writes.
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            return _held("TAG_MONITOR_FILE_UNAVAILABLE_OR_UNBOUNDED")
        snapshot = json.loads(path.read_bytes())
    except (OSError, ValueError, TypeError):
        return _held("TAG_MONITOR_FILE_UNREADABLE")
    return review_snapshot(snapshot, now=now)
