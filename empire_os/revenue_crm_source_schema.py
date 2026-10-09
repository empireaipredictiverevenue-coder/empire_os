"""Read-only metadata inspection for CRM tenant-link graph. No business-row reads."""
from __future__ import annotations
from typing import Any

REQUIRED = {
 "prospects": ("id", "business_name", "niche", "metro", "status"),
 "buyers": ("id", "org_id", "buyer_name", "status"),
 "prospect_entity_links": ("prospect_id", "entity_id", "active"),
 "tenant_business_entity_bindings": (
   "tenant_id", "entity_id", "binding_kind", "active",
   "valid_from", "valid_until", "evidence_ref"),
 "empire_conversations": ("id", "prospect_id", "channel", "state"),
 "closer_cases": ("id", "prospect_id"),
 "fulfilment_orders": ("id", "buyer_id"),
}
MANDATORY = ("prospects", "buyers", "prospect_entity_links", "tenant_business_entity_bindings")

def inspect_source_schema(cursor: Any) -> dict:
    sources = {}
    reasons = []
    for table, needed in REQUIRED.items():
        cursor.execute(
            "SELECT c.oid,c.relkind,c.relrowsecurity FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=%s", (table,))
        row = cursor.fetchone()
        present = bool(row and row[1] in ("r", "p"))
        observed = set()
        if present:
            cursor.execute(
                "SELECT attname FROM pg_catalog.pg_attribute "
                "WHERE attrelid=%s AND attnum>0 AND NOT attisdropped", (row[0],))
            observed = {str(r[0]) for r in cursor.fetchall()}
        missing = sorted(set(needed) - observed)
        sources[table] = {
            "present": present, "required_columns_present": not missing,
            "missing_column_names": missing,
            "row_level_security_enabled": bool(row and row[2] is True),
        }
        if table in MANDATORY and (not present or missing):
            reasons.append("SOURCE_" + table.upper() + "_CONTRACT_MISSING")
    return {
       "schema": "empire.crm_source_schema_metadata.v1",
       "status": "SOURCE_SCHEMA_PRESENT_EVIDENCE_PENDING" if not reasons else "BLOCKED",
       "reason_codes": reasons,
       "sources": sources,
       "tenant_binding_rows_verified": False,
       "unique_prospect_owner_verified": False,
       "role_permissions_verified": False,
       "read_only": True,
       "customer_rows_read": 0,
       "activation_authorized": False,
       "public_api_activation_authorized": False,
       "execution_authority": "none",
    }
