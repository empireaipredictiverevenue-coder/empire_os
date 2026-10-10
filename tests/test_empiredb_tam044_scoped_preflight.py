"""TAM044 read-only production-catalog gate, ephemeral database contract."""
from pathlib import Path
import pytest
from test_empiredb_materializer_bootstrap import execute
from test_empiredb_tam_isolated_restricted_reader import isolated

PREFLIGHT=Path("scripts/preflight_empiredb_tam044.sql")
MIGRATION=Path("migrations/empiredb/044_tam_scoped_market_sampling.sql")


def test_preflight_passes_only_before_044_and_does_not_mutate_db(isolated):
    sql=PREFLIGHT.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in sql
    assert "ROLLBACK;" in sql
    assert "CREATE FUNCTION" not in sql
    assert "GRANT EXECUTE" not in sql
    assert "TAM044_SCOPED_READER_READ_ONLY_PREFLIGHT_PASS" in sql
    isolated("empiredb",sql)
    isolated("empiredb",MIGRATION.read_text())


def test_preflight_rejects_redeployment_after_044(isolated):
    isolated("empiredb",MIGRATION.read_text())
    isolated("empiredb",PREFLIGHT.read_text(),
      expected_error="TAM044_PREFLIGHT_SCOPED_FUNCTION_COLLISION")


def test_preflight_rejects_new_role_base_table_privilege(isolated):
    isolated("empiredb","""
    GRANT SELECT ON public.prospect_acquisitions TO empire_tam_market_reader;
    """)
    isolated("empiredb",PREFLIGHT.read_text(),
      expected_error="TAM044_PREFLIGHT_UNEXPECTED_SOURCE_TABLE_PRIVILEGE")


def test_preflight_rejects_prior_043_function_removed(isolated):
    isolated("empiredb","""
      SET ROLE empiredb_migrator;
      DROP FUNCTION public.get_tam_market_observations(integer);
      RESET ROLE;
    """)
    isolated("empiredb",PREFLIGHT.read_text(),
      expected_error="TAM044_PREFLIGHT_EXISTING_043_FUNCTION_UNVERIFIED")
