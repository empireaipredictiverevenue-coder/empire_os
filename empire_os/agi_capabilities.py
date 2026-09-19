"""Typed capability registry and request review for Empire agents.

This is a policy-facing registry, not an executor.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Capability:
    key: str
    side_effect_class: str
    minimum_mode: str
    approval_required: bool
    reversible: bool
    description: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_MODE_ORDER = {
    "OBSERVE": 0,
    "ASSIST": 1,
    "GUARDED_EXECUTE": 2,
}

_CAPABILITIES = {
    "evidence.read": Capability(
        "evidence.read", "none", "OBSERVE", False, True,
        "Read governed evidence through scoped adapters.",
    ),
    "world_model.read": Capability(
        "world_model.read", "none", "OBSERVE", False, True,
        "Read canonical temporal world-state projections.",
    ),
    "forecast.preview": Capability(
        "forecast.preview", "none", "OBSERVE", False, True,
        "Create a non-mutating predictive preview.",
    ),
    "simulation.preview": Capability(
        "simulation.preview", "none", "OBSERVE", False, True,
        "Run a simulation labelled non-actual.",
    ),
    "content.draft": Capability(
        "content.draft", "reversible_internal", "ASSIST", False, True,
        "Draft content without publishing.",
    ),
    "outreach.send": Capability(
        "outreach.send", "external_communication", "GUARDED_EXECUTE", True, False,
        "Send approved external outreach through the governed sender.",
    ),
    "voice.call": Capability(
        "voice.call", "external_communication", "GUARDED_EXECUTE", True, False,
        "Initiate an approved external voice call.",
    ),
    "campaign.mutate": Capability(
        "campaign.mutate", "commercial_mutation", "GUARDED_EXECUTE", True, False,
        "Change an external campaign or spend configuration.",
    ),
    "inventory.allocate": Capability(
        "inventory.allocate", "commercial_mutation", "GUARDED_EXECUTE", True, False,
        "Allocate commercial inventory to a buyer.",
    ),
    "payment.move": Capability(
        "payment.move", "financial", "GUARDED_EXECUTE", True, False,
        "Move or settle funds through an approved payment workflow.",
    ),
    "infrastructure.change": Capability(
        "infrastructure.change", "infrastructure", "GUARDED_EXECUTE", True, False,
        "Change production infrastructure.",
    ),
    "model.promote": Capability(
        "model.promote", "commercial_mutation", "GUARDED_EXECUTE", True, False,
        "Promote an evaluated model/configuration into production.",
    ),
}


def capability_registry() -> dict[str, Any]:
    return {
        "schema_version": "agi_capability_registry.v1",
        "capabilities": [
            _CAPABILITIES[key].as_dict()
            for key in sorted(_CAPABILITIES)
        ],
        "wildcard_capabilities": False,
        "unrestricted_shell_capability": False,
        "unrestricted_database_capability": False,
    }


def review_capability_request(request: Mapping[str, Any]) -> dict[str, Any]:
    capability_key = str(request.get("capability") or "").strip()
    agent_id = str(request.get("agent_id") or "").strip()
    mode = str(request.get("authority_mode") or "OBSERVE").strip()
    approval_present = request.get("approval_present") is True
    granted = {
        str(x).strip()
        for x in request.get("granted_capabilities", ())
        if str(x).strip()
    }

    blockers: list[str] = []
    capability = _CAPABILITIES.get(capability_key)

    if not agent_id:
        blockers.append("agent_id_required")
    if capability is None:
        blockers.append("unknown_capability")
    if mode not in _MODE_ORDER:
        blockers.append("unsupported_authority_mode")

    if capability is not None and mode in _MODE_ORDER:
        if capability_key not in granted:
            blockers.append("capability_not_granted")
        if _MODE_ORDER[mode] < _MODE_ORDER[capability.minimum_mode]:
            blockers.append("authority_mode_too_low")
        if capability.approval_required and not approval_present:
            blockers.append("approval_required")

    permitted = not blockers
    return {
        "schema_version": "agi_capability_review.v1",
        "agent_id": agent_id or None,
        "capability": capability_key or None,
        "authority_mode": mode,
        "capability_definition": capability.as_dict() if capability else None,
        "permitted": permitted,
        "blockers": blockers,
        "execution_performed": False,
    }
