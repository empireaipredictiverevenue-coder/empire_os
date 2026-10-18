"""Conservative event-revision capture for re-downloaded NYC permit records.

Never creates a prospect, marks damage, changes a verified identity or
promotes observed source metadata to newly issued project evidence.
Source evidence remains in the EXISTING signal inbox/Source Intelligence.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from empire_os.permit_project_intelligence import _official_day, _official_url

# Official event and project-reference columns ONLY. No owner/permittee
# names, phones, addresses, descriptions or speculative categories.
PERMIT_EVENT_FIELDS = (
    "filing_date",
    "issuance_date",
    "expiration_date",
    "job_start_date",
    "permit_status",
    "filing_status",
    "job_type",
    "work_type",
    "bbl",
    "bin__",
)
MAX_EVENT_REVISIONS = 12


def _job(raw: Mapping[str, Any] | None) -> str:
    if not isinstance(raw, Mapping):
        return ""
    value = raw.get("job__")
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return ""
    clean = str(value).strip()
    return clean if re.fullmatch(r"\d{5,12}", clean) else ""


def _trusted(row: Mapping[str, Any]) -> str:
    if row.get("source") != "permits_nyc":
        return ""
    raw = row.get("raw")
    job = _job(raw)
    return job if _official_url(row.get("url"), job) is not None else ""


def _safe_event_fields(raw: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in PERMIT_EVENT_FIELDS:
        value = raw.get(key)
        if value is None or not isinstance(value, (str, int)) or isinstance(value, bool):
            continue
        cleaned = str(value).strip()
        if not cleaned or len(cleaned) > 70:
            continue
        if key in ("filing_date", "issuance_date", "expiration_date", "job_start_date"):
            # Preserve only valid calendar dates; no narrative or contact.
            if _official_day(cleaned) is None:
                continue
        elif key in ("bbl", "bin__"):
            if not re.fullmatch(r"\d{7,12}", cleaned):
                continue
        elif not re.fullmatch(r"[A-Za-z0-9_ -]{1,40}", cleaned):
            continue
        result[key] = cleaned
    return result


def _event_signature(raw: Mapping[str, Any]) -> str:
    return sha256(json.dumps(_safe_event_fields(raw),
                             sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def trusted_permit_match(existing: Mapping[str, Any],
                         incoming: Mapping[str, Any]) -> bool:
    """A true official job-key match survives changes in owner/source labels."""
    old_job, new_job = _trusted(existing), _trusted(incoming)
    return bool(old_job and old_job == new_job)


def refresh_trusted_permit_event(
    existing: dict[str, Any], incoming: Mapping[str, Any], *,
    observed_at: str,
) -> dict[str, Any]:
    """Mutate existing *locked inbox record* with a bounded real source revision.

    No brand-new signal, personal/contact change or false fresh event. A newer
    collection only updates last_seen_at unless event columns actually differ.
    """
    result = {
        "decision": "matched",
        "event_revision_added": False,
        "trusted_job_reference": False,
        "event_revision_count": len(existing.get("source_event_revisions") or []),
    }
    if not trusted_permit_match(existing, incoming):
        return result
    result["trusted_job_reference"] = True
    old_raw = existing.get("raw")
    new_raw = incoming.get("raw")
    if not isinstance(old_raw, dict) or not isinstance(new_raw, Mapping):
        return result
    # An older source run must never roll back a newer recorded issuance/state.
    old_run = _official_day(old_raw.get("dobrundate"))
    new_run = _official_day(new_raw.get("dobrundate"))
    if old_run and new_run and new_run < old_run:
        result["source_state"] = "OLDER_SOURCE_RUN_NO_EVENT_OVERWRITE"
        return result
    old_values = _safe_event_fields(old_raw)
    incoming_values = _safe_event_fields(new_raw)
    if not incoming_values:
        return result
    merged = {**old_values, **incoming_values}
    changed = {
        k: {"previous": old_values.get(k), "current": value}
        for k, value in incoming_values.items()
        if old_values.get(k) != value
    }
    if not changed:
        if new_run and (old_run is None or new_run > old_run):
            old_raw["dobrundate"] = str(new_raw["dobrundate"])
        return result

    # The source-run date is evidence of an updated source snapshot, NOT an
    # actual filing or issuance. The true project event is classified later.
    revision = {
        "job__": _trusted(incoming),
        "observed_at": observed_at,
        "official_run_date": new_run.date().isoformat() if new_run else None,
        "changed_event_fields": changed,
        "source_event_truth": "SOURCE_COLUMN_REVISION_NOT_VERIFIED_NEW_PROJECT",
        "company_or_buyer_verified": False,
        "outbound_authorized": False,
    }
    history = existing.get("source_event_revisions")
    if not isinstance(history, list):
        history = []
    existing["source_event_revisions"] = (history + [revision])[-MAX_EVENT_REVISIONS:]
    for k, v in merged.items():
        old_raw[k] = v
    if new_run:
        old_raw["dobrundate"] = str(new_raw["dobrundate"])
    existing["last_material_source_event_at"] = observed_at
    existing["source_event_revision_count"] = int(
        existing.get("source_event_revision_count") or 0) + 1
    result["event_revision_added"] = True
    result["event_revision_count"] = existing["source_event_revision_count"]
    return result
