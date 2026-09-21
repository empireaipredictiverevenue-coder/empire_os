"""Read-only snapshot of the EmpireOS Control Fabric registry."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from empire_os.control_fabric import default_registry


def build_control_fabric_snapshot() -> dict[str, Any]:
    registry = default_registry()
    authority = Counter(row.authority for row in registry)
    events: dict[str, list[str]] = {}
    for component in registry:
        for event in component.consumes:
            events.setdefault(event, []).append(component.name)
    return {
        "schema_version": "empire.control_fabric_snapshot.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE",
        "execution_authority": "none",
        "component_count": len(registry),
        "authority_counts": dict(sorted(authority.items())),
        "components": [row.as_dict() for row in registry],
        "event_routes": {
            key: sorted(value)
            for key, value in sorted(events.items())
        },
        "external_execution_enabled": False,
        "founder_gates_preserved": True,
    }
