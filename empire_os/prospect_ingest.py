"""
Canonical prospect-ingest preparation for Empire OS.

This module is deliberately side-effect free.

Responsibilities:
- normalize LeadCandidate-style input;
- preserve acquisition provenance;
- prepare fields compatible with canonical Supabase `prospects`;
- derive a stable acquisition fingerprint;
- NEVER treat a crawler/source URL as a verified business website.

Persistence and prospect/entity matching are handled separately.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


class ProspectIngestError(ValueError):
    """Candidate cannot safely enter canonical prospect ingest."""


def _text(value: Any) -> str:
    return " ".join(
        str(value or "").strip().split()
    )


def _key(value: Any) -> str:
    return _text(value).casefold()


def _phone(value: Any) -> str:
    digits = re.sub(
        r"\D+",
        "",
        str(value or ""),
    )

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    return digits


def _source_url(value: Any) -> str:
    raw = _text(value)

    if not raw:
        return ""

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    # Strip fragments only. Query parameters can be part of the
    # source record identity, e.g. public permit/job references.
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            parsed.query,
            "",
        )
    )


def acquisition_fingerprint(
    *,
    source: str,
    source_url: str,
    business_name: str,
    metro: str,
    phone: str,
) -> str:
    """
    Stable acquisition fingerprint.

    Priority is provenance. Phone/name/metro provide deterministic
    fallback material when a source does not expose a durable URL.

    This fingerprint is an ingest/idempotency aid, NOT proof that two
    businesses are the same canonical entity.
    """
    material = {
        "source": _key(source),
        "source_url": _source_url(source_url),
        "business_name": _key(business_name),
        "metro": _key(metro),
        "phone": _phone(phone),
    }

    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def prepare_candidate(candidate: Any) -> dict[str, Any]:
    """
    Convert a LeadCandidate-like object/dict into canonical ingest data.

    Returns:
        {
            "prospect": {...},
            "evidence": {...},
            "ingest_key": "...",
        }

    No database or network operations occur here.
    """
    if isinstance(candidate, dict):
        data = dict(candidate)
    else:
        fields = (
            "name",
            "email",
            "phone",
            "niche",
            "metro",
            "state",
            "details",
            "source",
            "lead_score",
            "url",
            "raw",
        )
        data = {
            field: getattr(candidate, field, None)
            for field in fields
        }

    business_name = _text(data.get("name"))
    niche = _key(data.get("niche"))
    metro = _key(data.get("metro"))

    if not business_name:
        raise ProspectIngestError(
            "candidate missing business name"
        )

    if not niche:
        raise ProspectIngestError(
            "candidate missing niche"
        )

    if not metro:
        raise ProspectIngestError(
            "candidate missing metro"
        )

    phone_raw = _text(data.get("phone"))
    phone_key = _phone(phone_raw)

    source = _key(data.get("source")) or "unknown"
    source_url = _source_url(data.get("url"))

    details = _text(data.get("details"))
    email = _text(data.get("email"))
    state = _text(data.get("state"))

    try:
        lead_score = int(
            data.get("lead_score")
            if data.get("lead_score") is not None
            else 50
        )
    except (TypeError, ValueError):
        lead_score = 50

    lead_score = max(
        0,
        min(100, lead_score),
    )

    ingest_key = acquisition_fingerprint(
        source=source,
        source_url=source_url,
        business_name=business_name,
        metro=metro,
        phone=phone_key,
    )

    prospect = {
        "business_name": business_name,
        "niche": niche,
        "metro": metro,
        "phone": phone_raw,
        "buy_signal_score": lead_score,
        "contact_source": source,
        "contacted_status": "not_contacted",
    }

    # Do not write empty values unnecessarily.
    prospect = {
        key: value
        for key, value in prospect.items()
        if value not in ("", None)
    }

    evidence = {
        "source": source,
        "source_url": source_url,
        "email": email,
        "state": state,
        "details": details,
        "raw": data.get("raw"),
    }

    # Deliberately absent:
    #   prospect["website"] = candidate.url
    #
    # `LeadCandidate.url` is provenance/source evidence. It may be a
    # permit record, court record, Reddit post, directory page, etc.
    # A business website must pass first-party identity verification
    # before it enters prospects.website.

    return {
        "prospect": prospect,
        "evidence": evidence,
        "ingest_key": ingest_key,
    }


def match_existing_prospect(
    prepared: dict[str, Any],
    existing_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Conservatively match prepared candidate identity to existing prospects.

    Matching hierarchy:
    1. exact normalized non-empty phone;
    2. exact normalized business name + metro.

    Multiple matches are ambiguous and MUST NOT auto-merge.

    Niche + metro alone is never identity proof.
    """
    prospect = prepared.get("prospect")

    if not isinstance(prospect, dict):
        raise ProspectIngestError(
            "prepared candidate missing prospect payload"
        )

    candidate_phone = _phone(
        prospect.get("phone")
    )

    if candidate_phone:
        phone_matches = [
            row
            for row in existing_rows
            if _phone(row.get("phone"))
            == candidate_phone
        ]

        if len(phone_matches) == 1:
            return {
                "decision": "matched",
                "reason": "exact_phone",
                "prospect": phone_matches[0],
            }

        if len(phone_matches) > 1:
            return {
                "decision": "ambiguous",
                "reason": "multiple_exact_phone_matches",
                "prospect": None,
            }

    candidate_name = _key(
        prospect.get("business_name")
    )

    candidate_metro = _key(
        prospect.get("metro")
    )

    name_metro_matches = [
        row
        for row in existing_rows
        if (
            candidate_name
            and candidate_metro
            and _key(row.get("business_name"))
            == candidate_name
            and _key(row.get("metro"))
            == candidate_metro
        )
    ]

    if len(name_metro_matches) == 1:
        return {
            "decision": "matched",
            "reason": "exact_name_metro",
            "prospect": name_metro_matches[0],
        }

    if len(name_metro_matches) > 1:
        return {
            "decision": "ambiguous",
            "reason": "multiple_exact_name_metro_matches",
            "prospect": None,
        }

    return {
        "decision": "new",
        "reason": "no_strong_identity_match",
        "prospect": None,
    }


