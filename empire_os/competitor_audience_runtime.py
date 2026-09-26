"""Founder-facing runtime projection for competitor audience intelligence.

Canonical signals are read through the dedicated least-privilege materializer
login. Raw signal rows may be repeated snapshots, so founder metrics are built
from unique public evidence fingerprints rather than raw row counts.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from empire_os.competitor_audience_omega_cortex import (
    build_competitor_omega_cortex_context,
)
from empire_os.competitor_audience_priority import (
    rank_competitor_audience_companies,
)
from empire_os.intelligence_materializer_transport import (
    ROLE,
    PostgresIntelligenceMaterializer,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/competitor_audience_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _evidence_fingerprint(
    entity_id: str,
    item: Mapping[str, Any],
) -> tuple[str, str, str, str] | None:
    competitor_key = _clean(item.get("competitor_key"))
    evidence_type = _clean(item.get("evidence_type"))
    source_ref = _clean(item.get("source_ref"))

    if not entity_id or not competitor_key or not evidence_type or not source_ref:
        return None

    return (
        entity_id,
        competitor_key,
        evidence_type,
        source_ref,
    )


def summarize_competitor_audience_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Summarize canonical competitor signals without double-counting evidence."""
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    raw_rows = [row for row in rows if isinstance(row, Mapping)]

    company_state: dict[str, dict[str, Any]] = {}
    unique_fingerprints: set[tuple[str, str, str, str]] = set()
    competitor_keys: set[str] = set()
    latest_observed_at: str | None = None

    for row in raw_rows:
        entity_id = _clean(row.get("entity_id"))
        if not entity_id:
            continue

        company = company_state.setdefault(
            entity_id,
            {
                "entity_id": entity_id,
                "company_name": _clean(row.get("canonical_name")),
                "company_website": _clean(row.get("canonical_website")),
                "evidence": [],
                "competitors": set(),
                "confidence_values": [],
                "signal_rows": 0,
            },
        )
        company["signal_rows"] += 1

        observed_at = _clean(row.get("observed_at"))
        if observed_at and (
            latest_observed_at is None or observed_at > latest_observed_at
        ):
            latest_observed_at = observed_at

        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if not isinstance(payload, Mapping):
            payload = {}

        evidence = payload.get("evidence")
        if not isinstance(evidence, list):
            continue

        for item in evidence:
            if not isinstance(item, Mapping):
                continue

            fingerprint = _evidence_fingerprint(entity_id, item)
            if fingerprint is None or fingerprint in unique_fingerprints:
                continue

            unique_fingerprints.add(fingerprint)
            competitor_key = fingerprint[1]
            competitor_keys.add(competitor_key)
            company["competitors"].add(competitor_key)

            confidence = item.get("confidence")
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                confidence_value = None

            if (
                confidence_value is not None
                and 0.0 <= confidence_value <= 1.0
            ):
                company["confidence_values"].append(confidence_value)

            company["evidence"].append(
                {
                    "competitor_key": competitor_key,
                    "evidence_type": fingerprint[2],
                    "source_ref": fingerprint[3],
                    "summary": _clean(item.get("summary")),
                    "observed_at": _clean(item.get("observed_at")),
                    "confidence": confidence_value,
                }
            )

    companies: list[dict[str, Any]] = []
    for company in company_state.values():
        evidence = company["evidence"]
        if not evidence:
            continue

        confidences = company.pop("confidence_values")
        competitors = sorted(company.pop("competitors"))
        evidence.sort(
            key=lambda item: (
                item.get("competitor_key") or "",
                item.get("source_ref") or "",
            )
        )

        companies.append(
            {
                **company,
                "competitors": competitors,
                "competitor_count": len(competitors),
                "unique_evidence_count": len(evidence),
                "stack_strength": min(1.0, len(evidence) / 3.0),
                "confidence": (
                    round(sum(confidences) / len(confidences), 6)
                    if confidences
                    else None
                ),
                "research_candidate": True,
                "buyer_intent": False,
                "commercial_intent": False,
                "outreach_enabled": False,
                "execution_authority": "none",
            }
        )

    companies.sort(
        key=lambda row: (
            -int(row["unique_evidence_count"]),
            row["company_name"].casefold(),
        )
    )

    priorities = rank_competitor_audience_companies(companies)
    omega_cortex_context = build_competitor_omega_cortex_context(
        priorities
    )
    priority_by_entity = {
        row["entity_id"]: row
        for row in priorities
        if row.get("entity_id")
    }

    for company in companies:
        company["research_priority"] = priority_by_entity.get(
            company["entity_id"],
            {
                "research_priority_score": 0.0,
                "research_priority_rank": None,
                "stack_state": "NO_EVIDENCE",
                "recommendation_only": True,
                "execution_authority": "none",
            },
        )

    return {
        "schema_version": "empire.competitor_audience_runtime.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "generated_at": generated,
        "latest_observed_at": latest_observed_at,
        "canonical_signal_row_count": len(raw_rows),
        "company_count": len(companies),
        "competitor_count": len(competitor_keys),
        "unique_evidence_count": len(unique_fingerprints),
        "stacked_company_count": sum(
            1 for row in companies
            if int(row["unique_evidence_count"]) >= 2
        ),
        "max_evidence_stack": max(
            (
                int(row["unique_evidence_count"])
                for row in companies
            ),
            default=0,
        ),
        "research_priority": priorities,
        "omega_cortex_context": omega_cortex_context,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "companies": companies,
    }


def load_canonical_competitor_rows(
    writer: PostgresIntelligenceMaterializer,
) -> list[dict[str, Any]]:
    with writer._connect(writer.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {ROLE}")
            cursor.execute(
                """
                SELECT
                  s.id,
                  s.entity_id,
                  be.canonical_name,
                  be.canonical_website,
                  s.observed_at,
                  s.strength,
                  s.confidence,
                  s.payload
                FROM public.intelligence_signals s
                JOIN public.business_entities be
                  ON be.id=s.entity_id
                WHERE s.signal_type='competitor_audience_evidence'
                  AND s.signal_domain='competitive_intelligence'
                ORDER BY s.observed_at ASC, s.id ASC
                """
            )
            names = [item.name for item in cursor.description]
            return [
                dict(zip(names, row, strict=True))
                for row in cursor.fetchall()
            ]


def write_competitor_audience_snapshot(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def refresh_competitor_audience_snapshot(
    repo_root: Path,
    writer: PostgresIntelligenceMaterializer,
) -> dict[str, Any]:
    payload = summarize_competitor_audience_rows(
        load_canonical_competitor_rows(writer)
    )
    write_competitor_audience_snapshot(repo_root, payload)
    return payload


def build_competitor_audience_runtime(
    repo_root: Path,
) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.competitor_audience_runtime.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "reason": "canonical_competitor_audience_snapshot_unavailable",
            "company_count": 0,
            "unique_evidence_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
        }

    if not isinstance(payload, dict):
        return {
            "available": False,
            "schema_version": "empire.competitor_audience_runtime.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "reason": "canonical_competitor_audience_snapshot_invalid",
            "company_count": 0,
            "unique_evidence_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
        }

    return {
        "available": True,
        **payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh canonical competitor audience founder snapshot"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Read canonical signals and atomically refresh founder snapshot.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.refresh:
        print(
            json.dumps(
                build_competitor_audience_runtime(repo_root),
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_competitor_audience_snapshot(repo_root, writer)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
