"""Versioned API registry for Empire Data Cloud.

Foundation only: describes surfaces, authentication and exposure policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.data_cloud_contract import API_SURFACES


@dataclass(frozen=True)
class ApiContract:
    name: str
    prefix: str
    authenticated: bool = True
    tenant_context_required: bool = True
    public_enabled: bool = False
    raw_sql_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_api_registry() -> tuple[ApiContract, ...]:
    return tuple(
        ApiContract(
            name=surface.name,
            prefix=surface.prefix,
            tenant_context_required=surface.name not in {"platform"},
            public_enabled=False,
            raw_sql_allowed=False,
        )
        for surface in API_SURFACES
    )


def api_registry_snapshot() -> dict[str, Any]:
    rows = default_api_registry()
    return {
        "schema_version": "empire.data-cloud-api-registry.v1",
        "surfaces": [row.as_dict() for row in rows],
        "public_surface_count": sum(int(row.public_enabled) for row in rows),
        "raw_sql_surface_count": sum(int(row.raw_sql_allowed) for row in rows),
    }
