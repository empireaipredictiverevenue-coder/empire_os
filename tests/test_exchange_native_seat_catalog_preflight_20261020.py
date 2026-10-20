"""Fail-closed static checks: isolated SQL preflight must query only catalog."""
from pathlib import Path
import re
import pytest

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"docs/commercial/sql/EXCHANGE_NATIVE_SEAT_ROLE_PREFLIGHT_READONLY_20261020.sql"

def test_preflight_readonly_canonical_catalog_only():
    sql=SQL.read_text()
    assert sql.count("BEGIN TRANSACTION READ ONLY")==1
    assert "SET LOCAL statement_timeout = '5s'" in sql
    assert "SET LOCAL lock_timeout = '1s'" in sql
    assert sql.count("ROLLBACK;")==1
    assert not re.search(r"\b(COMMIT|INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER TABLE|CREATE TABLE|GRANT|REVOKE)\s+",re.sub(r"--[^\n]*","",sql),re.I)
    for attr in ("current_database()","pg_catalog.pg_class","pg_catalog.pg_attribute",
                 "pg_catalog.pg_roles","pg_catalog.pg_namespace","pg_catalog.to_regclass"):
        assert attr in sql
    assert "SELECT * FROM public." not in sql
    assert "JOIN public.buyers" not in sql
    assert "FROM public.bsc_payment_evidence" not in sql
    assert "FROM public.bsc_payment_requests" not in sql

def test_audit_does_not_misrepresent_privileges_or_revenue():
    sql=SQL.read_text()
    for s in (
        "'finance_role_reader_grants_proven',false",
        "'tenant_rls_identity_proven',false",
        "'settlement_authenticated',false",
        "'entitlement_activation_authorized',false",
        "'schema_migration_authorized',false",
        "'proposed_exchange_seat_finance_role_already_exists'",
        "'native_required_source_columns_all_exist'",
        "'missing_required_column_names'",
    ):
        assert s in sql

def test_source_columns_exact_approved_tables():
    sql=SQL.read_text()
    pairs=re.findall(r"\('([a-z_]+)','([a-z_]+)'\)",sql.split("), inspected AS (")[0])
    assert pairs
    assert len(pairs)==len(set(pairs))
    assert {table for table,column in pairs}=={
        "buyers","fulfilment_orders","bsc_payment_requests","bsc_payment_evidence"
    }
    assert all(re.fullmatch(r"[a-z_]+",table) and re.fullmatch(r"[a-z_]+",col)
               for table,col in pairs)
