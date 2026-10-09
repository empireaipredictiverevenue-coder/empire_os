"""Canonical tenant/business-entity provenance for Economic Signal Fabric.

This module performs no writes and grants no execution authority.

Tenant identity must be supplied from authenticated/system context.
Entity ownership/scope is proven only by an active canonical
tenant_business_entity_bindings row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID


ALLOWED_BINDING_KINDS = frozenset({
    "owned",
    "managed",
    "customer",
    "prospect",
    "observed",
})


class TenantEntityBindingError(ValueError):
    pass


def _uuid(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    try:
        return str(UUID(text))
    except (ValueError, TypeError, AttributeError) as exc:
        raise TenantEntityBindingError(
            f"invalid_{field}"
        ) from exc


@dataclass(frozen=True)
class TenantEntityBinding:
    tenant_id: str
    entity_id: str
    binding_kind: str
    evidence_ref: str
    valid_from: str
    valid_until: str | None

    @property
    def binding_ref(self) -> str:
        return (
            "empiredb:tenant_business_entity_bindings:"
            f"{self.tenant_id}:{self.entity_id}:{self.binding_kind}:"
            f"{self.evidence_ref}"
        )


def resolve_tenant_entity_binding(
    cursor: Any,
    *,
    tenant_id: str,
    entity_id: str,
    as_of: datetime,
) -> TenantEntityBinding:
    """Resolve one active canonical tenant/entity binding.

    Multiple active binding kinds are ambiguous for this trust boundary and
    therefore fail closed rather than choosing one implicitly.
    """

    tenant = _uuid(tenant_id, field="tenant_id")
    entity = _uuid(entity_id, field="entity_id")

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise TenantEntityBindingError("aware_as_of_required")

    instant = as_of.astimezone(timezone.utc)

    cursor.execute(
        """
        SELECT
            tenant_id,
            entity_id,
            binding_kind,
            evidence_ref,
            valid_from,
            valid_until
        FROM public.tenant_business_entity_bindings
        WHERE tenant_id=%s
          AND entity_id=%s
          AND active=true
          AND valid_from <= %s
          AND (valid_until IS NULL OR valid_until > %s)
        ORDER BY binding_kind
        """,
        (tenant, entity, instant, instant),
    )

    rows = cursor.fetchall()

    if not rows:
        raise TenantEntityBindingError(
            "tenant_entity_binding_not_found"
        )

    if len(rows) != 1:
        raise TenantEntityBindingError(
            "tenant_entity_binding_ambiguous"
        )

    row = rows[0]

    kind = str(row[2] or "").strip()
    evidence_ref = str(row[3] or "").strip()

    if kind not in ALLOWED_BINDING_KINDS:
        raise TenantEntityBindingError(
            "unsupported_binding_kind"
        )

    if not evidence_ref:
        raise TenantEntityBindingError(
            "binding_evidence_required"
        )

    valid_from = row[4]
    valid_until = row[5]

    return TenantEntityBinding(
        tenant_id=tenant,
        entity_id=entity,
        binding_kind=kind,
        evidence_ref=evidence_ref,
        valid_from=valid_from.isoformat(),
        valid_until=(
            valid_until.isoformat()
            if valid_until is not None
            else None
        ),
    )
