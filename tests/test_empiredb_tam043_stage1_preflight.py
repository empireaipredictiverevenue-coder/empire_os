"""Read-only stage-1 catalog preflight for held isolated TAM release.

Runs against an ephemeral PostgreSQL cluster. Never contacts live EmpireDB.
"""
from pathlib import Path

from test_empiredb_materializer_bootstrap import execute
from test_empiredb_tam_country_evidence_restricted_reader import SCHEMA

PREFLIGHT = Path("scripts/preflight_empiredb_tam043_stage1.sql")
BOOTSTRAP = Path("deploy/empiredb/tam_isolated_roles_bootstrap.sql")


def install_schema(db):
    db("postgres", "CREATE DATABASE empiredb;")
    db("empiredb", SCHEMA)
    db("empiredb", """
        GRANT SELECT ON public.prospect_entity_links,
            public.business_entities TO empire_intelligence_materializer;
    """)


def test_readonly_preflight_passes_before_held_release(execute):
    install_schema(execute)
    script = PREFLIGHT.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in script
    assert "ROLLBACK;" in script
    assert "CREATE ROLE" not in script
    assert "DROP ROLE" not in script
    assert "GRANT " not in script
    assert "INSERT INTO" not in script
    assert "DELETE FROM" not in script
    assert "TAM043_STAGE1_READ_ONLY_CATALOG_PREFLIGHT_PASS" in script
    execute("empiredb", script)


def test_readonly_preflight_rejects_already_present_tam_role(execute):
    install_schema(execute)
    execute("empiredb", BOOTSTRAP.read_text())
    execute(
        "empiredb", PREFLIGHT.read_text(),
        expected_error="TAM043_PRECHECK_ISOLATED_ROLE_COLLISION",
    )


def test_readonly_preflight_rejects_missing_live_column(execute):
    install_schema(execute)
    execute("empiredb", "ALTER TABLE public.business_entities DROP COLUMN canonical_niche;")
    execute(
        "empiredb", PREFLIGHT.read_text(),
        expected_error="TAM043_PRECHECK_SOURCE_COLUMN_CONTRACT_DRIFT",
    )


def test_readonly_preflight_rejects_old_materializer_grant_loss(execute):
    install_schema(execute)
    execute("empiredb", """
        REVOKE SELECT ON public.prospect_entity_links,
            public.business_entities FROM empire_intelligence_materializer;
    """)
    execute(
        "empiredb", PREFLIGHT.read_text(),
        expected_error="TAM043_PRECHECK_LEGACY_GRANTS_NOT_VERIFIED",
    )



def test_readonly_preflight_rejects_wrong_source_column_type(execute):
    install_schema(execute)
    execute("empiredb", """
        ALTER TABLE public.prospect_acquisitions
          ALTER COLUMN source_url TYPE integer USING NULL::integer;
    """)
    execute("empiredb",PREFLIGHT.read_text(),
            expected_error="TAM043_PRECHECK_SOURCE_COLUMN_CONTRACT_DRIFT")
