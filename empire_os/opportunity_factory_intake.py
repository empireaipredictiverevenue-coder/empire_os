"""Truth-preserving intake bridge from Opportunity Radar to Opportunity Factory.

The bridge joins radar and bounded research evidence, then checks whether all
inputs required by Opportunity Factory exist. It never manufactures numeric
scores from search-result counts or model prose.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.opportunity_factory import (
    OpportunityCandidate,
    assess_opportunity,
)


RADAR = Path("runtime/opportunity_radar/latest.json")
RESEARCH = Path("runtime/opportunity_radar/research_latest.json")
NORMALIZED = Path("runtime/opportunity_factory/normalized_signals_latest.json")
OUTPUT = Path("runtime/opportunity_factory/intake_latest.json")

SCORE_KEYS = (
    "buyer_intent",
    "demand",
    "urgency",
    "margin_potential",
    "distribution_strength",
    "data_advantage",
    "fulfilment_readiness",
    "build_complexity",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _score(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= number <= 1.0:
        return None
    return round(number, 6)


def _refs(candidate: Mapping[str, Any], research: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for value in candidate.get("evidence_refs") or []:
        clean = _clean(value)
        if clean:
            refs.append(clean)
    for value in research.get("evidence_urls") or []:
        clean = _clean(value)
        if clean:
            refs.append(clean)
    return tuple(dict.fromkeys(refs))




NORMALIZER_BATCH_SCHEMA = "empire.opportunity_evidence_normalizer_batch.v1"
NORMALIZER_ROW_SCHEMA = "empire.opportunity_evidence_normalizer.v1"
ALLOWED_SCORE_SEMANTICS = frozenset((
    "observed_stage", "modeled_proxy", "policy_scenario",
))


def _fresh_producer_timestamp(value: Any, *, now: datetime) -> bool:
    if not isinstance(value, str) or not 20 <= len(value) <= 48:
        return False
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if stamp.tzinfo is None:
        return False
    age = now.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)
    return -timedelta(minutes=5) <= age <= timedelta(hours=2)


def _evidence_bound_signals(
    row: Mapping[str, Any], *,
    opportunity_key: str,
    opportunity_class: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Validate the producer's exact score/evidence contract before admission.

    Numeric output and a reported count alone cannot authorize Factory
    readiness or Opportunity Lifecycle commercial validation.
    """
    if (row.get("schema_version") != NORMALIZER_ROW_SCHEMA
            or row.get("mode") != "OBSERVE"
            or row.get("execution_authority") != "none"
            or row.get("search_result_counts_used_as_scores") is not False
            or row.get("competitor_gaps_used_as_demand") is not False
            or row.get("buyer_intent_inferred_from_public_pain") is not False
            or row.get("market_share_inferred") is not False
            or row.get("revenue_inferred") is not False
            or row.get("opportunity_key") != opportunity_key
            or row.get("opportunity_class") != opportunity_class):
        return {}, {}, "NORMALIZER_PRODUCER_CONTRACT_INVALID"
    signals = row.get("normalized_signals")
    evidence = row.get("score_evidence")
    if not isinstance(signals, Mapping) or not isinstance(evidence, Mapping):
        return {}, {}, "NORMALIZER_SCORE_EVIDENCE_MISSING"
    values = {}
    witnessed = {}
    for key in SCORE_KEYS:
        raw = signals.get(key)
        if raw is None:
            if key in evidence:
                return {}, {}, "NORMALIZER_EVIDENCE_WITHOUT_SCORE"
            values[key] = None
            continue
        value = _score(raw)
        proof = evidence.get(key)
        if (value is None or not isinstance(proof, Mapping)
                or _score(proof.get("value")) != value
                or proof.get("semantic_class") not in ALLOWED_SCORE_SEMANTICS
                or not isinstance(proof.get("basis"), str)
                or not 1 <= len(proof["basis"]) <= 160
                or not isinstance(proof.get("evidence_refs"), list)
                or not 1 <= len(proof["evidence_refs"]) <= 20
                or any(not isinstance(ref, str) or not 10 <= len(ref) <= 500
                       or not ref.startswith(("canonical:", "runtime:", "source:"))
                       for ref in proof["evidence_refs"])
                or proof.get("observed_truth") is not (
                    proof.get("semantic_class") == "observed_stage"
                )
                or proof.get("modeled_or_policy") is not (
                    proof.get("semantic_class") in ("modeled_proxy", "policy_scenario")
                )):
            return {}, {}, "NORMALIZER_SCORE_PROVENANCE_INVALID"
        values[key] = value
        witnessed[key] = dict(proof)
    if (type(row.get("normalized_score_count")) is not int
            or row["normalized_score_count"] != len(witnessed)):
        return {}, {}, "NORMALIZER_SCORE_COUNT_INCONSISTENT"
    for optional in ("offer_key", "distribution_path"):
        value = signals.get(optional)
        if value is None:
            continue
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 160:
            return {}, {}, "NORMALIZER_COMMERCIAL_PATH_INVALID"
        if optional == "offer_key" and (
            "build_complexity" not in witnessed
            or "canonical:commercial_product_catalog" not in
            witnessed["build_complexity"]["evidence_refs"]
        ):
            return {}, {}, "NORMALIZER_PRODUCT_AUTHORITY_MISSING"
        if optional == "distribution_path" and (
            "distribution_strength" not in witnessed
            or "canonical:buyer_candidate_reviews" not in
            witnessed["distribution_strength"]["evidence_refs"]
        ):
            return {}, {}, "NORMALIZER_DISTRIBUTION_AUTHORITY_MISSING"
        values[optional] = value.strip()
    return values, witnessed, "EVIDENCE_BOUND_OR_UNKNOWN"


