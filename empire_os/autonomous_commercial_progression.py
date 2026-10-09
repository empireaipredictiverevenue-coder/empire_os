"""Autonomous internal commercial progression for EmpireOS.

This layer converts existing evidence-gated Next-Best-Action recommendations
into bounded internal execution decisions.

Authority model:

AUTO_INTERNAL
    Reversible internal work requires explicit runtime execution authority.

GATED_EXTERNAL
    Outreach, calls, binding commercial terms, payment/funds, destructive
    infrastructure, and revenue recognition remain outside this engine.

The engine deliberately prefers advancing an existing commercial opportunity
over discovering another one when a safe internal action can move the existing
opportunity closer to verified revenue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping


from empire_os.predictive_cloud_fabric import ExecutionAuthority


SCHEMA_VERSION = "empire.autonomous-commercial-progression.v1"

AUTO_INTERNAL_ACTIONS = frozenset({
    "prepare_buyer_review",
    "verify_decision_maker",
    "enrich_identity",
    "research_more",
    "refresh_evidence",
    "refresh_buyer_review",
    "recover_contact_evidence",
    "reconcile_identity",
})

GATED_EXTERNAL_ACTIONS = frozenset({
    "conversation_follow_up",
    "terms_candidate",
    "payment_review",
    "fulfilment_review",
    "send_email",
    "send_linkedin",
    "place_call",
    "accept_terms",
    "move_funds",
})

# Lower number = closer to commercial conversion and therefore higher priority.
ACTION_PRIORITY = {
    "prepare_buyer_review": 10,
    "refresh_buyer_review": 12,
    "verify_decision_maker": 20,
    "reconcile_identity": 22,
    "recover_contact_evidence": 25,
    "enrich_identity": 30,
    "refresh_evidence": 35,
    "research_more": 40,
}

DEFAULT_OUTPUT = Path(
    "runtime/autonomous_commercial_progression/latest.json"
)


def authority_state(mode: str, execution_authority: ExecutionAuthority | None = None) -> dict[str, Any]:
    """ACP projection of the existing fabric authority; never parse planner claims.

    Only a typed EXECUTE_BOUNDED supplied by the runtime caller permits ACP's
    allowlisted internal work. No fabric authority grants external execution here.
    Unknown modes and malformed/untyped authority fail closed.
    """
    mode = mode if type(mode) is str and mode in ("OBSERVE", "AUTO_INTERNAL", "GATED_EXTERNAL") else "OBSERVE"
    authorized = (
        mode in ("AUTO_INTERNAL", "GATED_EXTERNAL")
        and execution_authority is ExecutionAuthority.EXECUTE_BOUNDED
    )
    return {
        "mode": mode,
        "execution_authority": execution_authority.value if type(execution_authority) is ExecutionAuthority else "none",
        "internal_mutation_authorized": authorized,
        "external_execution_authorized": False,
    }


def authority_blocker(mode: str, execution_authority: ExecutionAuthority | None = None) -> dict[str, Any]:
    return {
        **authority_state(mode, execution_authority),
        "status": "BLOCKED",
        "blocker": "INTERNAL_MUTATION_AUTHORITY_REQUIRED",
        "retryable": False,
        "internal_mutation_performed": False,
        "external_execution_performed": False,
        "outbound_sent": False,
        "call_placed": False,
        "binding_terms_action": False,
        "payment_action": False,
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_authority(action: Mapping[str, Any]) -> str:
    """Return AUTO_INTERNAL, GATED_EXTERNAL, or NO_AUTHORITY.

    We trust neither model scores nor action names alone. An internal action
    must also carry the existing deterministic `internal_write` authority and
    must not require founder approval or an external wait.
    """
    name = _text(action.get("recommended_action"))
    authority = _text(action.get("authority"))

    if (
        name in AUTO_INTERNAL_ACTIONS
        and authority == "internal_write"
        and action.get("founder_gate_required") is not True
        and action.get("waiting_external") is not True
    ):
        return "AUTO_INTERNAL"

    if (
        name in GATED_EXTERNAL_ACTIONS
        or action.get("founder_gate_required") is True
        or authority in {"governed_external", "founder_gate"}
    ):
        return "GATED_EXTERNAL"

    return "NO_AUTHORITY"


def _priority(action: Mapping[str, Any]) -> tuple[int, str, str]:
    name = _text(action.get("recommended_action"))
    return (
        ACTION_PRIORITY.get(name, 10_000),
        _text(action.get("company_name")).casefold(),
        _text(action.get("entity_id")),
    )


def select_next_internal_action(
    next_best_action_snapshot: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Select one highest-value safe internal action.

    Discovery is intentionally not an AUTO_INTERNAL action here. If a known
    opportunity can be progressed, commercial progression wins over expansion.
    """
    candidates: list[dict[str, Any]] = []

    for raw in next_best_action_snapshot.get("actions") or []:
        if not isinstance(raw, Mapping):
            continue

        action = dict(raw)
        mode = classify_authority(action)

        if mode != "AUTO_INTERNAL":
            continue

        action["progression_mode"] = mode
        action["internal_mutation_authorized"] = False
        action["mutation_authorized"] = False
        action["execution_authority"] = "none"
        action["external_execution_authorized"] = False
        action["outreach_authorized"] = False
        action["call_authorized"] = False
        action["payment_authorized"] = False
        action["binding_terms_authorized"] = False
        candidates.append(action)

    if not candidates:
        return None

    candidates.sort(key=_priority)
    return candidates[0]


