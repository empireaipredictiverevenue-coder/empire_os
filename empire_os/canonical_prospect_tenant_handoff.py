"""Exact existing EmpireDB prospect -> entity -> tenant read-only handoff.

This is NOT an opportunity/lead promotion or an authentication gateway.
Callers MUST supply a cursor from the original, independently authenticated
tenant-scoped reader. The injected cursor proves query semantics in tests
only; it does not independently attest the PostgreSQL login.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.economic_signal_tenant_binding import (
    TenantEntityBindingError, resolve_tenant_entity_binding,
)

SCHEMA = "empire.canonical.prospect_tenant_handoff.v1"
_ALLOWED_MATCH = frozenset({
    "exact_primary_domain", "verified_source_identity",
    "first_party_official_match", "source_and_official_registry",
})

class ProspectHandoffHold(ValueError):
    pass

def _uuid(raw: Any, field: str) -> str:
    if not isinstance(raw, str):
        raise ProspectHandoffHold("INVALID_" + field)
    try:
        uid = str(UUID(raw))
    except (TypeError, AttributeError, ValueError) as exc:
        raise ProspectHandoffHold("INVALID_" + field) from exc
    if uid != raw.lower():
        raise ProspectHandoffHold("NON_CANONICAL_" + field)
    return uid

def review_existing_prospect_entity_tenant(
    cursor: Any, *,
    prospect_id: str,
    entity_id: str,
    authenticated_tenant_id: str,
    as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_REVIEW_TIME_REQUIRED")
    prospect = _uuid(prospect_id, "PROSPECT_ID")
    entity = _uuid(entity_id, "ENTITY_ID")
    tenant = _uuid(authenticated_tenant_id, "AUTHENTICATED_TENANT_ID")
    if not callable(getattr(cursor, "execute", None)) or not callable(getattr(cursor, "fetchall", None)):
        raise ProspectHandoffHold("RESTRICTED_READER_CURSOR_REQUIRED")

    # This query does not mutate the database. The caller opens an explicit
    # READ ONLY transaction with a restricted login in the original CRM service.
    cursor.execute(
        """
        SELECT l.prospect_id, l.entity_id, l.match_method,
               l.evidence, l.active
        FROM public.prospect_entity_links AS l
        WHERE l.prospect_id=%s::uuid AND l.entity_id=%s::uuid
          AND l.active=true
        """, (prospect, entity),
    )
    links = cursor.fetchall()
    if len(links) != 1 or not isinstance(links[0], (tuple, list)) or len(links[0]) != 5:
        raise ProspectHandoffHold("EXACT_ACTIVE_PROSPECT_ENTITY_LINK_REQUIRED")
    row = links[0]
    if (str(row[0]) != prospect or str(row[1]) != entity
            or row[4] is not True
            or row[2] not in _ALLOWED_MATCH
            or not isinstance(row[3], dict)
            or not isinstance(row[3].get("source_ref"), str)
            or not 1 <= len(row[3]["source_ref"]) <= 500):
        raise ProspectHandoffHold("PROSPECT_ENTITY_SOURCE_MATCH_NOT_VERIFIED")

    # Name/website similarity is never enough; an unresolved identity conflict
    # must remain a hold rather than assigning another company's buyer scope.
    cursor.execute(
        """
        SELECT id FROM public.business_entity_conflicts
        WHERE prospect_id=%s::uuid AND entity_id=%s::uuid
          AND resolution_state!='resolved'
        LIMIT 2
        """, (prospect, entity),
    )
    if cursor.fetchall():
        raise ProspectHandoffHold("OPEN_IDENTITY_CONFLICT_HOLD")

    try:
        binding = resolve_tenant_entity_binding(
            cursor, tenant_id=tenant, entity_id=entity,
            as_of=as_of.astimezone(timezone.utc),
        )
    except TenantEntityBindingError as exc:
        raise ProspectHandoffHold("ACTIVE_TENANT_BUSINESS_BINDING_REQUIRED") from exc

    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "INJECTED_READER_CANONICAL_PROSPECT_AND_TENANT_BINDINGS_OBSERVED",
        "prospect_id": prospect, "entity_id": entity, "tenant_id": tenant,
        "prospect_entity_source_ref": row[3]["source_ref"],
        "tenant_entity_binding_ref": binding.binding_ref,
        "binding_kind": binding.binding_kind,
        "identity_conflict_absent_at_query_time": True,
        "query_time": as_of.astimezone(timezone.utc).isoformat(),
        "authenticated_reader_session_attested_by_this_module": False,
        "gtm_opportunity_link_verified": False,
        "buyer_acceptance_verified": False,
        "commercial_terms_authorized": False,
        "outbound_authorized": False,
        "database_writes": False,
        "payment_authorized": False,
        "execution_authority": "NONE",
    }


def review_signed_crm_prospect_tenant(
    *, signed_crm_bearer: str,
    crm_verifier: Any,
    dedicated_crm_dsn: str,
    prospect_id: str,
    entity_id: str,
    as_of: datetime,
    connect_factory: Any = None,
) -> dict[str, Any]:
    """Original signed tenant and PostgreSQL role-scoped READ ONLY path.

    This only proves source prospect -> entity -> tenant scope. It does NOT
    establish a canonical GTM opportunity/order/realised revenue; each needs
    its own independent owner-verification stage. Injected connectors in tests
    NEVER attest an independent real database.
    """
    from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
    from empire_os import revenue_crm_transport as crm_transport
    # The authenticated login contract is being upgraded by the CRM owner.
    # A role name alone cannot prove the dedicated-login privilege envelope.
    # Never import unpublished dirty production changes or bypass the guard.
    if not hasattr(crm_transport, 'CRM_LOGIN_AUTHORITY_SQL'):
        raise ProspectHandoffHold('ORIGINAL_CRM_LOGIN_ATTESTATION_UNRELEASED')
    CRM_LOGIN_AUTHORITY_SQL = crm_transport.CRM_LOGIN_AUTHORITY_SQL
    ROLE = crm_transport.ROLE

    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ProspectHandoffHold("ORIGINAL_SIGNED_CRM_VERIFIER_REQUIRED")
    if not isinstance(signed_crm_bearer, str) or not 1 <= len(signed_crm_bearer) <= 4096:
        raise ProspectHandoffHold("ORIGINAL_SIGNED_CRM_READ_TOKEN_REQUIRED")
    if not isinstance(dedicated_crm_dsn, str) or not dedicated_crm_dsn.strip():
        raise ProspectHandoffHold("DEDICATED_CRM_READER_REQUIRED")
    try:
        tenant = _uuid(crm_verifier.authenticate(signed_crm_bearer), "SIGNED_TENANT")
    except Exception:
        raise ProspectHandoffHold("SIGNED_CRM_MEMBERSHIP_NOT_VERIFIED") from None

    original_connector = connect_factory is None
    if original_connector:
        try:
            import psycopg
            connect_factory = psycopg.connect
        except ImportError as exc:
            raise ProspectHandoffHold("ORIGINAL_POSTGRES_CONNECTOR_UNAVAILABLE") from exc
    try:
        with connect_factory(dedicated_crm_dsn, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                cursor.execute(CRM_LOGIN_AUTHORITY_SQL)
                authority = cursor.fetchone()
                if (not isinstance(authority, (tuple, list))
                        or tuple(authority) != (True, False, False, False)):
                    raise ProspectHandoffHold("RESTRICTED_CRM_READER_ROLE_NOT_ATTESTED")
                cursor.execute("SET LOCAL ROLE " + ROLE)
                cursor.execute("SELECT public.empire_current_tenant_id()")
                row = cursor.fetchone()
                if (not isinstance(row, (tuple, list)) or len(row) != 1
                        or str(row[0]) != tenant):
                    raise ProspectHandoffHold("CRM_SESSION_TENANT_SCOPE_MISMATCH")
                result = review_existing_prospect_entity_tenant(
                    cursor, prospect_id=prospect_id, entity_id=entity_id,
                    authenticated_tenant_id=tenant, as_of=as_of,
                )
    except ProspectHandoffHold:
        raise
    except Exception:
        raise ProspectHandoffHold("ORIGINAL_CRM_READ_SESSION_UNAVAILABLE") from None

    result["signed_crm_active_membership_verified"] = True
    result["restricted_db_session_role_and_tenant_checked"] = True
    result["real_database_connector_independently_attested"] = original_connector
    result["status"] = (
        "ORIGINAL_CRM_READ_LINKS_OBSERVED_UNPROMOTED"
        if original_connector
        else "INJECTED_CONNECTOR_RESEARCH_ONLY"
    )
    return result
