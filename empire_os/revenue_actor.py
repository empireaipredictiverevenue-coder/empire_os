"""Governed composable revenue actor contract for EmpireOS.

Inspired by durable actor/job systems, but Empire's unit of work is a governed
commercial decision rather than a scrape task.

Actor execution never implies commercial execution authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


SCHEMA_VERSION = "empire.revenue_actor.v1"

ALLOWED_EXECUTION_AUTHORITIES = {"none"}

TRUTH_CLASSES = {
    "observed",
    "derived",
    "model_inference",
    "mixed",
    "unknown",
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ActorDescriptor:
    actor_key: str
    actor_version: str
    purpose: str
    input_schema: str
    output_schema: str
    policy_version: str
    model_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "actor_key": self.actor_key,
            "actor_version": self.actor_version,
            "purpose": self.purpose,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "policy_version": self.policy_version,
            "model_version": self.model_version,
        }


class RevenueActor(Protocol):
    descriptor: ActorDescriptor

    def run(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


def build_actor_envelope(
    *,
    descriptor: ActorDescriptor,
    actor_input: Mapping[str, Any],
    decision: str,
    recommended_next_action: str,
    output: Mapping[str, Any],
    evidence_refs: list[str] | tuple[str, ...] = (),
    truth_class: str = "derived",
    confidence: Mapping[str, Any] | None = None,
    blockers: list[str] | tuple[str, ...] = (),
    supports: list[str] | tuple[str, ...] = (),
    execution_authority: str = "none",
) -> dict[str, Any]:
    if execution_authority not in ALLOWED_EXECUTION_AUTHORITIES:
        raise ValueError(
            "Revenue Actor V1 cannot grant execution authority"
        )

    if truth_class not in TRUTH_CLASSES:
        raise ValueError("invalid revenue actor truth class")

    input_fp = fingerprint(actor_input)
    output_fp = fingerprint(output)

    run_identity_material = {
        "actor_key": descriptor.actor_key,
        "actor_version": descriptor.actor_version,
        "policy_version": descriptor.policy_version,
        "model_version": descriptor.model_version,
        "input_fingerprint": input_fp,
    }
    run_id = fingerprint(run_identity_material)

    return {
        "schema_version": SCHEMA_VERSION,
        "actor": descriptor.as_dict(),
        "run": {
            "run_id": run_id,
            "replay_key": run_id,
            "input_fingerprint": input_fp,
            "output_fingerprint": output_fp,
            "deterministic_replay_supported": True,
        },
        "truth_class": truth_class,
        "evidence_refs": list(dict.fromkeys(evidence_refs)),
        "decision": str(decision),
        "recommended_next_action": str(recommended_next_action),
        "confidence": dict(confidence or {}),
        "blockers": list(dict.fromkeys(blockers)),
        "supports": list(dict.fromkeys(supports)),
        "output": dict(output),
        "governance": {
            "outreach_authorized": False,
            "database_write_performed": False,
            "canonical_promotion_performed": False,
            "payment_mutation": False,
            "content_posted": False,
            "actual_revenue": False,
            "execution_authority": execution_authority,
        },
        "observability": {
            "actor_key": descriptor.actor_key,
            "actor_version": descriptor.actor_version,
            "policy_version": descriptor.policy_version,
            "model_version": descriptor.model_version,
            "input_fingerprint": input_fp,
            "output_fingerprint": output_fp,
        },
    }


def validate_actor_envelope(
    envelope: Mapping[str, Any],
) -> dict[str, Any]:
    actor = envelope.get("actor")
    run = envelope.get("run")
    governance = envelope.get("governance")

    if not isinstance(actor, Mapping):
        raise ValueError("actor descriptor missing")
    if not isinstance(run, Mapping):
        raise ValueError("actor run metadata missing")
    if not isinstance(governance, Mapping):
        raise ValueError("actor governance missing")

    required_actor = {
        "actor_key",
        "actor_version",
        "purpose",
        "input_schema",
        "output_schema",
        "policy_version",
    }
    missing = required_actor - set(actor)
    if missing:
        raise ValueError(
            f"actor descriptor incomplete: {sorted(missing)}"
        )

    if governance.get("execution_authority") != "none":
        raise ValueError("actor execution authority must remain none")

    forbidden_true = (
        "outreach_authorized",
        "database_write_performed",
        "canonical_promotion_performed",
        "payment_mutation",
        "content_posted",
        "actual_revenue",
    )
    for key in forbidden_true:
        if governance.get(key) is True:
            raise ValueError(
                f"revenue actor governance violation: {key}"
            )

    if envelope.get("truth_class") not in TRUTH_CLASSES:
        raise ValueError("invalid truth class")

    if not str(run.get("run_id") or ""):
        raise ValueError("run_id missing")

    return dict(envelope)
