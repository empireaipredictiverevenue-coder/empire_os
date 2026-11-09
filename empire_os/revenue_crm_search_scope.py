"""Validate server-loaded CRM/SEO bindings; never an HTTP auth substitute.

The caller must authenticate the CRM principal and obtain these records from
the restricted database reader. Request payloads must never supply bindings.
This module grants no database, publishing or commercial authority.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class SearchScopeUnavailable(ValueError):
    """No unambiguous, current account/site scope can be established."""


@dataclass(frozen=True)
class AccountSiteBinding:
    tenant_id: str
    prospect_id: str
    entity_id: str
    site_id: str
    tenant_key: str
    evidence_ref: str
    valid_from: datetime
    valid_until: datetime | None = None
    active: bool = True


@dataclass(frozen=True)
class ResolvedSearchScope:
    tenant_id: str
    prospect_id: str
    entity_id: str
    site_id: str
    tenant_key: str
    binding_evidence_ref: str


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise SearchScopeUnavailable("invalid scope identity") from None


def _aware(value: datetime) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def resolve_search_scope(
    *,
    authenticated_tenant_id: str,
    prospect_id: str,
    site_id: str,
    authorized_entity_id: str,
    server_bindings: tuple[AccountSiteBinding, ...],
    now: datetime,
) -> ResolvedSearchScope:
    """Require exactly one current binding for an already-authorised entity.

Tenant and entity must come from the authenticated CRM reader. Site/prospect
selectors may come from a request but convey no authority. Expired/revoked
records cannot resolve a scope. Unexpected rows fail closed, not silently
filtered. Multiple current records remain ambiguous even if identical.
"""
    tenant, prospect, site, entity = map(_uuid, (
        authenticated_tenant_id, prospect_id, site_id, authorized_entity_id,
    ))
    if not _aware(now):
        raise SearchScopeUnavailable("timezone-aware observation time required")
    current = []
    for row in server_bindings:
        if not isinstance(row, AccountSiteBinding):
            raise SearchScopeUnavailable("invalid binding record")
        identities = tuple(map(_uuid, (
            row.tenant_id, row.prospect_id, row.site_id, row.entity_id,
        )))
        if identities != (tenant, prospect, site, entity):
            raise SearchScopeUnavailable("binding scope mismatch")
        if type(row.active) is not bool:
            raise SearchScopeUnavailable("invalid binding state")
        if (not _aware(row.valid_from)
                or (row.valid_until is not None and not _aware(row.valid_until))):
            raise SearchScopeUnavailable("invalid binding validity")
        if row.valid_until is not None and row.valid_until <= row.valid_from:
            raise SearchScopeUnavailable("invalid binding interval")
        for value in (row.tenant_key, row.evidence_ref):
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise SearchScopeUnavailable("invalid binding provenance or search key")
        if (row.active and row.valid_from <= now
                and (row.valid_until is None or now < row.valid_until)):
            current.append(row)
    if len(current) != 1:
        raise SearchScopeUnavailable("account/site scope unavailable or ambiguous")
    row = current[0]
    return ResolvedSearchScope(
        tenant, prospect, entity, site, row.tenant_key, row.evidence_ref,
    )