def lookup_existing_prospect(
    prepared: dict[str, Any],
    reader,
    *,
    page_size: int = 1000,
    max_pages: int = 10,
) -> dict[str, Any]:
    """
    Read-only canonical prospect lookup.

    Fetches prospects only for the candidate metro, paginates deterministically,
    then applies match_existing_prospect() client-side.

    If the bounded lookup is exhausted before the metro is fully scanned,
    fail closed as ambiguous rather than incorrectly declaring a new prospect.

    `reader` signature:
        reader(path: str, params: dict[str, str]) -> list[dict]
    """
    prospect = prepared.get("prospect")

    if not isinstance(prospect, dict):
        raise ProspectIngestError(
            "prepared candidate missing prospect payload"
        )

    metro = _key(prospect.get("metro"))

    if not metro:
        raise ProspectIngestError(
            "prepared candidate missing metro"
        )

    if page_size < 1:
        raise ProspectIngestError(
            "page_size must be positive"
        )

    if max_pages < 1:
        raise ProspectIngestError(
            "max_pages must be positive"
        )

    rows: list[dict[str, Any]] = []
    pages = 0
    truncated = False

    for page in range(max_pages):
        offset = page * page_size

        batch = reader(
            "/rest/v1/prospects",
            {
                "select": (
                    "id,business_name,phone,metro,niche,"
                    "website,address,status,contact_source"
                ),
                "metro": "ilike." + metro,
                "order": "created_at.asc",
                "limit": str(page_size),
                "offset": str(offset),
            },
        )

        if not isinstance(batch, list):
            raise ProspectIngestError(
                "prospect lookup returned invalid response"
            )

        pages += 1
        rows.extend(
            row
            for row in batch
            if isinstance(row, dict)
        )

        if len(batch) < page_size:
            break
    else:
        # We consumed every permitted page. If the final page was full,
        # there may be additional rows we did not inspect.
        if batch and len(batch) >= page_size:
            truncated = True

    if truncated:
        return {
            "decision": "ambiguous",
            "reason": "prospect_lookup_truncated",
            "prospect": None,
            "rows_scanned": len(rows),
            "pages_scanned": pages,
        }

    result = match_existing_prospect(
        prepared,
        rows,
    )

    return {
        **result,
        "rows_scanned": len(rows),
        "pages_scanned": pages,
    }


def materialize_prospect(
    prepared: dict[str, Any],
    lookup_result: dict[str, Any],
    writer,
) -> dict[str, Any]:
    """
    Materialize a prepared prospect after conservative lookup.

    Existing or ambiguous identities are returned without writing.
    Only a lookup decision of ``new`` may reach the injected atomic writer.
    """
    prospect = prepared.get("prospect")
    evidence = prepared.get("evidence")
    ingest_key = prepared.get("ingest_key")

    if not isinstance(prospect, dict):
        raise ProspectIngestError(
            "prepared candidate missing prospect payload"
        )

    if not isinstance(evidence, dict):
        raise ProspectIngestError(
            "prepared candidate missing evidence payload"
        )

    if not isinstance(ingest_key, str) or not ingest_key:
        raise ProspectIngestError(
            "prepared candidate missing ingest key"
        )

    if not isinstance(lookup_result, dict):
        raise ProspectIngestError(
            "invalid prospect lookup result"
        )

    decision = lookup_result.get("decision")

    if decision in {"matched", "ambiguous"}:
        return dict(lookup_result)

    if decision != "new":
        raise ProspectIngestError(
            "invalid prospect lookup decision"
        )

    result = writer(
        {
            "prospect": dict(prospect),
            "evidence": dict(evidence),
            "ingest_key": ingest_key,
            "identity_keys": prospect_identity_keys(prepared),
        }
    )

    if not isinstance(result, dict):
        raise ProspectIngestError(
            "prospect writer returned invalid response"
        )

    return result



def prospect_identity_keys(
    prepared: dict[str, Any],
) -> list[str]:
    """
    Derive all strong deterministic identity keys available.

    Name + metro is always retained. When a normalized phone exists,
    phone + metro is added as an additional concurrency/idempotency claim.
    """
    prospect = prepared.get("prospect")

    if not isinstance(prospect, dict):
        raise ProspectIngestError(
            "prepared candidate missing prospect payload"
        )

    business_name = _key(prospect.get("business_name"))
    metro = _key(prospect.get("metro"))
    phone = _phone(prospect.get("phone"))

    if not business_name or not metro:
        raise ProspectIngestError(
            "prepared candidate missing strong identity"
        )

    keys: list[str] = []

    if phone:
        keys.append(f"phone_metro:{phone}|{metro}")

    keys.append(f"name_metro:{business_name}|{metro}")

    return keys
