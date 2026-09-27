"""Read-only parity audit between canonical prospects and legacy lead stores."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


Reader = Callable[[str, dict[str, str]], Any]


class LeadParityError(RuntimeError):
    """Parity inputs are invalid or unsafe to compare."""


@dataclass(frozen=True)
class Match:
    legacy_source: str
    legacy_id: str
    prospect_id: str | None
    method: str
    confidence: float
    mismatches: tuple[str, ...] = ()
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "legacy_source": self.legacy_source,
            "legacy_id": self.legacy_id,
            "prospect_id": self.prospect_id,
            "method": self.method,
            "confidence": self.confidence,
            "mismatches": list(self.mismatches),
            "reason": self.reason,
        }


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _identity_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _norm(row.get("business_name") or row.get("name")),
        _norm(row.get("niche")),
        _norm(row.get("metro")),
    )


def _external_ids(acquisition: dict[str, Any]) -> set[str]:
    evidence = acquisition.get("evidence")
    if not isinstance(evidence, dict):
        return set()

    raw = evidence.get("raw")
    values: set[str] = set()
    if isinstance(raw, dict):
        value = _norm(raw.get("external_lead_id"))
        if value:
            values.add(value)

    direct = _norm(evidence.get("external_lead_id"))
    if direct:
        values.add(direct)
    return values


def fetch_canonical_parity_inputs(
    reader: Reader,
    *,
    limit: int = 5000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 1 <= int(limit) <= 10000:
        raise ValueError("limit must be between 1 and 10000")

    prospects = reader(
        "/rest/v1/prospects",
        {
            "select": (
                "id,business_name,niche,metro,phone,website,status,"
                "created_at"
            ),
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    acquisitions = reader(
        "/rest/v1/prospect_acquisitions",
        {
            "select": (
                "id,prospect_id,ingest_key,identity_keys,source,"
                "source_url,evidence,created_at"
            ),
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )

    if not isinstance(prospects, list) or any(
        not isinstance(row, dict) for row in prospects
    ):
        raise LeadParityError("invalid canonical prospects payload")
    if not isinstance(acquisitions, list) or any(
        not isinstance(row, dict) for row in acquisitions
    ):
        raise LeadParityError("invalid acquisition payload")

    return list(prospects), list(acquisitions)


def _mismatches(
    legacy: dict[str, Any],
    canonical: dict[str, Any],
) -> tuple[str, ...]:
    fields = ("business_name", "niche", "metro", "phone")
    diffs: list[str] = []
    for field in fields:
        legacy_value = _norm(legacy.get(field))
        canonical_value = _norm(canonical.get(field))
        if (
            legacy_value
            and canonical_value
            and legacy_value != canonical_value
        ):
            diffs.append(field)
    return tuple(diffs)


def build_parity_report(
    *,
    prospects: list[dict[str, Any]],
    acquisitions: list[dict[str, Any]],
    crm_leads: list[dict[str, Any]],
    lane_leads: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical: dict[str, dict[str, Any]] = {}
    identity_index: dict[
        tuple[str, str, str],
        list[str],
    ] = {}
    external_index: dict[str, set[str]] = {}

    for prospect in prospects:
        prospect_id = _norm(prospect.get("id"))
        if not prospect_id:
            raise LeadParityError("canonical prospect missing id")
        if prospect_id in canonical:
            raise LeadParityError("duplicate canonical prospect id")
        canonical[prospect_id] = prospect

        key = _identity_key(prospect)
        if all(key):
            identity_index.setdefault(key, []).append(prospect_id)

    for acquisition in acquisitions:
        prospect_id = _norm(acquisition.get("prospect_id"))
        if not prospect_id:
            raise LeadParityError("acquisition missing prospect_id")
        if prospect_id not in canonical:
            raise LeadParityError(
                "acquisition references unknown prospect"
            )
        for external_id in _external_ids(acquisition):
            external_index.setdefault(
                external_id,
                set(),
            ).add(prospect_id)

    matched_prospect_ids: set[str] = set()
    ambiguous_identity = 0
    ambiguous_external = 0

    def match_one(
        row: dict[str, Any],
        *,
        source: str,
        id_field: str,
    ) -> Match:
        nonlocal ambiguous_identity, ambiguous_external

        legacy_id = _norm(row.get(id_field))
        if not legacy_id:
            return Match(
                source,
                "",
                None,
                "unmatched",
                0.0,
                reason="legacy_id_missing",
            )

        if legacy_id in canonical:
            prospect = canonical[legacy_id]
            matched_prospect_ids.add(legacy_id)
            return Match(
                source,
                legacy_id,
                legacy_id,
                "canonical_uuid",
                1.0,
                _mismatches(row, prospect),
            )

        external_matches = external_index.get(legacy_id, set())
        if len(external_matches) == 1:
            prospect_id = next(iter(external_matches))
            matched_prospect_ids.add(prospect_id)
            return Match(
                source,
                legacy_id,
                prospect_id,
                "acquisition_external_id",
                0.95,
                _mismatches(row, canonical[prospect_id]),
            )
        if len(external_matches) > 1:
            ambiguous_external += 1
            return Match(
                source,
                legacy_id,
                None,
                "ambiguous",
                0.0,
                reason="external_id_maps_to_multiple_prospects",
            )

        key = _identity_key(row)
        candidates = identity_index.get(key, []) if all(key) else []
        if len(candidates) == 1:
            prospect_id = candidates[0]
            matched_prospect_ids.add(prospect_id)
            return Match(
                source,
                legacy_id,
                prospect_id,
                "identity_diagnostic",
                0.70,
                _mismatches(row, canonical[prospect_id]),
            )
        if len(candidates) > 1:
            ambiguous_identity += 1
            return Match(
                source,
                legacy_id,
                None,
                "ambiguous",
                0.0,
                reason="identity_maps_to_multiple_prospects",
            )

        return Match(
            source,
            legacy_id,
            None,
            "unmatched",
            0.0,
            reason="no_canonical_match",
        )

    crm_matches = [
        match_one(
            row,
            source="crm_leads",
            id_field="lead_uid",
        )
        for row in crm_leads
    ]
    lane_matches = [
        match_one(
            row,
            source="lane_leads",
            id_field="prospect_id",
        )
        for row in lane_leads
    ]

    all_matches = crm_matches + lane_matches
    unmatched = sum(
        1 for match in all_matches if match.method == "unmatched"
    )
    ambiguous = sum(
        1 for match in all_matches if match.method == "ambiguous"
    )
    mismatched = sum(
        1 for match in all_matches if match.mismatches
    )

    return {
        "schema_version": "lead_parity.v1",
        "read_only": True,
        "canonical_total": len(canonical),
        "legacy_crm_total": len(crm_leads),
        "legacy_lane_total": len(lane_leads),
        "matched_legacy_rows": sum(
            1
            for match in all_matches
            if match.prospect_id is not None
        ),
        "unmatched_legacy_rows": unmatched,
        "ambiguous_legacy_rows": ambiguous,
        "field_mismatch_rows": mismatched,
        "canonical_without_legacy": sorted(
            set(canonical) - matched_prospect_ids
        ),
        "ambiguous_identity_rows": ambiguous_identity,
        "ambiguous_external_id_rows": ambiguous_external,
        "crm_matches": [match.as_dict() for match in crm_matches],
        "lane_matches": [match.as_dict() for match in lane_matches],
    }
