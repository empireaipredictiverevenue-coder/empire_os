"""Read-only observer for orphaned legacy permit inventory.

Consumes a bounded slice of public.lane_leads, reconstructs identity from
preserved notes, revalidates supported permit evidence, and writes only a
runtime recovery artifact. It never promotes prospects, sends outreach,
creates commercial terms, or treats historical Omega as current truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
import urllib.parse

import requests

from empire_os.lead_sources.permits import URL as NYC_PERMIT_URL
from empire_os.qualification_worker_v2 import request_json


OUTPUT = Path("runtime/recovery/legacy_permit_recovery_latest.json")
MAX_BATCH_SIZE = 500
MAX_SCAN_ROWS = 2500

_NOTE_RE = re.compile(
    r"^name=(.*?)\s+email=(.*?)\s+phone=(.*?)\s+metro=(.*?)"
    r"\s+state=(.*?)\s+details=(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_PERMIT_RE = re.compile(
    r"\bpermit\s+#?([A-Za-z0-9-]+)\s+issued\s+"
    r"(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_BBL_RE = re.compile(r"\bBBL\s+([A-Za-z0-9-]+)", re.IGNORECASE)
_ADDRESS_RE = re.compile(r"\bAddress:\s*(.+)$", re.IGNORECASE | re.DOTALL)
_LEAD_REF_RE = re.compile(r"\blead_ref=([A-Za-z0-9-]+)", re.IGNORECASE)
_NYC_BOROUGH_SUFFIX_RE = re.compile(
    r"\s+\((Queens|Brooklyn|Manhattan|Bronx|Staten Island)\)\s*$",
    re.IGNORECASE,
)

_PLACEHOLDER_NAMES = {
    "",
    "n/a",
    "na",
    "none",
    "unknown",
    "not available",
    "not applicable",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _phone_digits(value: str) -> str:
    return "".join(char for char in _clean(value) if char.isdigit())


def _meaningful_name(value: str) -> bool:
    return _clean(value).casefold() not in _PLACEHOLDER_NAMES


def _identity_fingerprint(
    business_name: str,
    phone: str,
    address: str,
) -> str | None:
    parts = [
        _clean(business_name).casefold(),
        _phone_digits(phone),
        " ".join(_clean(address).casefold().split()),
    ]
    if not any(parts):
        return None
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def parse_legacy_lane_notes(notes: str) -> dict[str, Any]:
    raw = _clean(notes)
    match = _NOTE_RE.match(raw)
    if not match:
        return {
            "parsed": False,
            "parse_reason": "legacy_note_shape_unrecognised",
            "raw_notes": raw,
        }

    source_name, email, phone, metro, state, details = (
        _clean(value) for value in match.groups()
    )
    permit_match = _PERMIT_RE.search(details)
    permit_number = _clean(permit_match.group(1)) if permit_match else ""
    permit_issued_date = _clean(permit_match.group(2)) if permit_match else ""

    address_match = _ADDRESS_RE.search(details)
    address = _clean(address_match.group(1)) if address_match else ""
    if address:
        address = re.split(r"\s+lead_ref=", address, maxsplit=1)[0].strip()

    bbl_match = _BBL_RE.search(details)
    lead_ref_match = _LEAD_REF_RE.search(details)
    business_name = _NYC_BOROUGH_SUFFIX_RE.sub("", source_name).strip()

    identity_recoverable = bool(
        _meaningful_name(business_name)
        and (_phone_digits(phone) or address)
    )

    metro_upper = metro.upper()
    if metro_upper == "NYC":
        source_system = "nyc_dob_permits"
    elif metro_upper == "CHI":
        source_system = "chicago_permits_legacy"
    elif metro_upper == "LAX":
        source_system = "los_angeles_permits_legacy"
    else:
        source_system = "legacy_permit_unknown"

    return {
        "parsed": True,
        "source_name": source_name,
        "business_name": business_name,
        "email": email,
        "phone": phone,
        "phone_digits": _phone_digits(phone),
        "metro": metro,
        "state": state,
        "details": details,
        "address": address,
        "permit_number": permit_number,
        "permit_issued_date": permit_issued_date,
        "bbl": _clean(bbl_match.group(1)) if bbl_match else None,
        "lead_ref": _clean(lead_ref_match.group(1)) if lead_ref_match else None,
        "source_system": source_system,
        "permit_evidence_present": bool(permit_number),
        "identity_recoverable": identity_recoverable,
        "routing_only": not identity_recoverable,
        "identity_fingerprint": _identity_fingerprint(
            business_name if _meaningful_name(business_name) else "",
            phone,
            address,
        ),
        "raw_notes": raw,
    }


def dedupe_legacy_lane_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        prospect_id = _clean(raw.get("prospect_id"))
        if not prospect_id:
            continue
        grouped.setdefault(prospect_id, []).append(dict(raw))

    deduped: list[dict[str, Any]] = []
    for prospect_id, group in grouped.items():
        group.sort(
            key=lambda row: (
                _clean(row.get("created_at")),
                int(row.get("id") or 0),
            ),
            reverse=True,
        )
        representative = dict(group[0])
        representative["legacy_lane_row_count"] = len(group)
        representative["legacy_lane_ids"] = sorted({
            _clean(row.get("lane_id"))
            for row in group
            if _clean(row.get("lane_id"))
        })
        representative["dedupe_status"] = (
            "DUPLICATE_LANE_ROWS_COLLAPSED"
            if len(group) > 1
            else "UNIQUE_LEGACY_ID"
        )
        deduped.append(representative)

    deduped.sort(
        key=lambda row: (
            _clean(row.get("created_at")),
            _clean(row.get("prospect_id")),
        )
    )
    return deduped


def _permit_chunks(values: Iterable[str], size: int = 40) -> Iterable[list[str]]:
    cleaned = []
    seen = set()
    for value in values:
        permit = _clean(value)
        if not permit or not re.fullmatch(r"[A-Za-z0-9-]+", permit):
            continue
        if permit in seen:
            continue
        seen.add(permit)
        cleaned.append(permit)
    for start in range(0, len(cleaned), size):
        yield cleaned[start:start + size]


def revalidate_nyc_permits(
    permit_numbers: Iterable[str],
    *,
    timeout: float = 12.0,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    observed_at = _now()

    for chunk in _permit_chunks(permit_numbers):
        quoted = ",".join("'" + value.replace("'", "''") + "'" for value in chunk)
        try:
            response = requests.get(
                NYC_PERMIT_URL,
                params={
                    "$where": f"job__ in({quoted})",
                    "$limit": max(50, len(chunk) * 3),
                },
                timeout=timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(f"http_{response.status_code}")
            payload = response.json()
            rows = payload if isinstance(payload, list) else []
        except Exception as exc:
            for permit in chunk:
                results[permit] = {
                    "validation_state": "SOURCE_ERROR",
                    "validation_reason": type(exc).__name__,
                    "source_system": "nyc_dob_permits",
                    "source_url": NYC_PERMIT_URL,
                    "source_observed_at": observed_at,
                    "source_freshness": "UNKNOWN",
                }
            continue

        by_job: dict[str, list[dict[str, Any]]] = {}
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            job = _clean(raw.get("job__"))
            if job:
                by_job.setdefault(job, []).append(dict(raw))

        for permit in chunk:
            matches = by_job.get(permit) or []
            if matches:
                latest = matches[0]
                results[permit] = {
                    "validation_state": "VERIFIED_CURRENT",
                    "validation_reason": "current_public_source_match",
                    "source_system": "nyc_dob_permits",
                    "source_url": NYC_PERMIT_URL,
                    "source_observed_at": observed_at,
                    "source_freshness": "SOURCE_REVALIDATED_CURRENT",
                    "source_record_count": len(matches),
                    "matched_permit_number": permit,
                    "matched_run_date": _clean(latest.get("dobrundate")) or None,
                    "matched_permit_status": _clean(
                        latest.get("permit_status")
                    ) or None,
                }
            else:
                results[permit] = {
                    "validation_state": "NOT_FOUND",
                    "validation_reason": "no_current_public_source_match",
                    "source_system": "nyc_dob_permits",
                    "source_url": NYC_PERMIT_URL,
                    "source_observed_at": observed_at,
                    "source_freshness": "NOT_CONFIRMED",
                    "source_record_count": 0,
                }

    return results


def _pending_validation(parsed: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "validation_state": "REVALIDATION_PENDING",
        "validation_reason": "source_adapter_not_available",
        "source_system": parsed.get("source_system"),
        "source_observed_at": None,
        "source_freshness": "UNKNOWN",
    }


def classify_recovery(
    parsed: Mapping[str, Any],
    validation: Mapping[str, Any],
    *,
    canonical_identity_match: bool = False,
) -> tuple[str, str]:
    if parsed.get("parsed") is not True:
        return "REJECT", "REJECTED"
    if parsed.get("identity_recoverable") is not True:
        return "REJECT", "REJECTED"
    if not parsed.get("permit_number"):
        return "ARCHIVE", "RECOVERED_EVIDENCE"

    state = _clean(validation.get("validation_state"))
    if state == "VERIFIED_CURRENT":
        if canonical_identity_match:
            return "MERGE", "VERIFIED_CURRENT"
        return "REUSE", "VERIFIED_CURRENT"
    if state == "NOT_FOUND":
        return "ARCHIVE", "REVALIDATION_FAILED"
    if state in {"SOURCE_ERROR", "REVALIDATION_PENDING"}:
        return "MODERNIZE", "REVALIDATION_PENDING"
    return "MODERNIZE", "REVALIDATION_PENDING"


def build_recovery_observer(
    rows: Iterable[Mapping[str, Any]],
    *,
    batch_size: int = 100,
    nyc_validation: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    batch_size = max(1, min(int(batch_size), MAX_BATCH_SIZE))
    deduped = dedupe_legacy_lane_rows(rows)[:batch_size]
    parsed_rows = [
        (row, parse_legacy_lane_notes(_clean(row.get("notes"))))
        for row in deduped
    ]

    if nyc_validation is None:
        nyc_validation = revalidate_nyc_permits(
            parsed.get("permit_number")
            for _, parsed in parsed_rows
            if parsed.get("parsed") is True
            and _clean(parsed.get("metro")).upper() == "NYC"
            and parsed.get("permit_number")
        )

    recovered: list[dict[str, Any]] = []
    classifications: dict[str, int] = {}
    states: dict[str, int] = {}

    for row, parsed in parsed_rows:
        permit_number = _clean(parsed.get("permit_number"))
        if (
            parsed.get("parsed") is True
            and _clean(parsed.get("metro")).upper() == "NYC"
            and permit_number
        ):
            validation = dict(
                nyc_validation.get(permit_number)
                or {
                    "validation_state": "SOURCE_ERROR",
                    "validation_reason": "validation_result_missing",
                    "source_system": "nyc_dob_permits",
                    "source_freshness": "UNKNOWN",
                }
            )
        elif parsed.get("parsed") is True and permit_number:
            validation = _pending_validation(parsed)
        else:
            validation = {
                "validation_state": "NOT_APPLICABLE",
                "validation_reason": "permit_evidence_missing_or_unparsed",
                "source_system": parsed.get("source_system"),
                "source_freshness": "UNKNOWN",
            }

        recovery_class, recovery_state = classify_recovery(
            parsed,
            validation,
            canonical_identity_match=False,
        )
        classifications[recovery_class] = (
            classifications.get(recovery_class, 0) + 1
        )
        states[recovery_state] = states.get(recovery_state, 0) + 1

        recovered.append({
            "legacy_prospect_id": _clean(row.get("prospect_id")),
            "legacy_lane_ids": list(row.get("legacy_lane_ids") or []),
            "legacy_lane_row_count": int(
                row.get("legacy_lane_row_count") or 1
            ),
            "dedupe_status": row.get("dedupe_status"),
            "original_evidence": {
                "status": row.get("status"),
                "niche": row.get("niche"),
                "metro": row.get("metro"),
                "notes": row.get("notes"),
                "created_at": row.get("created_at"),
            },
            "historical_omega": {
                "score": row.get("omega_score"),
                "tier": row.get("omega_tier"),
                "historical_only": True,
                "current_truth": False,
            },
            "recovered_fields": {
                key: parsed.get(key)
                for key in (
                    "business_name",
                    "source_name",
                    "email",
                    "phone",
                    "metro",
                    "state",
                    "address",
                    "permit_number",
                    "permit_issued_date",
                    "bbl",
                    "lead_ref",
                    "source_system",
                    "identity_fingerprint",
                )
            },
            "identity_recoverable": bool(
                parsed.get("identity_recoverable")
            ),
            "parse_state": (
                "PARSED" if parsed.get("parsed") is True else "UNPARSED"
            ),
            "validation": validation,
            "source_freshness": validation.get("source_freshness"),
            "current_identity_match_state": "UNKNOWN_NOT_CHECKED",
            "canonical_prospect_id": None,
            "canonical_promotion_performed": False,
            "recovery_classification": recovery_class,
            "recovery_state": recovery_state,
            "commercial_ready": False,
            "allocated": False,
            "delivered": False,
            "outreach_authorized": False,
        })

    return {
        "schema_version": "empire.legacy-permit-recovery-observer.v1",
        "generated_at": _now(),
        "mode": "OBSERVE",
        "input_row_count": len(list(rows)) if isinstance(rows, list) else None,
        "deduped_candidate_count": len(deduped),
        "processed_count": len(recovered),
        "classification_counts": dict(sorted(classifications.items())),
        "recovery_state_counts": dict(sorted(states.items())),
        "records": recovered,
        "historical_omega_is_current_truth": False,
        "database_write_performed": False,
        "canonical_promotion_performed": False,
        "outbound_sent": False,
        "commercial_terms_created": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def fetch_legacy_permit_rows(
    *,
    batch_size: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int, int]:
    batch_size = max(100, min(int(batch_size), MAX_BATCH_SIZE))
    offset = max(0, int(offset))
    scan_limit = min(MAX_SCAN_ROWS, batch_size * 5)
    params = urllib.parse.urlencode({
        "select": (
            "id,lane_id,prospect_id,status,omega_score,omega_tier,"
            "notes,created_at,buyer_id,niche,metro"
        ),
        "prospect_id": "like.prospect_*",
        "notes": "ilike.*permit*",
        "order": "created_at.asc,id.asc",
        "limit": str(scan_limit),
        "offset": str(offset),
    })
    rows = request_json("GET", f"/rest/v1/lane_leads?{params}") or []
    if not isinstance(rows, list):
        rows = []
    next_offset = offset + len(rows) if len(rows) == scan_limit else 0
    return [dict(row) for row in rows if isinstance(row, Mapping)], next_offset, scan_limit


def _previous_next_offset(path: Path) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, Mapping):
        return 0
    try:
        return max(0, int(payload.get("next_offset") or 0))
    except (TypeError, ValueError):
        return 0


def refresh_legacy_permit_recovery_observer(
    repo_root: str | Path,
    *,
    batch_size: int = 100,
    offset: int | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    output_path = root / OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if offset is None:
        offset = _previous_next_offset(output_path)

    rows, next_offset, scan_limit = fetch_legacy_permit_rows(
        batch_size=batch_size,
        offset=offset,
    )
    if not rows and offset:
        offset = 0
        rows, next_offset, scan_limit = fetch_legacy_permit_rows(
            batch_size=batch_size,
            offset=0,
        )

    payload = build_recovery_observer(
        rows,
        batch_size=max(100, min(int(batch_size), MAX_BATCH_SIZE)),
    )
    payload.update({
        "source_store": "public.lane_leads",
        "scan_offset": offset,
        "scan_limit": scan_limit,
        "scanned_row_count": len(rows),
        "next_offset": next_offset,
        "canonical_store": "supabase",
        "promotion_policy": "NO_PROMOTION_OBSERVE_ONLY",
    })

    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(output_path)
    return payload
