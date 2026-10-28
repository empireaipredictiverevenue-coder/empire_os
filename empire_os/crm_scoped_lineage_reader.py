"""Tenant-safe, exact GTM event/order continuity for ORIGINAL Smart CRM.

This intentionally invokes only an owner-reviewed SECURITY DEFINER, tenant-
scoped RPC. CRM040 forbids exposing global prospect/entity/tenant tables to
the restricted CRM reader. No RPC migration is applied by this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold

FUNCTION_SIGNATURE = "public.empire_crm_exact_lineage(uuid,uuid,uuid,text)"
READ_SQL = (
    "SELECT prospect_id, entity_id, tenant_id, opportunity_id, evidence_id, evidence_kind, buyer_id "
    "FROM public.empire_crm_exact_lineage(%s::uuid,%s::uuid,%s::uuid,%s::text)"
)

def _id(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ProspectHandoffHold("INVALID_" + label)
    try:
        parsed=str(UUID(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProspectHandoffHold("INVALID_" + label) from exc
    if parsed!=value:
        raise ProspectHandoffHold("NON_CANONICAL_" + label)
    return parsed

def review_signed_scoped_lineage(*, signed_crm_bearer: str,
                                 crm_verifier: Any, dedicated_crm_dsn: str,
                                 prospect_id: str, opportunity_id: str,
                                 evidence_id: str, evidence_kind: str,
                                 as_of: datetime,
                                 connect_factory: Any = None) -> dict[str, Any]:
    """Never selects global source tables. Exact returned tenant must match
    signed active membership and original session_user-bound tenant resolver.

    Allows event / order only. Neither kind proves source rights, acceptance,
    fulfilment, net settlement or revenue. Injected connectors are test-only.
    """
    from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
    from empire_os import revenue_crm_transport as transport
    if evidence_kind not in ("event", "order"):
        raise ProspectHandoffHold("UNSUPPORTED_EXACT_LINEAGE_RECEIPT_KIND")
    prospect=_id(prospect_id,"PROSPECT_ID")
    opportunity=_id(opportunity_id,"OPPORTUNITY_ID")
    evidence=_id(evidence_id,"RECEIPT_ID")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ProspectHandoffHold("AWARE_REVIEW_TIME_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ProspectHandoffHold("ORIGINAL_SIGNED_CRM_VERIFIER_REQUIRED")
    if not isinstance(signed_crm_bearer,str) or not 1<=len(signed_crm_bearer)<=4096:
        raise ProspectHandoffHold("ORIGINAL_SIGNED_CRM_READ_TOKEN_REQUIRED")
    if not isinstance(dedicated_crm_dsn,str) or not dedicated_crm_dsn.strip():
        raise ProspectHandoffHold("DEDICATED_CRM_READER_REQUIRED")
    login_sql=getattr(transport,"CRM_LOGIN_AUTHORITY_SQL",None)
    if not isinstance(login_sql,str) or not login_sql.startswith("SELECT "):
        raise ProspectHandoffHold("ORIGINAL_CRM_LOGIN_ATTESTATION_UNRELEASED")
    try:
        signed_tenant=_id(crm_verifier.authenticate(signed_crm_bearer),"SIGNED_TENANT")
    except Exception:
        raise ProspectHandoffHold("SIGNED_CRM_MEMBERSHIP_NOT_VERIFIED") from None

    original=connect_factory is None
    if original:
        try:
            import psycopg
            connect_factory=psycopg.connect
        except ImportError as exc:
            raise ProspectHandoffHold("ORIGINAL_POSTGRES_CONNECTOR_UNAVAILABLE") from exc

    try:
        with connect_factory(dedicated_crm_dsn,connect_timeout=5) as con:
            with con.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                cursor.execute(login_sql)
                auth=cursor.fetchone()
                if (not isinstance(auth,(tuple,list))
                        or tuple(auth)!=(True,False,False,False)):
                    raise ProspectHandoffHold("RESTRICTED_CRM_READER_ROLE_NOT_ATTESTED")
                cursor.execute("SET LOCAL ROLE " + transport.ROLE)
                cursor.execute("SELECT public.empire_current_tenant_id()")
                scope=cursor.fetchone()
                if not isinstance(scope,(tuple,list)) or len(scope)!=1 or str(scope[0])!=signed_tenant:
                    raise ProspectHandoffHold("CRM_SESSION_TENANT_SCOPE_MISMATCH")
                cursor.execute(
                    """
                    SELECT p.prosecdef,p.provolatile,owner.rolname,
                      (COALESCE(p.proconfig,ARRAY[]::text[])
                       && ARRAY['search_path=', 'search_path=""']::text[])
                    FROM pg_catalog.pg_proc p
                    JOIN pg_catalog.pg_roles owner ON owner.oid=p.proowner
                    WHERE p.oid=pg_catalog.to_regprocedure(%s)
                    """, (FUNCTION_SIGNATURE,))
                provenance=cursor.fetchall()
                if not provenance:
                    raise ProspectHandoffHold("ORIGINAL_TENANT_SCOPED_RPC_NOT_RELEASED")
                if (not isinstance(provenance,list) or len(provenance)!=1
                        or not isinstance(provenance[0],(tuple,list))
                        or tuple(provenance[0]) !=
                        (True, "s", "empiredb_migrator", True)):
                    raise ProspectHandoffHold("UNTRUSTED_TENANT_SCOPED_RPC_PROVENANCE")
                cursor.execute(READ_SQL,(prospect,opportunity,evidence,evidence_kind))
                rows=cursor.fetchall()
                if (not isinstance(rows,list) or len(rows)!=1
                        or not isinstance(rows[0],(tuple,list)) or len(rows[0])!=7):
                    raise ProspectHandoffHold("ONE_EXACT_AUTHORIZED_LINEAGE_RECEIPT_REQUIRED")
                db_prospect,db_entity,db_tenant,db_opportunity,db_receipt,db_kind,db_buyer=rows[0]
                if (str(db_prospect)!=prospect or str(db_tenant)!=signed_tenant
                        or str(db_opportunity)!=opportunity or str(db_receipt)!=evidence
                        or db_kind!=evidence_kind):
                    raise ProspectHandoffHold("SCOPED_LINEAGE_RECEIPT_MISMATCH")
                entity=_id(str(db_entity),"ENTITY_ID")
                buyer=_id(str(db_buyer),"BUYER_ID")
    except ProspectHandoffHold:
        raise
    except Exception:
        raise ProspectHandoffHold("ORIGINAL_CRM_SCOPED_READ_UNAVAILABLE") from None

    return {
        "schema_version":"empire.crm.scoped_lineage_review.v1",
        "mode":"OBSERVE",
        "status":("EXACT_TENANT_SCOPED_RECEIPT_OBSERVED_NOT_PROMOTED"
                  if original else "INJECTED_SCOPED_RPC_TEST_ONLY"),
        "prospect_id":prospect,"entity_id":entity,"tenant_id":signed_tenant,
        "buyer_id":buyer,
        "opportunity_id":opportunity,"receipt_id":evidence,
        "receipt_kind":evidence_kind,
        "signed_crm_membership_verified":True,
        "original_db_tenant_scope_checked":True,
        "real_database_connector_used":original,
        "source_rights_verified":False,
        "buyer_terms_verified":False,
        "buyer_capacity_verified":False,
        "fulfilment_verified":False,
        "settlement_verified":False,
        "recognised_revenue_verified":False,
        "outbound_authorized":False,
        "database_writes":False,
        "execution_authority":"NONE",
    }
