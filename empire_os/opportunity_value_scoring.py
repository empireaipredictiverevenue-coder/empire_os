"""Read-only Opportunity Value projection from Quant Brain decision packets.

This module does not invent a second scoring model. It exposes the expected
economics and risk-adjusted score already produced by Quant Brain when the
required quantitative evidence exists. Unavailable packets remain unavailable.

All values are predictions/recommendations, never actual revenue or execution
authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


QUANT_REVIEW = Path("runtime/opportunity_factory/quant_review_latest.json")
OUTPUT = Path("runtime/opportunity_factory/value_latest.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _value_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    key = str(raw.get("opportunity_key") or "").strip()
    packet = raw.get("decision_packet")
    packet = packet if isinstance(packet, Mapping) else {}
    status = str(packet.get("status") or "UNAVAILABLE").upper()
    evidence = raw.get("quant_input_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}

    if status != "AVAILABLE":
        return {
            "opportunity_key": key or None,
            "opportunity_class": raw.get("opportunity_class"),
            "status": "UNAVAILABLE",
            "rank": None,
            "expected_revenue_cents": None,
            "expected_cost_cents": None,
            "expected_gross_profit_cents": None,
            "risk_adjusted_score": None,
            "missing_fields": list(packet.get("missing_fields") or []),
            "quant_input_evidence": dict(evidence),
            "prediction_only": True,
            "recommendation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    economics = packet.get("expected_economics")
    economics = economics if isinstance(economics, Mapping) else {}
    risk = packet.get("risk_adjusted")
    risk = risk if isinstance(risk, Mapping) else {}
    downside = packet.get("downside_simulation")
    downside = downside if isinstance(downside, Mapping) else {}

    required = {
        "expected_revenue_cents": _number(
            economics.get("expected_revenue_cents")
        ),
        "expected_cost_cents": _number(
            economics.get("expected_cost_cents")
        ),
        "expected_gross_profit_cents": _number(
            economics.get("expected_gross_profit_cents")
        ),
        "risk_adjusted_score": _number(
            risk.get("risk_adjusted_score")
        ),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        return {
            "opportunity_key": key or None,
            "opportunity_class": raw.get("opportunity_class"),
            "status": "UNAVAILABLE",
            "rank": None,
            **{name: None for name in required},
            "missing_fields": missing,
            "quant_input_evidence": dict(evidence),
            "prediction_only": True,
            "recommendation_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    return {
        "opportunity_key": key or None,
        "opportunity_class": raw.get("opportunity_class"),
        "status": "AVAILABLE",
        "rank": None,
        **required,
        "risk_penalty_cents": _number(risk.get("risk_penalty_cents")),
        "time_discount": _number(risk.get("time_discount")),
        "confidence": _number(risk.get("confidence")),
        "p05_gross_profit_cents": _number(
            downside.get("p05_gross_profit_cents")
        ),
        "p50_gross_profit_cents": _number(
            downside.get("p50_gross_profit_cents")
        ),
        "p95_gross_profit_cents": _number(
            downside.get("p95_gross_profit_cents")
        ),
        "probability_negative_gross_profit": _number(
            downside.get("probability_negative_gross_profit")
        ),
        "missing_fields": [],
        "quant_input_evidence": dict(evidence),
        "prediction_only": True,
        "recommendation_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_opportunity_value_snapshot(
    quant_review: Mapping[str, Any],
) -> dict[str, Any]:
    rows = [
        _value_row(raw)
        for raw in (quant_review.get("items") or [])
        if isinstance(raw, Mapping)
    ]

    available = [row for row in rows if row["status"] == "AVAILABLE"]
    available.sort(
        key=lambda row: (
            -float(row["risk_adjusted_score"]),
            str(row.get("opportunity_key") or ""),
        )
    )
    for rank, row in enumerate(available, 1):
        row["rank"] = rank

    unavailable = [row for row in rows if row["status"] != "AVAILABLE"]
    items = available + unavailable

    return {
        "schema_version": "empire.opportunity_value.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "value_available_count": len(available),
        "value_unavailable_count": len(unavailable),
        "items": items,
        "source": "quant_brain_decision_packets",
        "new_scoring_model_introduced": False,
        "prediction_only": True,
        "recommendation_only": True,
        "actual_revenue": False,
        "capital_execution": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def refresh_opportunity_value_snapshot(
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    payload = build_opportunity_value_snapshot(
        _read(root / QUANT_REVIEW)
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
