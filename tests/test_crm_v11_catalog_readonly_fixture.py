"""Run owner catalog audit only against the existing throwaway PG18 fixture."""

import json
from pathlib import Path

from tests.test_crm_scoped_lineage_sql_ephemeral import pg

AUDIT = Path(__file__).resolve().parents[1] / "docs/architecture/CRM_V11_OWNER_RELEASE_CATALOG_AUDIT_20261027.sql"


def test_owner_catalog_inventory_in_disposable_fixture(pg):
    output, _ = pg(file=AUDIT)
    docs = [json.loads(line) for line in output.splitlines()
            if line.startswith("{") and line.endswith("}")]
    assert len(docs) == 1
    obj = docs[0]
    assert obj["schema_version"] == "empire.crm.v11.catalog_release_audit.v1"
    assert obj["catalog_preflight_passed"] is True, obj
    assert obj["exact_rpc_present"] is True
    assert obj["security_definer"] is True
    assert obj["stable_function"] is True
    assert obj["owner_is_original_migrator"] is True
    assert obj["locked_empty_search_path"] is True
    assert obj["public_execute_present"] is False
    assert obj["original_reader_explicit_execute_granted"] is True
    assert obj["restricted_original_reader_role"] is True
    assert obj["original_tenant_resolver_present"] is True
    assert obj["restricted_reader_has_no_raw_table_select"] is True
    assert obj["owner_authorized"] is False
    assert obj["real_order_verified"] is False
    assert obj["production_release_authorized"] is False


def test_owner_audit_rejects_unlocked_search_path_in_disposable_db(pg):
    """Mutation is isolated to the temporary fixture and always reverted."""
    signature = "public.empire_crm_exact_lineage(uuid,uuid,uuid,text)"
    try:
        pg(sql=f"ALTER FUNCTION {signature} SET search_path TO public")
        output, _ = pg(file=AUDIT)
        records = [json.loads(line) for line in output.splitlines()
                   if line.startswith("{") and line.endswith("}")]
        assert len(records) == 1
        assert records[0]["exact_rpc_present"] is True
        assert records[0]["locked_empty_search_path"] is False
        assert records[0]["catalog_preflight_passed"] is False
        assert records[0]["production_release_authorized"] is False
    finally:
        pg(sql=f"ALTER FUNCTION {signature} SET search_path TO ''")