@dataclass(frozen=True)
class ProgressionReceipt:
    generated_at: str
    action: str | None
    company_name: str | None
    entity_id: str | None
    prospect_id: str | None
    mode: str
    status: str
    blocker: str | None
    recovery_strategy: str | None
    result: Mapping[str, Any]
    execution_authority: str = "none"
    internal_mutation_authorized: bool = False
    internal_mutation_performed: bool = False
    external_execution_performed: bool = False
    outbound_sent: bool = False
    call_placed: bool = False
    payment_action: bool = False
    binding_terms_action: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "action": self.action,
            "selected_action": self.action,
            "execution_authority": self.execution_authority,
            "internal_mutation_authorized": self.internal_mutation_authorized,
            "external_execution_authorized": False,
            "retryable": self.result.get("retryable", False),
            "company_name": self.company_name,
            "entity_id": self.entity_id,
            "prospect_id": self.prospect_id,
            "mode": self.mode,
            "status": self.status,
            "blocker": self.blocker,
            "recovery_strategy": self.recovery_strategy,
            "result": dict(self.result),
            "internal_mutation_performed": self.internal_mutation_performed,
            "external_execution_performed": self.external_execution_performed,
            "outbound_sent": self.outbound_sent,
            "call_placed": self.call_placed,
            "payment_action": self.payment_action,
            "binding_terms_action": self.binding_terms_action,
            "learning_event": {
                "blocker": self.blocker,
                "recovery_strategy": self.recovery_strategy,
                "result_status": self.status,
                "verified_commercial_outcome": False,
                "eligible_for_outcome_conditioned_economic_memory": False,
            },
        }


Handler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def execute_one_internal_progression(
    next_best_action_snapshot: Mapping[str, Any],
    *,
    handlers: Mapping[str, Handler],
    mode: str = "AUTO_INTERNAL",
    execution_authority: ExecutionAuthority | None = None,
) -> ProgressionReceipt:
    """Execute at most one allowlisted reversible internal progression action."""

    selected = select_next_internal_action(next_best_action_snapshot)
    state = authority_state(mode, execution_authority)
    receipt_authority = {key: state[key] for key in ("mode", "execution_authority", "internal_mutation_authorized")}
    if not state["internal_mutation_authorized"]:
        selected = selected or {}
        return ProgressionReceipt(
            generated_at=_now(), action=selected.get("recommended_action"),
            company_name=selected.get("company_name"), entity_id=selected.get("entity_id"),
            prospect_id=selected.get("prospect_id"), **receipt_authority,
            status="BLOCKED", blocker="INTERNAL_MUTATION_AUTHORITY_REQUIRED",
            recovery_strategy=None, result=authority_blocker(mode, execution_authority),
        )

    if selected is None:
        return ProgressionReceipt(
            generated_at=_now(),
            action=None,
            company_name=None,
            entity_id=None,
            prospect_id=None,
            **receipt_authority,
            status="IDLE_NO_SAFE_INTERNAL_ACTION",
            blocker="no_auto_internal_action_available",
            recovery_strategy=None,
            result={},
        )

    action_name = _text(selected.get("recommended_action"))
    handler = handlers.get(action_name)

    if handler is None:
        return ProgressionReceipt(
            generated_at=_now(),
            action=action_name,
            company_name=_text(selected.get("company_name")) or None,
            entity_id=_text(selected.get("entity_id")) or None,
            prospect_id=_text(selected.get("prospect_id")) or None,
            **receipt_authority,
            status="BLOCKED",
            blocker="internal_handler_not_registered",
            recovery_strategy=action_name,
            result={},
        )

    result = handler(selected)

    if not isinstance(result, Mapping):
        raise TypeError("progression handler must return a mapping")

    return ProgressionReceipt(
        generated_at=_now(),
        action=action_name,
        company_name=_text(selected.get("company_name")) or None,
        entity_id=_text(selected.get("entity_id")) or None,
        prospect_id=_text(selected.get("prospect_id")) or None,
        **receipt_authority,
        status=_text(result.get("status")) or "EXECUTED",
        blocker=_text(result.get("blocker")) or None,
        recovery_strategy=(
            _text(result.get("recovery_strategy"))
            or action_name
        ),
        result=dict(result),
        internal_mutation_performed=(
            result.get(
                "internal_mutation_performed"
            ) is True
        ),
    )


def build_progression_plan(
    next_best_action_snapshot: Mapping[str, Any],
    *, mode: str = "AUTO_INTERNAL",
    execution_authority: ExecutionAuthority | None = None,
) -> dict[str, Any]:
    selected = select_next_internal_action(next_best_action_snapshot)

    external_gates = []
    for raw in next_best_action_snapshot.get("actions") or []:
        if not isinstance(raw, Mapping):
            continue
        action_mode = classify_authority(raw)
        if action_mode == "GATED_EXTERNAL":
            external_gates.append({
                "entity_id": raw.get("entity_id"),
                "company_name": raw.get("company_name"),
                "recommended_action": raw.get("recommended_action"),
                "founder_gate_required": raw.get("founder_gate_required"),
                "authority": raw.get("authority"),
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        **authority_state(mode, execution_authority),
        "selected_action": selected.get("recommended_action") if selected else None,
        "selected_internal_action": selected,
        "safe_internal_action_available": selected is not None,
        "external_gate_count": len(external_gates),
        "external_gates": external_gates,
        "discovery_deprioritized_when_progression_available": True,
        "outreach_authorized": False,
        "call_authorized": False,
        "binding_terms_authorized": False,
        "payment_authorized": False,
        "external_execution_authorized": False,
    }


def write_progression_plan(
    payload: Mapping[str, Any],
    *,
    output: Path = DEFAULT_OUTPUT,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            dict(payload),
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp.replace(output)
    return output
