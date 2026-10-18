"""Single-shot official Environment Agency warning stream -> existing Sensor Mesh.

Zero persistent writes, no scheduler, no address/contact data, and no claim
that warning = damaged property or buyer. Only GET a fixed public OGL source
when explicitly requested. No dynamic URLs, credentials or paid providers.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping

from empire_os.real_world_event_intelligence import SourceEvidence

ENDPOINT = "https://environment.data.gov.uk/flood-monitoring/id/floods?_limit=100"
DOCUMENTATION = "https://environment.data.gov.uk/flood-monitoring/doc/reference"
SCHEMA = "empire.ea_flood_source_observation.v1"
ATTRIBUTION = (
    "This uses Environment Agency flood and river level data from the "
    "real-time data API (Beta)"
)
MAX_RESPONSE_BYTES = 750_000
MAX_EVENTS = 100
SEVERITY_LEVELS = (1, 2, 3, 4)
ID_PREFIX = "http://environment.data.gov.uk/flood-monitoring/id/floods/"
HTTPS_ID_PREFIX = "https://environment.data.gov.uk/flood-monitoring/id/floods/"


class SourceObservationUnavailable(RuntimeError):
    pass


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceObservationUnavailable("official flood source redirected")


def _official_get() -> bytes:
    request = urllib.request.Request(
        ENDPOINT, method="GET",
        headers={"Accept": "application/json",
                 "User-Agent": "EmpireAI-SourceIntelligence/1.0 (empire-ai.co.uk)"},
    )
    opener = urllib.request.build_opener(_RefuseRedirects)
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200:
                raise SourceObservationUnavailable("non-200 official source response")
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "json" not in content_type:
                raise SourceObservationUnavailable("unexpected official source content type")
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise SourceObservationUnavailable("official flood source not currently reachable") from exc
    if not 0 < len(content) <= MAX_RESPONSE_BYTES:
        raise SourceObservationUnavailable("response size outside budget")
    return content


def _aware(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if not isinstance(result, datetime) or result.utcoffset() is None:
        raise ValueError("timezone-aware observation clock required")
    return result.astimezone(timezone.utc)


def normalize_ea_flood_warnings(
    payload: Mapping[str, Any],
    *,
    retrieved_at: datetime,
) -> dict[str, Any]:
    """Truthful observations with per-record original-source hash, no contact."""
    now = _aware(retrieved_at)
    if not isinstance(payload, Mapping):
        raise ValueError("EA JSON object required")
    metadata = payload.get("meta")
    if not isinstance(metadata, Mapping) or metadata.get("publisher") != "Environment Agency":
        raise ValueError("EA publisher identity must be present")
    licence = str(metadata.get("licence") or "").lower()
    if "nationalarchives.gov.uk/doc/open-government-licence" not in licence:
        raise ValueError("EA open licence metadata required")
    items = payload.get("items")
    if not isinstance(items, list) or len(items) > MAX_EVENTS:
        raise ValueError("EA bounded item list required")
    unique: set[str] = set()
    observations: list[dict[str, Any]] = []
    severity = Counter()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("invalid EA warning object")
        ref = item.get("@id")
        if (not isinstance(ref, str) or not
                (ref.startswith(ID_PREFIX) or ref.startswith(HTTPS_ID_PREFIX))
                or len(ref) > 240):
            raise ValueError("invalid official warning identifier")
        raw_id = ref.split("/id/floods/", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,90}", raw_id) or raw_id in unique:
            raise ValueError("invalid or repeated warning identifier")
        unique.add(raw_id)
        code = item.get("floodAreaID")
        if code is not None and (
            not isinstance(code, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,100}", code
            )
        ):
            raise ValueError("untrusted geographic code")
        level = item.get("severityLevel")
        if type(level) is not int or level not in SEVERITY_LEVELS:
            raise ValueError("untrusted flood warning severity")
        # Public text fields can be messy, unbounded, potentially personal.
        # Never copy description, message, recipient or precise addresses.
        selected = {
            "source_record_id": raw_id,
            "flood_area_code": code,
            "severity_level": level,
            "source_message_changed": item.get("timeMessageChanged"),
        }
        # The EA source's time fields sometimes omit a timezone; do not
        # reinterpret them as UTC or determine whether warning is still live.
        raw_hash = sha256(json.dumps(
            selected, sort_keys=True, separators=(",", ":"), default=str,
            allow_nan=False,
        ).encode()).hexdigest()
        source = SourceEvidence(
            source="uk_environment_agency_flood_monitoring",
            source_record_id=raw_id,
            retrieved_at=now,
            evidence_refs=(ref, DOCUMENTATION),
            raw_evidence_hash=raw_hash,
            source_severity=str(level),
            geographic_scope=code,
        )
        observations.append({
            "source_record_digest": sha256(raw_id.encode()).hexdigest(),
            "source_evidence": source.as_dict(),
            "severity_level": level,
            "source_reports_warning_active": level in (1, 2, 3),
            "geographic_scope_code_digest": (
                sha256(code.encode()).hexdigest() if code else None
            ),
            "independent_physical_damage_proven": False,
            "buyer_intent_proven": False,
            "commercial_exposure_proven": False,
        })
        severity[str(level)] += 1
    observations.sort(key=lambda row: row["source_record_digest"])
    sample_complete = len(items) < MAX_EVENTS
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source": "uk_environment_agency_flood_monitoring",
        "endpoint": ENDPOINT,
        "source_documentation": DOCUMENTATION,
        "attribution_required": ATTRIBUTION,
        "source_records_in_sample": len(items),
        "sample_at_provider_limit": not sample_complete,
        "source_global_total_known": False,
        "warning_severity_counts_in_sample": dict(sorted(severity.items())),
        "source_observations": observations,
        "status": "SOURCE_SAMPLE_OBSERVED" if items else "ZERO_WARNINGS_IN_SOURCE_SAMPLE",
        "source_truth": "OBSERVED_SOURCE_RECORD",
        "physical_event_truth": "UNKNOWN",
        "data_mining_scope": "OFFICIAL_PUBLIC_EVENT_ONLY",
        "geographic_property_owner_or_damage_proven": False,
        "buyer_intent_proven": False,
        "source_monitoring_scheduled": False,
        "canonical_signal_inbox_mutated": False,
        "source_downloaded_by_review": False,
        "outbound_sent": False,
        "payments_moved": False,
        "execution_authority": "none",
    }


def observe_ea_flood_warnings(
    *,
    as_of: datetime | None = None,
    fetcher: Callable[[], bytes] | None = None,
) -> dict[str, Any]:
    """One single bounded public GET at caller request; safe injectable tests."""
    timestamp = _aware(as_of)
    raw = (fetcher or _official_get)()
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RESPONSE_BYTES:
        raise SourceObservationUnavailable("invalid or oversized source bytes")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise SourceObservationUnavailable("unparseable official JSON") from exc
    report = normalize_ea_flood_warnings(payload, retrieved_at=timestamp)
    report["source_downloaded_by_review"] = True
    return report
