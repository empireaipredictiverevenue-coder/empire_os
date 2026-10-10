"""TAM044 postrelease verification: catalog only, disposal database tests."""
from pathlib import Path

from test_empiredb_materializer_bootstrap import execute
from test_empiredb_tam_isolated_restricted_reader import isolated

MIGRATION=Path("migrations/empiredb/044_tam_scoped_market_sampling.sql")
VERIFY=Path("scripts/verify_empiredb_tam044.sql")


def test_044_postverify_passes_only_after_scoped_release(isolated):
    script=VERIFY.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in script
    assert "ROLLBACK;" in script
    assert "CREATE FUNCTION" not in script
    assert "GRANT EXECUTE" not in script
    isolated("empiredb",MIGRATION.read_text())
    isolated("empiredb",script)


def test_044_postverify_rejects_missing_function(isolated):
    isolated("empiredb",VERIFY.read_text(),
        expected_error="TAM044_POST_SCOPED_FUNCTION_SECURITY_UNVERIFIED")


def test_044_postverify_rejects_unsafe_search_path(isolated):
    isolated("empiredb",MIGRATION.read_text())
    isolated("empiredb","""
       SET ROLE empiredb_migrator;
       ALTER FUNCTION public.get_tam_market_observations_scoped(
         text[],text[],integer
       ) SET search_path TO public;
       RESET ROLE;
    """)
    isolated("empiredb",VERIFY.read_text(),
        expected_error="TAM044_POST_SCOPED_FUNCTION_SECURITY_UNVERIFIED")


def test_044_postverify_rejects_public_execute(isolated):
    isolated("empiredb",MIGRATION.read_text())
    isolated("empiredb","""
      SET ROLE empiredb_migrator;
      GRANT EXECUTE ON FUNCTION
        public.get_tam_market_observations_scoped(text[],text[],integer)
      TO PUBLIC;
      RESET ROLE;
    """)
    isolated("empiredb",VERIFY.read_text(),
        expected_error="TAM044_POST_SCOPED_FUNCTION_EXECUTE_UNSAFE")
