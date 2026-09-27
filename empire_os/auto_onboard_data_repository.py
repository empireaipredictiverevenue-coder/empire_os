"""Optional canonical buyer mirror for Auto Onboard.

Local tenant/subscription state remains the delivery-path truth. This repository
is a bounded mirror and must never make local onboarding fail.
"""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway


class AutoOnboardDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @property
    def configured(self) -> bool:
        return self._gateway.configured

    def record_buyer(self, row: dict[str, Any]) -> bool:
        if not self.configured:
            return False
        self._gateway.insert(
            "buyers",
            row,
            return_repr=False,
        )
        return True

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "repository_authority": "buyer_mirror_only",
            "delivery_path_authority": False,
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
