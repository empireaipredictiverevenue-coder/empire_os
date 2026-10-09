"""CRM source ownership graph inspection reads metadata only."""
from empire_os.revenue_crm_source_schema import REQUIRED, inspect_source_schema


class Catalog:
    def __init__(self, tables=None):
        self.tables = tables if tables is not None else {
            name: set(cols) for name, cols in REQUIRED.items()
        }
        self.active = None
        self.calls = []
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if "FROM pg_catalog.pg_class c" in sql:
            self.active = params[0]
        elif "FROM pg_catalog.pg_attribute" not in sql:
            raise AssertionError("must use catalog only")
    def fetchone(self):
        if self.active not in self.tables:
            return None
        return (31, "r", True)
    def fetchall(self):
        return [(v,) for v in sorted(self.tables[self.active])]


def test_complete_schema_still_does_not_verify_tenant_authority():
    cursor = Catalog()
    result = inspect_source_schema(cursor)
    assert result["status"] == "SOURCE_SCHEMA_PRESENT_EVIDENCE_PENDING"
    assert result["reason_codes"] == []
    assert result["tenant_binding_rows_verified"] is False
    assert result["unique_prospect_owner_verified"] is False
    assert result["activation_authorized"] is False
    assert result["customer_rows_read"] == 0
    assert len(cursor.calls) == 2 * len(REQUIRED)
    for sql, _ in cursor.calls:
        assert "pg_catalog" in sql
        assert "SELECT *" not in sql
        assert "FROM public.prospects" not in sql


def test_missing_link_table_reports_precise_blocker():
    fixture = {key:set(columns) for key,columns in REQUIRED.items()}
    fixture.pop("tenant_business_entity_bindings")
    report=inspect_source_schema(Catalog(fixture))
    assert report["status"]=="BLOCKED"
    assert report["sources"]["tenant_business_entity_bindings"]["present"] is False
    assert "SOURCE_TENANT_BUSINESS_ENTITY_BINDINGS_CONTRACT_MISSING" in report["reason_codes"]


def test_missing_buyer_ownership_column_blocks_design():
    fixture = {key:set(columns) for key,columns in REQUIRED.items()}
    fixture["buyers"].discard("org_id")
    report=inspect_source_schema(Catalog(fixture))
    assert report["status"]=="BLOCKED"
    assert report["sources"]["buyers"]["missing_column_names"]==["org_id"]
    assert "SOURCE_BUYERS_CONTRACT_MISSING" in report["reason_codes"]


def test_noncritical_data_shapes_report_missing_not_fabricate():
    fixture = {key:set(columns) for key,columns in REQUIRED.items()}
    fixture.pop("empire_conversations")
    report=inspect_source_schema(Catalog(fixture))
    assert report["status"]=="SOURCE_SCHEMA_PRESENT_EVIDENCE_PENDING"
    assert report["sources"]["empire_conversations"]["present"] is False
    assert report["public_api_activation_authorized"] is False
