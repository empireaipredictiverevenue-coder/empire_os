"""Evidence-gated Next-Best Action engine for EmpireOS.

This module recommends the next internal or governed action from factual buyer
state. It never executes actions, never promotes scores into commercial intent,
and never jumps across founder or payment gates.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/next_best_action/next_best_action_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _states(entity: Mapping[str, Any]) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    for row in entity.get("states", []) or []:
        if not isinstance(row, Mapping):
            continue
        name = _clean(row.get("state"))
        if not name:
            continue
        observed = row.get("observed")
        result[name] = observed if isinstance(observed, bool) else None
    return result


def _recommendation(
    *,
    entity: Mapping[str, Any],
    action: str,
    reason: str,
    authority: str = "internal_write",
    founder_gate_required: bool = False,
    waiting_external: bool = False,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "empire.next_best_action.v1",
        "entity_id": _clean(entity.get("entity_id")),
        "company_name": _clean(entity.get("company_name")),
        "prospect_id": _clean(entity.get("prospect_id")) or None,
        "current_factual_state": entity.get("current_factual_state"),
        "recommended_action": action,
        "reason": reason,
        "authority": authority,
        "founder_gate_required": founder_gate_required,
        "waiting_external": waiting_external,
        "evidence": dict(evidence or {}),
        "recommendation_only": True,
        "mutation_authorized": False,
        "external_execution_authorized": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
    }


def derive_next_best_action(
    entity: Mapping[str, Any],
    *,
    account_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one bounded recommendation from factual state only."""
    state = _states(entity)
    context = dict(account_context or {})
    current = _clean(entity.get("current_factual_state"))

    decision_maker_verified = (
        context.get("decision_maker_verified") is True
    )

    # Paid but not fulfilled must go through fulfilment review.
    if state.get("PAID") is True and state.get("FULFILLED") is not True:
        return _recommendation(
            entity=entity,
            action="fulfilment_review",
            reason="verified payment exists but fulfilment is not observed",
            authority="governed_external",
            evidence={
                "paid_observed": True,
                "fulfilled_observed": state.get("FULFILLED"),
            },
        )

    # Payment pending is an external wait, not a reason to manufacture payment.
    if (
        state.get("PAYMENT_PENDING") is True
        and state.get("PAID") is not True
    ):
        return _recommendation(
            entity=entity,
            action="hold",
            reason="payment is pending and verified payment is not observed",
            authority="observe",
            waiting_external=True,
            evidence={
                "payment_pending_observed": True,
                "paid_observed": state.get("PAID"),
            },
        )

    # Accepted/binding terms can justify payment review, but not payment creation.
    if state.get("TERMS") is True and state.get("PAYMENT_PENDING") is not True:
        return _recommendation(
            entity=entity,
            action="payment_review",
            reason="terms are observed but payment request authority is gated",
            authority="founder_gate",
            founder_gate_required=True,
            evidence={
                "terms_observed": True,
                "payment_pending_observed": state.get("PAYMENT_PENDING"),
            },
        )

    # Commercial intent can justify preparing terms, never binding them silently.
    if (
        state.get("COMMERCIAL_INTENT") is True
        and state.get("TERMS") is not True
    ):
        return _recommendation(
            entity=entity,
            action="terms_candidate",
            reason="commercial intent is observed and binding terms are absent",
            authority="founder_gate",
            founder_gate_required=True,
            evidence={
                "commercial_intent_observed": True,
                "terms_observed": state.get("TERMS"),
            },
        )

    # An observed conversation without commercial intent stays in conversation.
    if (
        state.get("CONVERSATION") is True
        and state.get("COMMERCIAL_INTENT") is not True
    ):
        return _recommendation(
            entity=entity,
            action="conversation_follow_up",
            reason="conversation is observed but commercial intent is not",
            authority="governed_external",
            evidence={
                "conversation_observed": True,
                "commercial_intent_observed": (
                    state.get("COMMERCIAL_INTENT")
                ),
            },
        )

    if state.get("ENGAGED") is True and state.get("CONVERSATION") is not True:
        return _recommendation(
            entity=entity,
            action="conversation_follow_up",
            reason="engagement is observed but conversation is not yet observed",
            authority="governed_external",
            evidence={
                "engaged_observed": True,
                "conversation_observed": state.get("CONVERSATION"),
            },
        )

    if state.get("CONTACTED") is True and state.get("ENGAGED") is not True:
        return _recommendation(
            entity=entity,
            action="hold",
            reason="contact is observed and the next event is external engagement",
            authority="observe",
            waiting_external=True,
            evidence={
                "contacted_observed": True,
                "engaged_observed": state.get("ENGAGED"),
            },
        )

    # READY is only an internal readiness state. Before any outbound proposal,
    # require observed decision-maker identity in the account context.
    if state.get("READY") is True and state.get("CONTACTED") is False:
        if not decision_maker_verified:
            return _recommendation(
                entity=entity,
                action="verify_decision_maker",
                reason=(
                    "account is ready for governed review but decision-maker "
                    "identity is not verified"
                ),
                authority="internal_write",
                evidence={
                    "ready_observed": True,
                    "contacted_observed": False,
                    "decision_maker_verified": False,
                },
            )
        return _recommendation(
            entity=entity,
            action="prepare_buyer_review",
            reason=(
                "account is ready, not contacted, and decision-maker identity "
                "is verified"
            ),
            authority="internal_write",
            evidence={
                "ready_observed": True,
                "contacted_observed": False,
                "decision_maker_verified": True,
            },
        )

    # Research completed but readiness unresolved means more evidence, not contact.
    if state.get("RESEARCHED") is True and state.get("READY") is not True:
        return _recommendation(
            entity=entity,
            action="research_more",
            reason=(
                "research is observed but readiness is not established by "
                "canonical qualification evidence"
            ),
            authority="internal_write",
            evidence={
                "researched_observed": True,
                "ready_observed": state.get("READY"),
                "unknown_states": entity.get("unknown_states", []),
            },
        )

    if state.get("DISCOVERED") is True and state.get("RESEARCHED") is not True:
        return _recommendation(
            entity=entity,
            action="enrich_identity",
            reason="entity is discovered but account research is incomplete",
            authority="internal_write",
            evidence={
                "discovered_observed": True,
                "researched_observed": state.get("RESEARCHED"),
            },
        )

    return _recommendation(
        entity=entity,
        action="hold",
        reason="no stronger evidence-backed next action is currently justified",
        authority="observe",
        evidence={
            "current_factual_state": current or None,
            "unknown_states": entity.get("unknown_states", []),
        },
    )


