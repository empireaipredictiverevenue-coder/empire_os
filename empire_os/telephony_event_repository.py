"""Canonical data repository for telephony event mirrors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"


class TelephonyEventRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "TelephonyEventRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def record_call(self, row: Mapping[str, Any]) -> None:
        self._gateway.insert(
            "call_logs",
            dict(row),
            return_repr=False,
        )
