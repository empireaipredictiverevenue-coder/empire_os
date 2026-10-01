"""Execute the role contract in a disposable, socket-free PostgreSQL cluster."""
from pathlib import Path
import subprocess

import pytest


BIN = Path('/usr/lib/postgresql/18/bin')


@pytest.fixture
def execute(tmp_path):
    if not (BIN / 'initdb').exists():
        pytest.skip('PostgreSQL 18 binaries unavailable')
    data = tmp_path / 'pgdata'
    init = subprocess.run([str(BIN / 'initdb'), '-D', str(data), '-A', 'trust', '--no-locale'], capture_output=True, text=True)
    assert init.returncode == 0, init.stderr

    def execute(database, sql, expected_error=None):
        # -j reads one complete multiline command per double newline.
        payload = '\n'.join(line for line in sql.splitlines() if line.strip()) + '\n\n'
        result = subprocess.run([str(BIN / 'postgres'), '--single', '-j', '-D', str(data), database],
                                input=payload, capture_output=True, text=True)
        assert result.returncode == 0
        assert 'FATAL:' not in result.stderr, result.stderr
        if expected_error is None:
            assert 'ERROR:' not in result.stderr, result.stderr
        else:
            assert expected_error in result.stderr, result.stderr
        return result.stdout

    return execute


def test_materializer_contract_enforces_append_only_and_identity_scope(execute):
    execute('postgres', 'CREATE DATABASE empiredb;')
    execute('empiredb', '''
      CREATE ROLE empiredb_app NOLOGIN;
      CREATE TABLE prospects(id uuid);
      CREATE TABLE prospect_entity_links(id uuid);
      CREATE TABLE prospect_qualifications(id uuid);
      CREATE TABLE business_entities(id uuid);
      CREATE TABLE intelligence_sources(id uuid, source_key text);
      CREATE TABLE intelligence_facts(entity_type text, entity_id uuid,
        fact_key text, fact_value jsonb, source_id uuid, evidence_hash text);
      CREATE TABLE intelligence_scores(entity_type text, entity_id uuid,
        score_type text, model_key text, scored_at timestamptz);
      CREATE TABLE intelligence_signals(entity_id uuid, signal_type text,
        signal_domain text, source_id uuid, payload jsonb);
    ''')
    contract = Path('deploy/empiredb/intelligence_materializer.sql').read_text()
    execute('empiredb', 'BEGIN;\n' + contract + '\nCOMMIT;')
    execute('empiredb', 'BEGIN;\n' + contract + '\nCOMMIT;')  # idempotent
    execute('empiredb', '''
      INSERT INTO intelligence_sources VALUES
        ('00000000-0000-0000-0000-000000000001','empire.prospect.canonical.v1');
      SET ROLE empire_intelligence_materializer;
      INSERT INTO intelligence_facts(entity_type,source_id,evidence_hash)
        VALUES ('company','00000000-0000-0000-0000-000000000001','test-evidence');
      INSERT INTO intelligence_scores(entity_type,score_type,model_key)
        VALUES ('company','lead_qualification','empire_os.lead_scoring:v2');
      DO $$ BEGIN
        BEGIN
          INSERT INTO intelligence_facts(entity_type,evidence_hash) VALUES ('person','wrong');
          RAISE EXCEPTION 'bad fact allowed' USING ERRCODE='23514';
        EXCEPTION WHEN raise_exception THEN NULL; END;
        BEGIN
          INSERT INTO intelligence_scores(entity_type,score_type,model_key)
            VALUES ('company','revenue','made-up');
          RAISE EXCEPTION 'bad score allowed' USING ERRCODE='23514';
        EXCEPTION WHEN raise_exception THEN NULL; END;
        BEGIN
          DELETE FROM intelligence_facts;
          RAISE EXCEPTION 'delete allowed';
        EXCEPTION WHEN insufficient_privilege THEN NULL; END;
        BEGIN
          INSERT INTO prospects VALUES (gen_random_uuid());
          RAISE EXCEPTION 'prospect write allowed';
        EXCEPTION WHEN insufficient_privilege THEN NULL; END;
        IF pg_has_role('empiredb_app','empire_intelligence_materializer','MEMBER') THEN
          RAISE EXCEPTION 'generic app inherited materializer';
        END IF;
      END $$;
    ''')


