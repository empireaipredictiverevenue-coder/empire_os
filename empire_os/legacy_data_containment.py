"""Compatibility boundary for legacy hosted-data containment status.

Reliability code depends on generic containment semantics. This module preserves
the current legacy guard status path and compatibility fields until the hosted
backend is retired.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path("/srv/empire_os")
LEGACY_GUARD_STATUS_PATH = (
    ROOT / "runtime/control/supabase_egress_guard.json"
)


def legacy_data_contained(
    status_path: Path = LEGACY_GUARD_STATUS_PATH,
) -> bool:
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("state") == "contained"
        and payload.get("contained") is True
    )


def legacy_status_aliases(
    *,
    contained: bool,
    state: str,
) -> dict[str, Any]:
    """Temporary JSON compatibility aliases for existing consumers."""
    return {
        "supabase_egress_contained": bool(contained),
        "supabase_guard_state": str(state),
    }


def legacy_operating_state_alias(contained: bool) -> str:
    return (
        "SUPABASE_CONTAINED_LOCAL_RECOVERY"
        if contained
        else "NORMAL"
    )