def build_next_best_action_snapshot(
    buyer_state_snapshot: Mapping[str, Any],
    *,
    account_contexts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    contexts = {
        _clean(row.get("entity_id")): row
        for row in account_contexts
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }

    actions = [
        derive_next_best_action(
            entity,
            account_context=contexts.get(_clean(entity.get("entity_id"))),
        )
        for entity in buyer_state_snapshot.get("entities", []) or []
        if isinstance(entity, Mapping)
    ]

    actions.sort(
        key=lambda row: (
            row["founder_gate_required"],
            row["waiting_external"],
            row["company_name"].casefold(),
        )
    )

    return {
        "schema_version": "empire.next_best_action_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "action_count": len(actions),
        "founder_gate_count": sum(
            1 for row in actions if row["founder_gate_required"]
        ),
        "waiting_external_count": sum(
            1 for row in actions if row["waiting_external"]
        ),
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_authorized": False,
        "payment_authorized": False,
        "execution_authority": "none",
        "actions": actions,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _load_account_contexts(repo_root: Path) -> list[dict[str, Any]]:
    # Claim-critic briefs intentionally do not assert decision-maker identity
    # today. Preserve that unknown rather than manufacturing verification.
    path = (
        repo_root
        / "runtime/competitive_intelligence/"
        / "competitor_account_briefs_latest.json"
    )
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return []

    contexts = []
    for brief in payload.get("briefs", []) or []:
        if not isinstance(brief, Mapping):
            continue
        contexts.append({
            "entity_id": brief.get("entity_id"),
            "decision_maker_verified": False,
            "claim_critic": brief.get("claim_critic"),
        })
    return contexts


def write_next_best_action_snapshot(
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


def refresh_next_best_action_snapshot(repo_root: Path) -> dict[str, Any]:
    buyer_state_path = (
        repo_root
        / "runtime/buyer_state/"
        / "buyer_state_latest.json"
    )
    buyer_state = _load_json(buyer_state_path)
    payload = build_next_best_action_snapshot(
        buyer_state,
        account_contexts=_load_account_contexts(repo_root),
    )
    write_next_best_action_snapshot(repo_root, payload)
    return payload


def build_next_best_action_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {
            "available": False,
            "schema_version": "empire.next_best_action_snapshot.v1",
            "mode": "OBSERVE",
            "action_count": 0,
            "founder_gate_count": 0,
            "waiting_external_count": 0,
            "outreach_authorized": False,
            "payment_authorized": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build evidence-gated Next-Best Actions"
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
            build_next_best_action_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    payload = refresh_next_best_action_snapshot(repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
