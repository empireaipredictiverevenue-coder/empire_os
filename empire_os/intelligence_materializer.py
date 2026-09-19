"""Evidence-preserving projection into the Empire Intelligence Fabric."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


class IntelligenceMaterializerError(RuntimeError):
    """Canonical inputs cannot be projected safely."""


PROSPECT_SOURCE_KEY = "empire.prospect.canonical.v1"
QUALIFICATION_SOURCE_KEY = "empire.qualification.lead_scoring.v1"


@dataclass(frozen=True)
class FactObservation:
    entity_id: str
    fact_key: str
    fact_value: dict[str, Any]
    source_key: str
    confidence: float
    first_seen_at: str
    last_seen_at: str
    evidence_hash: str


@dataclass(frozen=True)
class ScoreObservation:
    entity_id: str
    score_type: str
    score: float
    confidence: float
    model_key: str
    features: dict[str, Any]
    explanation: dict[str, Any]
    scored_at: str


@dataclass(frozen=True)
class MaterializationPlan:
    prospect_id: str
    entity_id: str
    fact_rows: tuple[FactObservation, ...]
    score_rows: tuple[ScoreObservation, ...]
    skipped_fields: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not self.fact_rows and not self.score_rows


def _uuid(value: Any, *, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise IntelligenceMaterializerError(
            f"invalid {field}"
        ) from exc


def _iso(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise IntelligenceMaterializerError(
            f"{field} is required"
        )
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntelligenceMaterializerError(
            f"invalid {field}"
        ) from exc
    return text


def _unit(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IntelligenceMaterializerError(
            f"invalid {field}"
        ) from exc
    if not 0.0 <= number <= 1.0:
        raise IntelligenceMaterializerError(
            f"{field} must be between 0 and 1"
        )
    return number


def _hash_evidence(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fact(
    *,
    prospect_id: str,
    entity_id: str,
    key: str,
    value: Any,
    observed_at: str,
    confidence: float,
) -> FactObservation:
    fact_value = {
        "value": value,
        "prospect_id": prospect_id,
        "confidence_basis": "active_identity_link_match_score",
    }
    evidence = {
        "source_key": PROSPECT_SOURCE_KEY,
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "fact_key": key,
        "fact_value": fact_value,
        "observed_at": observed_at,
    }
    return FactObservation(
        entity_id=entity_id,
        fact_key=key,
        fact_value=fact_value,
        source_key=PROSPECT_SOURCE_KEY,
        confidence=confidence,
        first_seen_at=observed_at,
        last_seen_at=observed_at,
        evidence_hash=_hash_evidence(evidence),
    )


def build_materialization_plan(
    *,
    prospect: dict[str, Any],
    identity_link: dict[str, Any],
    qualification: dict[str, Any],
) -> MaterializationPlan:
    if identity_link.get("active") is not True:
        raise IntelligenceMaterializerError(
            "identity link is not active"
        )

    prospect_id = _uuid(
        prospect.get("id"),
        field="prospect id",
    )
    link_prospect_id = _uuid(
        identity_link.get("prospect_id"),
        field="identity link prospect id",
    )
    if link_prospect_id != prospect_id:
        raise IntelligenceMaterializerError(
            "identity link prospect mismatch"
        )
    entity_id = _uuid(
        identity_link.get("entity_id"),
        field="entity id",
    )
    match_score = _unit(
        identity_link.get("match_score"),
        field="identity match_score",
    )
    observed_at = _iso(
        prospect.get("created_at"),
        field="prospect created_at",
    )

    fact_rows: list[FactObservation] = []
    skipped: list[str] = []
    for key in (
        "business_name",
        "niche",
        "metro",
        "address",
        "rating",
        "review_count",
        "runs_ads",
    ):
        value = prospect.get(key)
        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            skipped.append(key)
            continue
        fact_rows.append(
            _fact(
                prospect_id=prospect_id,
                entity_id=entity_id,
                key=key,
                value=value,
                observed_at=observed_at,
                confidence=match_score,
            )
        )

    qualification_id = _uuid(
        qualification.get("id"),
        field="qualification id",
    )
    qualification_prospect_id = _uuid(
        qualification.get("prospect_id"),
        field="qualification prospect id",
    )
    if qualification_prospect_id != prospect_id:
        raise IntelligenceMaterializerError(
            "qualification prospect mismatch"
        )

    score_rows: list[ScoreObservation] = []
    score = qualification.get("score")
    scored_at = qualification.get("scored_at")
    engine = str(
        qualification.get("scoring_engine") or ""
    ).strip()
    version = str(
        qualification.get("scoring_version") or ""
    ).strip()
    completeness = qualification.get(
        "data_completeness_score"
    )

    if (
        score is None
        or not scored_at
        or not engine
        or not version
        or completeness is None
    ):
        skipped.append("qualification_score")
    else:
        try:
            score_value = float(score)
            completeness_value = float(completeness)
        except (TypeError, ValueError) as exc:
            raise IntelligenceMaterializerError(
                "invalid qualification score data"
            ) from exc
        if not 0.0 <= completeness_value <= 100.0:
            raise IntelligenceMaterializerError(
                "data completeness must be between 0 and 100"
            )
        score_rows.append(
            ScoreObservation(
                entity_id=entity_id,
                score_type="lead_qualification",
                score=score_value,
                confidence=completeness_value / 100.0,
                model_key=f"{engine}:{version}",
                features={
                    "prospect_id": prospect_id,
                    "qualification_id": qualification_id,
                    "source_key": QUALIFICATION_SOURCE_KEY,
                    "tier": qualification.get("tier"),
                    "data_completeness_score": completeness_value,
                    "business_presence_score": qualification.get(
                        "business_presence_score"
                    ),
                    "market_fit_score": qualification.get(
                        "market_fit_score"
                    ),
                    "engagement_potential_score": qualification.get(
                        "engagement_potential_score"
                    ),
                    "enrichment_quality_score": qualification.get(
                        "enrichment_quality_score"
                    ),
                },
                explanation={
                    "recommended_action": qualification.get(
                        "recommended_action"
                    ),
                    "confidence_basis": (
                        "data_completeness_score/100; "
                        "not outcome-calibrated predictive confidence"
                    ),
                },
                scored_at=_iso(
                    scored_at,
                    field="qualification scored_at",
                ),
            )
        )

    return MaterializationPlan(
        prospect_id=prospect_id,
        entity_id=entity_id,
        fact_rows=tuple(fact_rows),
        score_rows=tuple(score_rows),
        skipped_fields=tuple(skipped),
    )
