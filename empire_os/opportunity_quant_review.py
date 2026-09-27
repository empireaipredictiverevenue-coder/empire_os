"""Quantitative review of Opportunity Factory candidates.

This is a deterministic bridge between Opportunity Factory and Quant Brain.
It never invents missing probability/economics inputs. Incomplete candidates
receive an UNAVAILABLE decision packet with explicit missing fields.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.quant_brain import quant_decision_packet


INTAKE = Path("runtime/opportunity_factory/intake_latest.json")
OUTPUT = Path("runtime/opportunity_factory/quant_review_latest.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_quant_review(
    intake: Mapping[str, Any],
    *,
    trials: int = 2500,
    seed: int = 0,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing_counts: Counter[str] = Counter()

    for raw in intake.get("items") or []:
        if not isinstance(raw, Mapping):
            continue
        key = str(raw.get("opportunity_key") or "").strip()
        if not key:
            continue
        normalization = raw.get("normalization")
        normalization = (
            normalization if isinstance(normalization, Mapping) else {}
        )
        inputs = normalization.get("quant_inputs")
        inputs = inputs if isinstance(inputs, Mapping) else {}

        packet = quant_decision_packet(
            candidate_id=key,
            inputs=inputs,
            trials=trials,
            seed=seed,
        )
        missing = list(packet.get("missing_fields") or [])
        missing_counts.update(missing)

        rows.append({
            "opportunity_key": key,
            "opportunity_class": raw.get("opportunity_class"),
            "factory_ready": raw.get("factory_ready") is True,
            "quant_input_evidence": dict(
                normalization.get("quant_input_evidence") or {}
            ),
            "decision_packet": packet,
            "execution_authority": "none",
        })

    available = sum(
        row["decision_packet"].get("status") == "AVAILABLE"
        for row in rows
    )
    return {
        "schema_version": "empire.opportunity_quant_review.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "available_decision_packet_count": available,
        "unavailable_decision_packet_count": len(rows) - available,
        "missing_field_counts": dict(
            sorted(
                missing_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "items": rows,
        "prediction_is_actual": False,
        "capital_execution": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def refresh_quant_review(repo_root: Path) -> dict[str, Any]:
    payload = build_quant_review(_read(repo_root / INTAKE))
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
