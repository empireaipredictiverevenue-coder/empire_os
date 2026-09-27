"""Truth-preserving intake bridge from Opportunity Radar to Opportunity Factory.

The bridge joins radar and bounded research evidence, then checks whether all
inputs required by Opportunity Factory exist. It never manufactures numeric
scores from search-result counts or model prose.
"""
from __future__ import annotations

from datetime import datetime, timezone
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

    return {
        "schema_version": "empire.opportunity_factory_intake.v1",
        "mode": "OBSERVE",
        "opportunity_key": opportunity_key,
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


def build_factory_intake_batch(
    radar: Mapping[str, Any],
    research_batch: Mapping[str, Any] | None,
    normalized_batch: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    research_batch = research_batch or {}
    normalized_batch = normalized_batch or {}
    research_by_key = {
        _clean(row.get("opportunity_key")): row
        for row in (research_batch.get("actions") or [])
        if isinstance(row, Mapping)
        and _clean(row.get("opportunity_key"))
    }

    normalized_by_key = {
        _clean(row.get("opportunity_key")): row
        for row in (normalized_batch.get("items") or [])
        if isinstance(row, Mapping)
        and _clean(row.get("opportunity_key"))
    }

    rows = []
    for candidate in (radar.get("candidates") or []):
        if not isinstance(candidate, Mapping):
            continue
        key = _clean(candidate.get("opportunity_key"))
        normalized_row = normalized_by_key.get(key) or {}
        signals = normalized_row.get("normalized_signals")
        signals = signals if isinstance(signals, Mapping) else {}
        row = build_factory_intake(
            candidate,
            research_by_key.get(key),
            normalized_signals=signals,
        )
        row["normalization"] = {
            "available": bool(normalized_row),
            "normalized_score_count": int(
                normalized_row.get("normalized_score_count") or 0
            ),
            "missing_normalized_fields": list(
                normalized_row.get("missing_normalized_fields") or []
            ),
            "score_evidence": dict(
                normalized_row.get("score_evidence") or {}
            ),
            "quant_inputs": dict(
                normalized_row.get("quant_inputs") or {}
            ),
            "quant_input_evidence": dict(
                normalized_row.get("quant_input_evidence") or {}
            ),
            "quant_inputs_available": (
                normalized_row.get("quant_inputs_available") is True
            ),
            "quant_probability_inferred": (
                normalized_row.get("quant_probability_inferred") is True
            ),
            "search_result_counts_used_as_scores": (
                normalized_row.get(
                    "search_result_counts_used_as_scores"
                ) is True
            ),
        }
        rows.append(row)

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
        "candidates_with_any_normalized_score": sum(
            int((row.get("normalization") or {}).get(
                "normalized_score_count", 0
            ) > 0)
            for row in rows
        ),
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
