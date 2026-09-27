"""Evidence-gated Cortex learning loop for EmpireOS.

This layer converts observed research/account/commercial evidence into bounded
model-review packets. It never treats forecasts as outcomes, never invents
commercial labels, and never mutates model weights. Positive customer labels
require verified payment + fulfilment + recognized revenue.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/cortex_learning/cortex_learning_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _latest_qualification_score(twin: Mapping[str, Any]) -> float | None:
    qualification = twin.get("qualification")
    if not isinstance(qualification, Mapping):
        return None

    history = qualification.get("history")
    if isinstance(history, list) and history:
        for row in reversed(history):
            if not isinstance(row, Mapping):
                continue
            value = row.get("score")
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                continue

    latest = qualification.get("latest_evidence")
    if isinstance(latest, Mapping):
        value = latest.get("qualification_score")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _verified_fulfilment(commercial: Mapping[str, Any]) -> bool:
    for row in commercial.get("fulfilment_orders", []) or []:
        if not isinstance(row, Mapping):
            continue
        state = _clean(row.get("state")).lower()
        if (
            row.get("delivered_at")
            or row.get("confirmed_at")
            or row.get("outcome_at")
            or state in {"delivered", "confirmed", "outcome_captured"}
        ):
            return True
    return False


def _verified_payment(commercial: Mapping[str, Any]) -> bool:
    return any(
        isinstance(row, Mapping)
        and _clean(row.get("transaction_hash"))
        and row.get("verified_at")
        for row in commercial.get("payment_evidence", []) or []
    )


def _latest_verified_outcome(twin: Mapping[str, Any]) -> Mapping[str, Any] | None:
    outcomes = twin.get("outcomes")
    if not isinstance(outcomes, Mapping):
        return None
    rows = [
        row
        for row in outcomes.get("history", []) or []
        if isinstance(row, Mapping)
        and _clean(row.get("evidence_kind"))
        and _clean(row.get("evidence_reference"))
    ]
    return rows[-1] if rows else None


def build_cortex_learning_packet(twin: Mapping[str, Any]) -> dict[str, Any]:
    identity = twin.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}

    public = twin.get("public_evidence")
    public = public if isinstance(public, Mapping) else {}

    competitor = twin.get("competitor_relationships")
    competitor = competitor if isinstance(competitor, Mapping) else {}

    research = twin.get("research")
    research = research if isinstance(research, Mapping) else {}

    conversation = twin.get("conversation")
    conversation = conversation if isinstance(conversation, Mapping) else {}

    commercial = twin.get("commercial")
    commercial = commercial if isinstance(commercial, Mapping) else {}

    revenue = twin.get("revenue_truth")
    revenue = revenue if isinstance(revenue, Mapping) else {}

    buyer_state = twin.get("buyer_state")
    buyer_state = buyer_state if isinstance(buyer_state, Mapping) else {}

    replies = [
        row
        for row in conversation.get("replies", []) or []
        if isinstance(row, Mapping)
    ]
    reply_classes = sorted({
        _clean(row.get("classification")).lower()
        for row in replies
        if _clean(row.get("classification"))
    })

    payment_verified = _verified_payment(commercial)
    fulfilment_verified = _verified_fulfilment(commercial)
    recognized_revenue_cents = (
        int(revenue.get("recognized_revenue_cents") or 0)
        if revenue.get("available") is True
        else None
    )
    realized_gp_cents = (
        int(revenue.get("realized_gp_cents") or 0)
        if revenue.get("available") is True
        else None
    )
    revenue_recognized = bool(
        recognized_revenue_cents is not None
        and recognized_revenue_cents > 0
    )

    entity_id = _clean(twin.get("entity_id"))
    outcome = _latest_verified_outcome(twin)
    conversion_outcome = (
        _clean(outcome.get("conversion_outcome")).lower()
        if outcome else ""
    )

    verification_refs: list[str] = []
    outcome_ref = ""
    if outcome is not None:
        outcome_id = _clean(outcome.get("id"))
        outcome_ref = (
            f"canonical:commercial_outcomes:{outcome_id}"
            if outcome_id
            else _clean(outcome.get("evidence_reference"))
        )
        if outcome_ref:
            verification_refs.append(outcome_ref)
        evidence_reference = _clean(outcome.get("evidence_reference"))
        if evidence_reference:
            verification_refs.append(evidence_reference)

    for row in commercial.get("payment_evidence", []) or []:
        if not isinstance(row, Mapping):
            continue
        tx_hash = _clean(row.get("transaction_hash"))
        verified_at = row.get("verified_at")
        if not tx_hash or not verified_at:
            continue
        evidence_id = _clean(row.get("id"))
        verification_refs.append(
            f"canonical:bsc_payment_evidence:{evidence_id}"
            if evidence_id
            else f"bsc_transaction:{tx_hash}"
        )

    for row in commercial.get("fulfilment_orders", []) or []:
        if not isinstance(row, Mapping):
            continue
        state = _clean(row.get("state")).lower()
        verified = bool(
            row.get("delivered_at")
            or row.get("confirmed_at")
            or row.get("outcome_at")
            or state in {"delivered", "confirmed", "outcome_captured"}
        )
        if not verified:
            continue
        order_id = _clean(row.get("id"))
        if order_id:
            verification_refs.append(
                f"canonical:fulfilment_orders:{order_id}"
            )

    if revenue_recognized and entity_id:
        verification_refs.append(
            f"canonical:account_revenue_truth:{entity_id}"
        )
    verification_refs = list(dict.fromkeys(verification_refs))

    label_value: int | None = None
    label_kind: str | None = None
    label_blockers: list[str] = []

    if outcome is None:
        label_blockers.append("verified_commercial_outcome_missing")
    elif conversion_outcome == "won":
        if not payment_verified:
            label_blockers.append("verified_payment_missing")
        if not fulfilment_verified:
            label_blockers.append("verified_fulfilment_missing")
        if not revenue_recognized:
            label_blockers.append("recognized_revenue_missing")
        if not label_blockers:
            label_kind = "verified_customer_conversion"
            label_value = 1
    elif conversion_outcome in {"lost", "no_response"}:
        label_kind = "verified_non_conversion"
        label_value = 0
    else:
        label_blockers.append("terminal_conversion_outcome_missing")

    learning_ready = label_value is not None
    score = _latest_qualification_score(twin)

    return {
        "schema_version": "empire.cortex_learning_packet.v1",
        "mode": "OBSERVE",
        "entity_id": entity_id,
        "company_name": _clean(identity.get("company_name")),
        "feature_namespace": "account_buyer_digital_twin",
        "research_features": {
            "supported_claim_count": int(
                public.get("supported_claim_count") or 0
            ),
            "competitor_evidence_count": int(
                competitor.get("evidence_count") or 0
            ),
            "research_observation_count": int(
                research.get("observation_count") or 0
            ),
            "qualification_score": score,
            "current_factual_state": buyer_state.get(
                "current_factual_state"
            ),
            "features_only": True,
            "commercial_label": False,
        },
        "reply_outcome": {
            "history_available": conversation.get("history_available") is True,
            "reply_count": len(replies),
            "observed": len(replies) > 0,
            "classifications": reply_classes,
            "commercial_label": False,
        },
        "verification": {
            "payment_verified": payment_verified,
            "fulfilment_verified": fulfilment_verified,
            "recognized_revenue": revenue_recognized,
            "recognized_revenue_cents": recognized_revenue_cents,
            "realized_gp_cents": realized_gp_cents,
            "outcome_ref": outcome_ref or None,
            "evidence_refs": verification_refs,
        },
        "label": {
            "available": learning_ready,
            "kind": label_kind,
            "value": label_value,
            "conversion_outcome": conversion_outcome or None,
            "source": "verified_commercial_outcome" if outcome else None,
            "outcome_ref": outcome_ref or None,
            "evidence_refs": verification_refs,
            "blockers": label_blockers,
            "synthetic": False,
            "forecast_derived": False,
        },
        "calibration_feedback": {
            "available": learning_ready and score is not None,
            "qualification_score": score,
            "verified_label": label_value,
            "outcome_ref": outcome_ref or None,
            "evidence_refs": verification_refs,
            "model_weight_mutation_authorized": False,
            "note": (
                "Raw qualification score paired with verified outcome for "
                "offline calibration review; score is not assumed to be a "
                "probability."
            ),
        },
        "learning_ready": learning_ready,
        "verified_customer_learning": (
            label_kind == "verified_customer_conversion"
        ),
        "forecast_used_as_outcome": False,
        "synthetic_commercial_label": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "model_weight_mutation_authorized": False,
        "execution_authority": "none",
    }


def build_cortex_learning_snapshot(
    account_twin_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    packets = [
        build_cortex_learning_packet(twin)
        for twin in account_twin_snapshot.get("twins", []) or []
        if isinstance(twin, Mapping)
    ]

    return {
        "schema_version": "empire.cortex_learning_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_count": len(packets),
        "learning_ready_count": sum(
            1 for row in packets if row["learning_ready"]
        ),
        "verified_customer_learning_count": sum(
            1 for row in packets if row["verified_customer_learning"]
        ),
        "reply_observed_count": sum(
            1 for row in packets if row["reply_outcome"]["observed"]
        ),
        "forecast_used_as_outcome": False,
        "synthetic_commercial_label_count": 0,
        "model_weight_mutation_authorized": False,
        "execution_authority": "none",
        "packets": packets,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def write_cortex_learning_snapshot(
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


def refresh_cortex_learning_snapshot(repo_root: Path) -> dict[str, Any]:
    twin_path = (
        repo_root
        / "runtime/account_twin/"
        / "account_twin_latest.json"
    )
    payload = build_cortex_learning_snapshot(_load_json(twin_path))
    write_cortex_learning_snapshot(repo_root, payload)
    return payload


def build_cortex_learning_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {
            "available": False,
            "schema_version": "empire.cortex_learning_snapshot.v1",
            "mode": "OBSERVE",
            "packet_count": 0,
            "learning_ready_count": 0,
            "verified_customer_learning_count": 0,
            "reply_observed_count": 0,
            "forecast_used_as_outcome": False,
            "synthetic_commercial_label_count": 0,
            "model_weight_mutation_authorized": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build evidence-gated Cortex learning packets"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.refresh:
        print(json.dumps(
            build_cortex_learning_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    payload = refresh_cortex_learning_snapshot(repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