AUDIT_ERROR = 'PUBLIC authority audit required before materializer provisioning'


def public_authority_audit():
    contract = Path('deploy/empiredb/intelligence_materializer.sql').read_text()
    return contract[contract.index('-- A dedicated login cannot be least privilege'):]


def test_extension_owned_public_relation_passes_audit(execute):
    # Real extension membership in an isolated cluster; no production extensions
    # or names are needed, and no materializer role is provisioned by this test.
    execute('postgres', '''
      CREATE TABLE arbitrary_extension_relation(id integer);
      GRANT SELECT ON arbitrary_extension_relation TO PUBLIC;
      ALTER EXTENSION plpgsql ADD TABLE arbitrary_extension_relation;
    ''')
    execute('postgres', public_authority_audit())
    # Removing membership must restore fail-closed behavior immediately.
    execute('postgres', 'ALTER EXTENSION plpgsql DROP TABLE arbitrary_extension_relation;')
    execute('postgres', public_authority_audit(), expected_error=AUDIT_ERROR)


@pytest.mark.parametrize('privilege', ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'REFERENCES', 'TRIGGER', 'TRUNCATE'])
def test_non_extension_public_relation_blocks_audit(execute, privilege):
    execute('postgres', f'''
      CREATE TABLE ordinary_business_relation(id integer);
      GRANT {privilege} ON ordinary_business_relation TO PUBLIC;
    ''')
    execute('postgres', public_authority_audit(), expected_error=AUDIT_ERROR)


def test_extension_dependent_relation_without_membership_blocks_audit(execute):
    # A dependency on an extension member is not itself extension membership.
    execute('postgres', '''
      CREATE TABLE extension_base(id integer);
      ALTER EXTENSION plpgsql ADD TABLE extension_base;
      CREATE VIEW ordinary_view AS SELECT * FROM extension_base;
      GRANT SELECT ON ordinary_view TO PUBLIC;
    ''')
    execute('postgres', public_authority_audit(), expected_error=AUDIT_ERROR)


@pytest.mark.parametrize('extension_member', [False, True])
def test_public_security_definer_execute_still_blocks(execute, extension_member):
    execute('postgres', '''
      CREATE FUNCTION public.unexpected_definer() RETURNS integer
        LANGUAGE sql SECURITY DEFINER AS 'SELECT 1';
      GRANT EXECUTE ON FUNCTION public.unexpected_definer() TO PUBLIC;
    ''')
    if extension_member:
        execute('postgres', 'ALTER EXTENSION plpgsql ADD FUNCTION public.unexpected_definer();')
    execute('postgres', public_authority_audit(), expected_error=AUDIT_ERROR)
    execute('postgres', 'REVOKE EXECUTE ON FUNCTION public.unexpected_definer() FROM PUBLIC;')
    execute('postgres', public_authority_audit())


def test_security_definer_audit_contract_unchanged():
    assert public_authority_audit().split(') OR EXISTS (', 1)[1] == '''
    SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
      LATERAL aclexplode(COALESCE(p.proacl, acldefault('f',p.proowner))) a
    WHERE n.nspname='public' AND p.prosecdef AND a.grantee=0
      AND a.privilege_type='EXECUTE'
      AND p.proname NOT IN ('get_founder_commercial_funnel',
        'get_commercial_product_catalog','get_market_sweep_revenue_gps','get_revenue_pulse_window')
  ) THEN RAISE EXCEPTION 'PUBLIC authority audit required before materializer provisioning'; END IF;
END $$;
'''
