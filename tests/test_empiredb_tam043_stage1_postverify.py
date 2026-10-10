"""TAM 043 staged post-install verification; disposable PostgreSQL only."""
from pathlib import Path

from test_empiredb_materializer_bootstrap import execute
from test_empiredb_tam_country_evidence_restricted_reader import SCHEMA
from test_empiredb_tam_isolated_restricted_reader import BOOTSTRAP, MIGRATION

VERIFY=Path("scripts/verify_empiredb_tam043_stage1.sql")


def setup_schema(execute):
    execute("postgres","CREATE DATABASE empiredb;")
    execute("empiredb",SCHEMA)
    execute("empiredb","""
    GRANT SELECT ON public.prospect_entity_links,public.business_entities
      TO empire_intelligence_materializer;
    """)


def test_postrelease_read_only_catalog_passes_only_with_dormant_roles(execute):
    setup_schema(execute)
    sql=VERIFY.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in sql
    assert "ROLLBACK;" in sql
    assert "DROP ROLE" not in sql
    assert "CREATE ROLE" not in sql
    assert "GRANT " not in sql
    assert "DELETE FROM" not in sql
    execute("empiredb",BOOTSTRAP.read_text())
    execute("empiredb",MIGRATION.read_text())
    execute("empiredb",sql)


def test_postrelease_catalog_rejects_unapplied_migration(execute):
    setup_schema(execute)
    execute("empiredb",VERIFY.read_text(),
            expected_error="TAM043_POST_ROLES_NOT_DORMANT_NOLOGIN_NULL_PASSWORD")


def test_postrelease_catalog_rejects_activated_login(execute):
    setup_schema(execute)
    execute("empiredb",BOOTSTRAP.read_text())
    execute("empiredb",MIGRATION.read_text())
    execute("empiredb","ALTER ROLE empire_tam_market_login LOGIN;")
    execute("empiredb",VERIFY.read_text(),
            expected_error="TAM043_POST_ROLES_NOT_DORMANT_NOLOGIN_NULL_PASSWORD")


def test_postrelease_catalog_rejects_legacy_privilege_loss(execute):
    setup_schema(execute)
    execute("empiredb",BOOTSTRAP.read_text())
    execute("empiredb",MIGRATION.read_text())
    execute("empiredb","""
      REVOKE SELECT ON public.prospect_entity_links,public.business_entities
      FROM empire_intelligence_materializer;
    """)
    execute("empiredb",VERIFY.read_text(),
            expected_error="TAM043_POST_LEGACY_MATERIALIZER_GRANTS_CHANGED")



def test_postrelease_catalog_rejects_function_search_path_drift(execute):
    setup_schema(execute)
    execute("empiredb",BOOTSTRAP.read_text())
    execute("empiredb",MIGRATION.read_text())
    execute("empiredb","""
       SET ROLE empiredb_migrator;
       ALTER FUNCTION public.get_tam_market_observations(integer)
         SET search_path TO public;
       RESET ROLE;
    """)
    execute("empiredb",VERIFY.read_text(),
            expected_error="TAM043_POST_FUNCTION_CONTRACT_INVALID")


def test_postrelease_catalog_rejects_public_rpc_execute(execute):
    setup_schema(execute)
    execute("empiredb",BOOTSTRAP.read_text())
    execute("empiredb",MIGRATION.read_text())
    execute("empiredb","""
       SET ROLE empiredb_migrator;
       GRANT EXECUTE ON FUNCTION
         public.get_tam_market_observations(integer) TO PUBLIC;
       RESET ROLE;
    """)
    execute("empiredb",VERIFY.read_text(),
            expected_error="TAM043_POST_FUNCTION_EXECUTE_PRIVILEGES_UNSAFE")
