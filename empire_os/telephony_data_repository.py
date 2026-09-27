"""Canonical call-log mirror for telephony webhooks."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway


class TelephonyDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @property
    def configured(self) -> bool:
        return self._gateway.configured

    def record_call(self, row: dict[str, Any]) -> None:
        self._gateway.insert(
            "call_logs",
            row,
            return_repr=False,
        )

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "repository_authority": "call_log_mirror_only",
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
