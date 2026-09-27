"""Vendor-neutral token-scoped transport for the Astra observer."""
from __future__ import annotations

from typing import Any, Protocol

from empire_os.outcome_role_transport import OutcomeTransportError


ASTRA_TOKEN_FUNCTIONS = {
    "get_commercial_outcome_feedback": ("p_limit",),
    "get_astra_operational_evidence": (),
}


class AstraTokenBackend(Protocol):
    def call(
        self,
        name: str,
        params: dict[str, Any],
    ) -> Any:
        ...


class AstraTokenRpc:
    """Read-only Astra observer RPC policy boundary."""

    def __init__(self, backend: AstraTokenBackend):
        self._backend = backend

    def __call__(self, name: str, params: dict[str, Any]) -> Any:
        if name not in ASTRA_TOKEN_FUNCTIONS:
            raise OutcomeTransportError(
                f"Astra observer is not allowed to execute {name}"
            )

        keys = ASTRA_TOKEN_FUNCTIONS[name]
        if not isinstance(params, dict) or set(params) != set(keys):
            raise OutcomeTransportError("unexpected Astra RPC parameters")

        return self._backend.call(name, params)
