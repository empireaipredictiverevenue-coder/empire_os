"""Governed Phase 13 Revenue Exchange observation ingestion."""
from __future__ import annotations

from dataclasses import dataclass
import csv
from decimal import Decimal
import hashlib
import io
import json
import re
from typing import Any, Mapping

from empire_os.revenue_exchange import (
    ExchangeSnapshot,
    normalise_exchange_snapshot,
)


@dataclass(frozen=True)
class CanonicalExchangeObservation:
    observation_key: str
    snapshot: ExchangeSnapshot
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.observation_key or "").strip():
            raise ValueError("observation_key required")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")


def build_exchange_observation(
    *,
    observation_key: str,
    row: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
) -> CanonicalExchangeObservation:
    snapshot = normalise_exchange_snapshot(row)
    item = CanonicalExchangeObservation(
        observation_key=str(observation_key).strip(),
        snapshot=snapshot,
        evidence=dict(evidence or {}),
    )
    item.validate()
    return item


_COVERAGE_FIELDS = ("category", "service", "zipcode", "city", "state", "expected_value")


def prepare_coverage_export(
    content: bytes, *, source_ref: str, program_ref: str,
) -> dict[str, Any]:
    """Prepare unverified affiliate coverage evidence, never an ingest request.

    Exactness means equality of the six original decoded CSV fields (no trimming
    or numeric coercion). Numeric equivalence is used only for conflict reports.
    Artifact-scoped keys support repeat preparation, not cross-export dedupe.
    No observed counts or expected values enter canonical snapshot price fields.
    """
    for label, value in (("source_ref", source_ref), ("program_ref", program_ref)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} required")
    if not isinstance(content, bytes):
        raise ValueError("content must be original CSV bytes")
    digest = hashlib.sha256(content).hexdigest()

    def key(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=False,
                                        separators=(",", ":")).encode()).hexdigest()

    batch_key = key(["coverage_export_v1", program_ref, source_ref, digest])
    observations: dict[tuple[str, ...], dict[str, Any]] = {}
    groups: dict[tuple[str, ...], dict[Decimal, list[str]]] = {}
    zips: set[str] = set()
    count = 0
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader, None)
        if header is None or len(header) != len(_COVERAGE_FIELDS) or set(header) != set(_COVERAGE_FIELDS):
            raise ValueError("CSV requires exactly: " + ",".join(_COVERAGE_FIELDS))
        for record, cells in enumerate(reader, start=2):
            count += 1
            if len(cells) != len(header):
                raise ValueError(f"record {record}: incorrect field count")
            raw = dict(zip(header, cells))
            for field, value in raw.items():
                if not value.strip() or any(ord(c) < 32 for c in value):
                    raise ValueError(f"record {record}: invalid {field}")
            if not re.fullmatch(r"[0-9]{5}", raw["zipcode"]):
                raise ValueError(f"record {record}: invalid zipcode (five digits required)")
            if not re.fullmatch(r"[A-Z]{2}", raw["state"]):
                raise ValueError(f"record {record}: invalid state (two uppercase letters required)")
            number = raw["expected_value"]
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", number):
                raise ValueError(f"record {record}: invalid expected_value")
            amount = Decimal(number)
            if not amount.is_finite() or amount <= 0:
                raise ValueError(f"record {record}: expected_value must be finite and positive")
            exact = tuple(raw[field] for field in _COVERAGE_FIELDS)
            occurrence = {"record": record, "ending_line": reader.line_num}
            if exact in observations:
                observations[exact]["occurrences"].append(occurrence)
                continue
            observation_key = "coverage:" + key([batch_key, exact])
            observations[exact] = {
                "observation_key": observation_key,
                "source_fields": raw,
                "occurrences": [occurrence],
                "expected_value": {"amount": number, "currency": None,
                                   "definition": None, "verified_payout": False},
            }
            location = exact[:5]
            groups.setdefault(location, {}).setdefault(amount, []).append(observation_key)
            zips.add(raw["zipcode"])
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("invalid UTF-8 CSV") from exc
    if not count:
        raise ValueError("CSV has no observations")
    conflicts = [
        {"location": dict(zip(_COVERAGE_FIELDS[:5], location)),
         "observations_by_value": [
             {"value": str(value), "observation_keys": keys}
             for value, keys in values.items()
         ], "canonical_value": None}
        for location, values in groups.items() if len(values) > 1
    ]
    return {
        "schema_version": "empire.coverage_export_preparation.v1",
        "batch_key": batch_key,
        "source": {"source_ref": source_ref, "sha256": digest,
                   "program_ref": program_ref},
        "classification": "OBSERVED",
        "commercial_channel": "affiliate_calls",
        "dry_run": True,
        "ingestion_ready": False,
        "live_traffic_authorized": False,
        "revenue_recognized": False,
        "payable_terms": {"payout_amount": None, "currency": None,
                          "qualification": None, "daily_cap": None, "cac": None},
        "summary": {"rows": count, "exact_distinct_rows": len(observations),
                    "exact_duplicate_rows": count - len(observations),
                    "zipcodes": len(zips), "differing_value_groups": len(conflicts)},
        "observations": list(observations.values()),
        "differing_values": conflicts,
        "blockers": ["expected_value_definition_unconfirmed", "payable_terms_unverified",
                     "canonical_inventory_and_capacity_unknown", "activation_not_authorized"],
    }
