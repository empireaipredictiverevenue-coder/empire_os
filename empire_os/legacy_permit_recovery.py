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
from empire_os.prospect_ingest import match_existing_prospect


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

_PLACEHOLDER_NAME_KEYS = {
    "",
    "na",
    "none",
    "unknown",
    "notavailable",
    "notapplicable",
    "owner",
    "ownerself",
    "ownerasself",
    "self",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _phone_digits(value: str) -> str:
    return "".join(char for char in _clean(value) if char.isdigit())


def _placeholder_name_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        _clean(value).casefold(),
    )


def _meaningful_name(value: str) -> bool:
    key = _placeholder_name_key(value)
    if key in _PLACEHOLDER_NAME_KEYS:
        return False
    if key.isdigit():
        return False
    return bool(key)


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

    metro_upper = metro.upper()
    if metro_upper == "NYC":
        source_system = "nyc_dob_permits"
        legacy_name_role = "property_owner"
        legacy_phone_role = "permittee_contact"
        # The old NYC crawler paired owner name with permittee phone.
        # Owner identity therefore requires owner name + project address;
        # permittee phone cannot make the owner identity recoverable.
        identity_recoverable = bool(
            _meaningful_name(business_name) and address
        )
        fingerprint_phone = ""
    elif metro_upper == "CHI":
        source_system = "chicago_permits_legacy"
        legacy_name_role = "legacy_subject"
        legacy_phone_role = "unknown"
        identity_recoverable = bool(
            _meaningful_name(business_name)
            and (_phone_digits(phone) or address)
        )
        fingerprint_phone = phone
    elif metro_upper == "LAX":
        source_system = "los_angeles_permits_legacy"
        legacy_name_role = "legacy_subject"
        legacy_phone_role = "unknown"
        identity_recoverable = bool(
            _meaningful_name(business_name)
            and (_phone_digits(phone) or address)
        )
        fingerprint_phone = phone
    else:
        source_system = "legacy_permit_unknown"
        legacy_name_role = "legacy_subject"
        legacy_phone_role = "unknown"
        identity_recoverable = bool(
            _meaningful_name(business_name)
            and (_phone_digits(phone) or address)
        )
        fingerprint_phone = phone

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
        "legacy_name_role": legacy_name_role,
        "legacy_phone_role": legacy_phone_role,
        "permit_evidence_present": bool(permit_number),
        "identity_recoverable": identity_recoverable,
        "routing_only": not identity_recoverable,
        "identity_fingerprint": _identity_fingerprint(
            business_name if _meaningful_name(business_name) else "",
            fingerprint_phone,
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


def _source_identity_name(
    row: Mapping[str, Any],
    business_key: str,
    first_key: str,
    last_key: str,
) -> str:
    business = _clean(row.get(business_key))
    if business:
        return business
    return " ".join(
        part
        for part in (
            _clean(row.get(first_key)),
            _clean(row.get(last_key)),
        )
        if part
    ).strip()


def _unique_text(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean(value)
        key = _identity_name_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def source_owner_identity_state(
    parsed: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> str:
    if _clean(parsed.get("source_system")) != "nyc_dob_permits":
        return "NOT_AVAILABLE"
    if _clean(validation.get("validation_state")) != "VERIFIED_CURRENT":
        return "NOT_AVAILABLE"

    legacy_name = _identity_name_key(parsed.get("business_name"))
    owner_names = [
        _identity_name_key(value)
        for value in (validation.get("source_owner_names") or [])
        if _identity_name_key(value)
    ]
    if not legacy_name or not owner_names:
        return "UNKNOWN"
    if legacy_name in owner_names:
        return "MATCHED"
    return "MISMATCH"


def source_permittee_phone_state(
    parsed: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> str:
    if _clean(parsed.get("legacy_phone_role")) != "permittee_contact":
        return "NOT_AVAILABLE"
    legacy_phone = _phone_digits(_clean(parsed.get("phone")))
    if not legacy_phone:
        return "NOT_AVAILABLE"
    permittees = validation.get("source_permittees") or []
    phones = {
        _phone_digits(_clean(item.get("phone")))
        for item in permittees
        if isinstance(item, Mapping)
        and _phone_digits(_clean(item.get("phone")))
    }
    if not phones:
        return "UNKNOWN"
    if legacy_phone in phones:
        return "SOURCE_CONFIRMED"
    return "MISMATCH"


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
                owner_names = _unique_text(
                    _source_identity_name(
                        item,
                        "owner_s_business_name",
                        "owner_s_first_name",
                        "owner_s_last_name",
                    )
                    for item in matches
                )
                permittees_by_key: dict[tuple[str, str], dict[str, Any]] = {}
                for item in matches:
                    permittee_name = _source_identity_name(
                        item,
                        "permittee_s_business_name",
                        "permittee_s_first_name",
                        "permittee_s_last_name",
                    )
                    permittee_phone = _clean(
                        item.get("permittee_s_phone__")
                    )
                    key = (
                        _identity_name_key(permittee_name),
                        _phone_digits(permittee_phone),
                    )
                    if not any(key):
                        continue
                    permittees_by_key.setdefault(
                        key,
                        {
                            "business_name": _clean(
                                item.get("permittee_s_business_name")
                            ) or None,
                            "name": permittee_name or None,
                            "phone": permittee_phone or None,
                            "license_type": _clean(
                                item.get("permittee_s_license_type")
                            ) or None,
                            "license_number": _clean(
                                item.get("permittee_s_license__")
                            ) or None,
                        },
                    )
                source_addresses = _unique_text(
                    " ".join(
                        part
                        for part in (
                            _clean(item.get("house__")),
                            _clean(item.get("street_name")),
                            _clean(item.get("borough")),
                        )
                        if part
                    )
                    for item in matches
                )
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
                    "source_owner_names": owner_names,
                    "source_permittees": list(permittees_by_key.values()),
                    "source_addresses": source_addresses,
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


def fetch_canonical_prospects_by_metro(
    metros: Iterable[str],
    *,
    page_size: int = 1000,
    max_rows_per_metro: int = 50000,
) -> dict[str, dict[str, Any]]:
    """Read canonical prospects once per metro for bounded identity matching."""
    page_size = max(1, min(int(page_size), 1000))
    max_rows_per_metro = max(page_size, int(max_rows_per_metro))
    result: dict[str, dict[str, Any]] = {}

    for raw_metro in metros:
        metro = _clean(raw_metro).casefold()
        if not metro or metro in result:
            continue

        rows: list[dict[str, Any]] = []
        offset = 0
        truncated = False

        while offset < max_rows_per_metro:
            limit = min(page_size, max_rows_per_metro - offset)
            params = urllib.parse.urlencode({
                "select": (
                    "id,business_name,phone,metro,niche,website,address,"
                    "status,contact_source,created_at"
                ),
                "metro": f"ilike.{metro}",
                "order": "created_at.asc",
                "limit": str(limit),
                "offset": str(offset),
            })
            batch = request_json(
                "GET",
                f"/rest/v1/prospects?{params}",
            ) or []
            if not isinstance(batch, list):
                batch = []

            rows.extend(
                dict(row)
                for row in batch
                if isinstance(row, Mapping)
            )

            if len(batch) < limit:
                break

            offset += len(batch)
        else:
            truncated = True

        if len(rows) >= max_rows_per_metro:
            truncated = True

        result[metro] = {
            "rows": rows,
            "rows_scanned": len(rows),
            "truncated": truncated,
        }

    return result


def _identity_name_key(value: Any) -> str:
    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            _clean(value).casefold(),
        ).split()
    )


def match_canonical_identity(
    parsed: Mapping[str, Any],
    canonical_prospects_by_metro: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Match the legacy subject identity, never a role-mismatched contact."""
    if parsed.get("parsed") is not True:
        return {
            "match_state": "NOT_ELIGIBLE",
            "match_reason": "legacy_note_unparsed",
            "canonical_prospect_id": None,
            "match_method": None,
            "rows_scanned": 0,
        }
    if parsed.get("identity_recoverable") is not True:
        return {
            "match_state": "NOT_ELIGIBLE",
            "match_reason": "identity_not_recoverable",
            "canonical_prospect_id": None,
            "match_method": None,
            "rows_scanned": 0,
        }

    metro = _clean(parsed.get("metro")).casefold()
    bucket = canonical_prospects_by_metro.get(metro) or {}
    rows = bucket.get("rows") or []
    rows_scanned = int(bucket.get("rows_scanned") or len(rows))

    if bucket.get("truncated") is True:
        return {
            "match_state": "AMBIGUOUS",
            "match_reason": "canonical_lookup_truncated",
            "canonical_prospect_id": None,
            "match_method": None,
            "rows_scanned": rows_scanned,
        }

    lookup = match_existing_prospect(
        {
            "prospect": {
                "business_name": parsed.get("business_name"),
                "metro": parsed.get("metro"),
                "phone": (
                    ""
                    if parsed.get("legacy_phone_role") == "permittee_contact"
                    else parsed.get("phone")
                ),
            }
        },
        [
            dict(row)
            for row in rows
            if isinstance(row, Mapping)
        ],
    )

    decision = _clean(lookup.get("decision"))
    reason = _clean(lookup.get("reason"))
    prospect = lookup.get("prospect")

    if decision == "matched" and isinstance(prospect, Mapping):
        canonical_id = _clean(prospect.get("id")) or None

        # Permit phone fields can belong to contractors, managers, filing
        # agents, or other shared contacts. Phone-only equality is therefore
        # evidence for review, not sufficient proof that the permit owner and
        # canonical business are the same entity.
        if reason == "exact_phone":
            legacy_name = _identity_name_key(parsed.get("business_name"))
            canonical_name = _identity_name_key(
                prospect.get("business_name")
            )
            legacy_metro = _clean(parsed.get("metro")).casefold()
            canonical_metro = _clean(prospect.get("metro")).casefold()

            if (
                legacy_name
                and canonical_name
                and legacy_name == canonical_name
                and legacy_metro
                and legacy_metro == canonical_metro
            ):
                return {
                    "match_state": "MATCHED",
                    "match_reason": "exact_phone_name_metro",
                    "canonical_prospect_id": canonical_id,
                    "match_method": "exact_phone_name_metro",
                    "rows_scanned": rows_scanned,
                }

            return {
                "match_state": "PHONE_ONLY_REVIEW",
                "match_reason": "exact_phone_without_name_corroboration",
                "canonical_prospect_id": canonical_id,
                "match_method": "exact_phone_review_only",
                "rows_scanned": rows_scanned,
                "legacy_business_name": parsed.get("business_name"),
                "canonical_business_name": prospect.get("business_name"),
            }

        return {
            "match_state": "MATCHED",
            "match_reason": reason,
            "canonical_prospect_id": canonical_id,
            "match_method": reason,
            "rows_scanned": rows_scanned,
        }
    if decision == "ambiguous":
        return {
            "match_state": "AMBIGUOUS",
            "match_reason": reason,
            "canonical_prospect_id": None,
            "match_method": None,
            "rows_scanned": rows_scanned,
        }

    return {
        "match_state": "NO_MATCH",
        "match_reason": reason or "no_strong_identity_match",
        "canonical_prospect_id": None,
        "match_method": None,
        "rows_scanned": rows_scanned,
    }


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
    canonical_identity_state: str = "NO_MATCH",
    source_identity_state: str = "NOT_AVAILABLE",
) -> tuple[str, str]:
    if parsed.get("parsed") is not True:
        return "REJECT", "REJECTED"
    if parsed.get("identity_recoverable") is not True:
        return "REJECT", "REJECTED"
    if not parsed.get("permit_number"):
        return "ARCHIVE", "RECOVERED_EVIDENCE"

    state = _clean(validation.get("validation_state"))
    identity_state = _clean(canonical_identity_state).upper()

    if state == "VERIFIED_CURRENT":
        source_state = _clean(source_identity_state).upper()
        if (
            _clean(parsed.get("source_system")) == "nyc_dob_permits"
            and source_state != "MATCHED"
        ):
            return "MODERNIZE", "IDENTITY_REVIEW_REQUIRED"
        if identity_state == "MATCHED":
            return "MERGE", "VERIFIED_CURRENT"
        if identity_state in {"AMBIGUOUS", "PHONE_ONLY_REVIEW"}:
            return "MODERNIZE", "IDENTITY_REVIEW_REQUIRED"
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
    canonical_prospects_by_metro: (
        Mapping[str, Mapping[str, Any]] | None
    ) = None,
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

    if canonical_prospects_by_metro is None:
        canonical_prospects_by_metro = {}

    recovered: list[dict[str, Any]] = []
    classifications: dict[str, int] = {}
    states: dict[str, int] = {}
    identity_states: dict[str, int] = {}
    source_identity_states: dict[str, int] = {}
    permittee_phone_states: dict[str, int] = {}

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

        source_identity = source_owner_identity_state(
            parsed,
            validation,
        )
        source_identity_states[source_identity] = (
            source_identity_states.get(source_identity, 0) + 1
        )
        permittee_phone_state = source_permittee_phone_state(
            parsed,
            validation,
        )
        permittee_phone_states[permittee_phone_state] = (
            permittee_phone_states.get(permittee_phone_state, 0) + 1
        )

        identity_match = match_canonical_identity(
            parsed,
            canonical_prospects_by_metro,
        )
        identity_state = _clean(identity_match.get("match_state"))
        identity_states[identity_state] = (
            identity_states.get(identity_state, 0) + 1
        )

        recovery_class, recovery_state = classify_recovery(
            parsed,
            validation,
            canonical_identity_state=identity_state,
            source_identity_state=source_identity,
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
                    "legacy_name_role",
                    "legacy_phone_role",
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
            "source_owner_identity_state": source_identity,
            "source_permittee_phone_state": permittee_phone_state,
            "current_identity_match_state": identity_state,
            "canonical_match_reason": identity_match.get("match_reason"),
            "canonical_match_method": identity_match.get("match_method"),
            "canonical_lookup_rows_scanned": identity_match.get(
                "rows_scanned"
            ),
            "canonical_prospect_id": identity_match.get(
                "canonical_prospect_id"
            ),
            "canonical_promotion_performed": False,
            "recovery_classification": recovery_class,
            "recovery_state": recovery_state,
            "commercial_ready": False,
            "allocated": False,
            "delivered": False,
            "outreach_authorized": False,
        })

    return {
        "schema_version": "empire.legacy-permit-recovery-observer.v3",
        "generated_at": _now(),
        "mode": "OBSERVE",
        "input_row_count": len(list(rows)) if isinstance(rows, list) else None,
        "deduped_candidate_count": len(deduped),
        "processed_count": len(recovered),
        "classification_counts": dict(sorted(classifications.items())),
        "recovery_state_counts": dict(sorted(states.items())),
        "identity_match_counts": dict(sorted(identity_states.items())),
        "source_owner_identity_counts": dict(
            sorted(source_identity_states.items())
        ),
        "source_permittee_phone_counts": dict(
            sorted(permittee_phone_states.items())
        ),
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
    """Fetch a gap-free bounded batch of unique legacy prospect groups.

    lane_leads contains several lane rows per legacy prospect. Read rows in
    prospect_id order so duplicates stay contiguous, then stop immediately
    before the first row belonging to the next unique prospect after the
    requested batch size. The returned next_offset therefore never skips an
    unprocessed raw row.
    """
    batch_size = max(100, min(int(batch_size), MAX_BATCH_SIZE))
    offset = max(0, int(offset))
    scan_budget = MAX_SCAN_ROWS
    page_size = min(500, scan_budget)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw_consumed = 0
    reached_end = False
    batch_complete = False

    while raw_consumed < scan_budget and not batch_complete:
        limit = min(page_size, scan_budget - raw_consumed)
        params = urllib.parse.urlencode({
            "select": (
                "id,lane_id,prospect_id,status,omega_score,omega_tier,"
                "notes,created_at,buyer_id,niche,metro"
            ),
            "prospect_id": "like.prospect_*",
            "notes": "ilike.*permit*",
            "order": "prospect_id.asc,created_at.asc,id.asc",
            "limit": str(limit),
            "offset": str(offset + raw_consumed),
        })
        batch = request_json(
            "GET",
            f"/rest/v1/lane_leads?{params}",
        ) or []
        if not isinstance(batch, list):
            batch = []

        if not batch:
            reached_end = True
            break

        for raw in batch:
            if not isinstance(raw, Mapping):
                raw_consumed += 1
                continue

            prospect_id = _clean(raw.get("prospect_id"))
            if (
                prospect_id
                and prospect_id not in seen
                and len(seen) >= batch_size
            ):
                batch_complete = True
                break

            rows.append(dict(raw))
            raw_consumed += 1
            if prospect_id:
                seen.add(prospect_id)

        if batch_complete:
            break

        if len(batch) < limit:
            reached_end = True
            break

    next_offset = 0 if reached_end else offset + raw_consumed
    return rows, next_offset, scan_budget

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

    bounded_batch_size = max(
        100,
        min(int(batch_size), MAX_BATCH_SIZE),
    )
    preview = dedupe_legacy_lane_rows(rows)[:bounded_batch_size]
    canonical_prospects_by_metro = fetch_canonical_prospects_by_metro(
        {
            parsed.get("metro")
            for parsed in (
                parse_legacy_lane_notes(_clean(row.get("notes")))
                for row in preview
            )
            if parsed.get("parsed") is True
            and parsed.get("identity_recoverable") is True
            and _clean(parsed.get("metro"))
        }
    )

    payload = build_recovery_observer(
        rows,
        batch_size=bounded_batch_size,
        canonical_prospects_by_metro=canonical_prospects_by_metro,
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