def build_factory_intake(
    candidate: Mapping[str, Any],
    research: Mapping[str, Any] | None = None,
    *,
    normalized_signals: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    research = research or {}
    signals = dict(normalized_signals or {})

    opportunity_key = _clean(candidate.get("opportunity_key"))
    niche = _clean(candidate.get("niche"))
    trigger = _clean(candidate.get("trigger"))
    offer_key = _clean(
        signals.get("offer_key")
        if signals.get("offer_key") is not None
        else candidate.get("offer_key")
    )
    distribution_path = _clean(signals.get("distribution_path"))
    evidence_refs = _refs(candidate, research)

    scores = {
        key: _score(signals.get(key))
        for key in SCORE_KEYS
    }

    blockers: list[str] = []
    if not opportunity_key:
        blockers.append("opportunity_key_required")
    if not niche:
        blockers.append("niche_required")
    if not trigger:
        blockers.append("trigger_required")
    if not offer_key:
        blockers.append("offer_key_required")
    if not distribution_path:
        blockers.append("distribution_path_required")
    if len(evidence_refs) < 2:
        blockers.append("independent_evidence_required")
    for key, value in scores.items():
        if value is None:
            blockers.append(f"{key}_normalized_score_required")

    ready = not blockers
    assessment = None

    if ready:
        factory_candidate = OpportunityCandidate(
            opportunity_key=opportunity_key,
            niche=niche,
            trigger=trigger,
            offer_key=offer_key,
            distribution_path=distribution_path,
            evidence_refs=evidence_refs,
            **scores,
        )
        assessment = assess_opportunity(factory_candidate).as_dict()

    result = {
        "schema_version": "empire.opportunity_factory_intake.v1",
        "mode": "OBSERVE",
        "opportunity_key": opportunity_key,
        "tenant_id": candidate.get("tenant_id"),
        "opportunity_id": candidate.get("opportunity_id"),
        "opportunity_class": _clean(
            candidate.get("opportunity_class")
        ),
        "niche": niche or None,
        "trigger": trigger or None,
        "offer_key": offer_key or None,
        "distribution_path": distribution_path or None,
        "evidence_refs": list(evidence_refs),
        "evidence_count": len(evidence_refs),
        "research_observation_count": int(
            research.get("observation_count") or 0
        ),
        "normalized_scores": scores,
        "factory_ready": ready,
        "blockers": blockers,
        "assessment": assessment,
        "score_inference_from_search_results": False,
        "revenue_verified": False,
        "execution_authority": "none",
    }
    if "decision_provenance" in candidate:
        from empire_os.storm_opportunity_bridge import decision_opportunity_provenance
        provenance = decision_opportunity_provenance(
            candidate["decision_provenance"]["snapshot"],
            tenant_id=candidate.get("tenant_id"), event_id=candidate.get("event_id"),
            subject_id=candidate.get("subject_id"), as_of=datetime.now(timezone.utc),
        )
        result["decision_provenance"] = provenance
        result["research_requirements"] = provenance["research_requirements"]
    return result


def build_factory_intake_batch(
    radar: Mapping[str, Any],
    research_batch: Mapping[str, Any] | None,
    normalized_batch: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("offset-aware normalization clock required")
    research_batch = research_batch or {}
    normalized_batch = normalized_batch or {}
    research_by_key = {
        _clean(row.get("opportunity_key")): row
        for row in (research_batch.get("actions") or [])
        if isinstance(row, Mapping)
        and _clean(row.get("opportunity_key"))
    }

    normalized_rows = normalized_batch.get("items")
    producer_valid = (
        normalized_batch.get("schema_version") == NORMALIZER_BATCH_SCHEMA
        and normalized_batch.get("mode") == "OBSERVE"
        and normalized_batch.get("execution_authority") == "none"
        and _fresh_producer_timestamp(
            normalized_batch.get("generated_at"), now=clock
        )
        and normalized_batch.get("search_result_counts_used_as_scores") is False
        and normalized_batch.get("market_share_inferred") is False
        and normalized_batch.get("revenue_inferred") is False
        and isinstance(normalized_rows, list)
        and len(normalized_rows) <= 500
        and type(normalized_batch.get("candidate_count")) is int
        and len(normalized_rows) == normalized_batch.get("candidate_count")
        and all(isinstance(r, Mapping)
                and isinstance(r.get("opportunity_key"), str)
                and bool(r.get("opportunity_key"))
                for r in normalized_rows)
        and len({r["opportunity_key"] for r in normalized_rows})
            == len(normalized_rows)
    )
    normalized_by_key = (
        {r["opportunity_key"]: r for r in normalized_rows}
        if producer_valid else {}
    )
    invalid_normalizer_count = 0

    rows = []
    for candidate in (radar.get("candidates") or []):
        if not isinstance(candidate, Mapping):
            continue
        key = _clean(candidate.get("opportunity_key"))
        normalized_row = normalized_by_key.get(key) or {}
        signals = {}
        witnessed = {}
        evidence_status = "NORMALIZER_ROW_UNAVAILABLE"
        if normalized_row:
            signals, witnessed, evidence_status = _evidence_bound_signals(
                normalized_row,
                opportunity_key=key,
                opportunity_class=_clean(candidate.get("opportunity_class")),
            )
        elif normalized_batch and not producer_valid:
            evidence_status = "NORMALIZER_BATCH_CONTRACT_INVALID"
        if evidence_status not in (
            "EVIDENCE_BOUND_OR_UNKNOWN", "NORMALIZER_ROW_UNAVAILABLE"
        ):
            invalid_normalizer_count += 1
        row = build_factory_intake(
            candidate,
            research_by_key.get(key),
            normalized_signals=signals,
        )
        # In particular, untrusted score_evidence cannot advance the
        # lifecycle to VALIDATE while Factory correctly refuses readiness.
        row["normalization"] = {
            "available": evidence_status == "EVIDENCE_BOUND_OR_UNKNOWN",
            "evidence_contract_status": evidence_status,
            "normalized_score_count": len(witnessed),
            "missing_normalized_fields": [
                k for k in SCORE_KEYS if signals.get(k) is None
            ],
            "score_evidence": witnessed,
            "quant_inputs": (
                dict(normalized_row.get("quant_inputs") or {})
                if evidence_status == "EVIDENCE_BOUND_OR_UNKNOWN"
                and isinstance(normalized_row.get("quant_inputs"), Mapping)
                else {}
            ),
            "quant_input_evidence": (
                dict(normalized_row.get("quant_input_evidence") or {})
                if evidence_status == "EVIDENCE_BOUND_OR_UNKNOWN"
                and isinstance(normalized_row.get("quant_input_evidence"), Mapping)
                else {}
            ),
            "quant_inputs_available": (
                evidence_status == "EVIDENCE_BOUND_OR_UNKNOWN"
                and normalized_row.get("quant_inputs_available") is True
            ),
            "quant_probability_inferred": False,
            "search_result_counts_used_as_scores": False,
        }
        rows.append(row)

    # Report actual parsed score values, never the upstream producer's
    # unverified normalized_score_count claim. Missing commercial evidence
    # remains UNKNOWN rather than being treated as negative buyer demand.
    gap_counts = Counter(
        blocker for row in rows for blocker in row["blockers"]
    )
    scored_count = sum(
        any(value is not None for value in row["normalized_scores"].values())
        for row in rows
    )
    commercial_observation_count = sum(
        row["normalized_scores"]["buyer_intent"] is not None
        and row["normalized_scores"]["demand"] is not None
        for row in rows
    )
    return {
        "schema_version": "empire.opportunity_factory_intake_batch.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "factory_ready_count": sum(
            row["factory_ready"] for row in rows
        ),
        "blocked_count": sum(
            not row["factory_ready"] for row in rows
        ),
        "items": rows,
        "normalized_signal_source_available": bool(normalized_batch),
        "candidates_with_any_normalized_score": scored_count,
        "populated_scores_computed_from_values": True,
        "candidates_with_both_buyer_intent_and_demand_values": commercial_observation_count,
        "normalizer_batch_contract_accepted": producer_valid,
        "normalizer_rows_rejected_for_evidence": invalid_normalizer_count,
        "candidate_evidence_gap_counts": dict(
            sorted(gap_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "unverified_buyer_demand_not_negative_evidence": True,
        "search_observation_scores_inferred": False,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def refresh_factory_intake(repo_root: Path) -> dict[str, Any]:
    payload = build_factory_intake_batch(
        _read(repo_root / RADAR),
        _read(repo_root / RESEARCH),
        _read(repo_root / NORMALIZED),
    )
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
