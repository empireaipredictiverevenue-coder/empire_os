"""Real PostgreSQL login checks using only a temporary Unix-socket cluster."""
from pathlib import Path
import getpass
import json
import subprocess
import tempfile
import unittest

BIN = Path('/usr/lib/postgresql/18/bin')
ROOT = Path(__file__).resolve().parents[1]
T, U, P, Q, E, F, S, Z = [f'00000000-0000-0000-0000-{n:012d}' for n in range(1,9)]


@unittest.skipUnless((BIN / 'initdb').exists(), 'PostgreSQL 18 required')
class SearchReaderPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='crm-search-pg-')
        cls.root = Path(cls.temp.name)
        cls.sock = cls.root / 'socket'
        cls.sock.mkdir(mode=0o700)
        cls.data = cls.root / 'data'
        subprocess.run([str(BIN/'initdb'), '-D', str(cls.data), '-A', 'trust',
                        '--no-locale', '-E', 'UTF8'], check=True,
                       capture_output=True, timeout=30)
        subprocess.run([str(BIN/'pg_ctl'), '-D', str(cls.data), '-l', str(cls.root/'pg.log'),
                        '-o', f"-c listen_addresses='' -k {cls.sock}", '-w', 'start'],
                       check=True, capture_output=True, timeout=30)
        cls.addClassCleanup(cls.cleanup)
        cls.sql('CREATE DATABASE crm_search_fixture', db='postgres')
        cls.sql(f"""
          CREATE ROLE empiredb_migrator NOLOGIN;
          CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT;
          CREATE ROLE crm_a LOGIN NOINHERIT;
          CREATE ROLE crm_b LOGIN NOINHERIT;
          CREATE ROLE crm_unbound LOGIN NOINHERIT;
          GRANT empire_revenue_crm_reader TO crm_a,crm_b,crm_unbound;
          GRANT CREATE ON SCHEMA public TO empiredb_migrator;
          SET ROLE empiredb_migrator;
          CREATE TABLE business_entities(id uuid PRIMARY KEY);
          CREATE TABLE seo_sites(id uuid PRIMARY KEY,tenant_key text,base_url text);
          CREATE TABLE prospect_entity_links(prospect_id uuid,entity_id uuid,active boolean,evidence jsonb);
          CREATE TABLE tenant_business_entity_bindings(
            tenant_id uuid,entity_id uuid,active boolean,binding_kind text,evidence_ref text,
            valid_from timestamptz,valid_until timestamptz);
          CREATE TABLE seo_backlink_observations(
            id uuid,site_id uuid,source_url text,target_url text,anchor_text text,rel text,
            source text,provenance jsonb,observed_at timestamptz);
          CREATE TABLE seo_ai_visibility_observations(
            id uuid,site_id uuid,query text,engine text,cited_url text,source_url text,
            citation_position integer,mention_text text,provenance jsonb,observed_at timestamptz);
          CREATE FUNCTION empire_current_tenant_id() RETURNS uuid LANGUAGE sql STABLE
            SECURITY DEFINER SET search_path='' AS $$
            SELECT CASE session_user WHEN 'crm_a' THEN '{T}'::uuid
                                     WHEN 'crm_b' THEN '{U}'::uuid ELSE NULL END $$;
          CREATE FUNCTION empire_crm_prospect_authorized(uuid) RETURNS boolean LANGUAGE sql STABLE
            SECURITY DEFINER SET search_path='' AS $$
            SELECT count(*)=1 FROM public.prospect_entity_links l
            JOIN public.tenant_business_entity_bindings b ON b.entity_id=l.entity_id
            WHERE l.prospect_id=$1 AND l.active AND l.evidence<>'{{}}'::jsonb
              AND b.tenant_id=public.empire_current_tenant_id() AND b.active
              AND b.binding_kind IN ('owned','managed','customer','prospect')
              AND length(btrim(b.evidence_ref))>0 AND b.valid_from<=CURRENT_TIMESTAMP
              AND (b.valid_until IS NULL OR b.valid_until>CURRENT_TIMESTAMP) $$;
          REVOKE ALL ON FUNCTION empire_current_tenant_id() FROM PUBLIC;
          REVOKE ALL ON FUNCTION empire_crm_prospect_authorized(uuid) FROM PUBLIC;
          INSERT INTO business_entities VALUES ('{E}'),('{F}');
          INSERT INTO seo_sites VALUES ('{S}','key-a','https://a.example'),('{Z}','key-b','https://b.example');
          INSERT INTO prospect_entity_links VALUES
            ('{P}','{E}',true,'{{"fixture":true}}'),('{Q}','{F}',true,'{{"fixture":true}}');
          INSERT INTO tenant_business_entity_bindings VALUES
            ('{T}','{E}',true,'owned','fixture:a',now()-interval '1 day',NULL),
            ('{U}','{F}',true,'owned','fixture:b',now()-interval '1 day',NULL);
        """)
        cls.sql((ROOT/'migrations/empiredb/proposals/crm_search_evidence_reader.sql').read_text())

    @classmethod
    def cleanup(cls):
        subprocess.run([str(BIN/'pg_ctl'), '-D', str(cls.data), '-m', 'immediate', '-w', 'stop'],
                       check=True, capture_output=True, timeout=30)
        cls.temp.cleanup()

    @classmethod
    def sql(cls, query, *, login=None, db='crm_search_fixture', error=False):
        r = subprocess.run([str(BIN/'psql'), '-X', '-Atq', '-v', 'ON_ERROR_STOP=1',
                            '-h', str(cls.sock), '-U', login or getpass.getuser(), '-d', db,
                            '-c', query], capture_output=True, text=True, timeout=15)
        if error:
            if r.returncode == 0:
                raise AssertionError('Expected rejection')
        elif r.returncode:
            raise AssertionError(r.stderr)
        return r.stdout.strip()

    def setUp(self):
        self.sql(f"""
          TRUNCATE crm_search_site_bindings,seo_backlink_observations,seo_ai_visibility_observations;
          UPDATE seo_sites SET base_url='https://a.example',tenant_key='key-a' WHERE id='{S}';
          UPDATE tenant_business_entity_bindings SET active=true;
          INSERT INTO crm_search_site_bindings VALUES
            ('{T}','{E}','{S}','key-a','https://a.example','fixture:binding-a',true,now()-interval '1 day',NULL),
            ('{U}','{F}','{Z}','key-b','https://b.example','fixture:binding-b',true,now()-interval '1 day',NULL);
        """)

    def read(self, login='crm_a', prospect=P, site=S, limit=100, prefix='', error=False):
        return self.sql(f"BEGIN READ ONLY; SET LOCAL ROLE empire_revenue_crm_reader; {prefix} "
                        f"SELECT payload FROM public.empire_crm_search_evidence('{prospect}','{site}',"
                        f"'roofing','fixture-engine',{limit}); ROLLBACK;", login=login, error=error)

    def test_connected_empty_is_distinct_from_unbound_site(self):
        self.assertEqual(json.loads(self.read())['status'], 'CONNECTED_NO_OBSERVATIONS')
        self.assertEqual(json.loads(self.read(site=Z))['status'], 'NOT_CONNECTED')
        self.assertEqual(json.loads(self.read('crm_b', Q, Z))['site_id'], Z)

    def test_cross_tenant_and_unbound_login_denied(self):
        self.read(prospect=Q, site=Z, error=True)
        self.read('crm_b', P, S, error=True)
        self.read('crm_unbound', error=True)

    def test_forged_tenant_settings_do_not_grant_access(self):
        self.read(prospect=Q, site=Z, prefix=f"SET LOCAL app.tenant_id='{U}'; SET LOCAL app.tenant_key='key-b';", error=True)

    def test_direct_table_access_and_binding_writes_denied(self):
        for table in ('crm_search_site_bindings','tenant_business_entity_bindings',
                      'seo_sites','seo_backlink_observations','seo_ai_visibility_observations'):
            self.sql(f'SET ROLE empire_revenue_crm_reader; SELECT * FROM {table}', login='crm_a', error=True)
        self.sql('SET ROLE empire_revenue_crm_reader; DELETE FROM crm_search_site_bindings', login='crm_a', error=True)

    def test_revocation_expiry_and_site_identity_drift(self):
        for statement in (f"UPDATE crm_search_site_bindings SET active=false WHERE site_id='{S}'",
                          f"UPDATE crm_search_site_bindings SET valid_until=now() WHERE site_id='{S}'",
                          f"UPDATE seo_sites SET base_url='https://changed.example' WHERE id='{S}'",
                          f"UPDATE seo_sites SET tenant_key='key-b' WHERE id='{S}'"):
            self.setUp()
            self.sql(statement)
            self.assertEqual(json.loads(self.read())['status'], 'NOT_CONNECTED')

    def test_revoked_crm_entity_scope_is_denied(self):
        self.sql(f"UPDATE tenant_business_entity_bindings SET active=false WHERE tenant_id='{T}'")
        self.read(error=True)

    def test_observations_scoped_and_truncation_explicit(self):
        self.sql(f"""
          INSERT INTO seo_backlink_observations VALUES
            ('{P}','{S}','https://source.example','https://a.example',NULL,NULL,'fixture','["fixture:1"]',now()),
            ('{Q}','{S}','https://source2.example','https://a.example',NULL,NULL,'fixture','["fixture:2"]',now()),
            ('{E}','{Z}','https://secret.example','https://b.example',NULL,NULL,'fixture','["fixture:foreign"]',now());
          INSERT INTO seo_ai_visibility_observations VALUES
            ('{P}','{S}','roofing','fixture-engine','https://a.example',NULL,1,NULL,'["fixture:c"]',now()),
            ('{Q}','{S}','different','fixture-engine','https://a.example',NULL,1,NULL,'["fixture:other"]',now());
        """)
        data=json.loads(self.read(limit=1))
        self.assertEqual(data['status'], 'CONNECTED_OBSERVATIONS')
        self.assertEqual(len(data['backlinks']), 1)
        self.assertTrue(data['backlinks_truncated'])
        self.assertFalse(data['citations_truncated'])
        self.assertEqual(len(data['citations']), 1)
        self.assertNotIn('foreign', json.dumps(data))
        self.assertNotIn('fixture:other', json.dumps(data))

    def test_invalid_limits_are_rejected(self):
        for limit in (0,101):
            self.read(limit=limit,error=True)

    def test_rls_filtering_raises_instead_of_claiming_empty_evidence(self):
        self.sql('ALTER TABLE seo_backlink_observations ENABLE ROW LEVEL SECURITY; '
                 'ALTER TABLE seo_backlink_observations FORCE ROW LEVEL SECURITY;')
        try:
            self.read(error=True)
        finally:
            self.sql('ALTER TABLE seo_backlink_observations NO FORCE ROW LEVEL SECURITY; '
                     'ALTER TABLE seo_backlink_observations DISABLE ROW LEVEL SECURITY;')

    def test_rollback_preserves_provisioned_bindings(self):
        rollback=(ROOT/'migrations/empiredb/proposals/crm_search_evidence_reader_rollback.sql').read_text()
        self.sql(rollback,error=True)
        self.assertEqual(json.loads(self.read())['status'], 'CONNECTED_NO_OBSERVATIONS')
        self.sql('TRUNCATE crm_search_site_bindings')
        self.sql(rollback)
        self.assertEqual(self.sql("SELECT to_regclass('public.crm_search_site_bindings') IS NULL"), 't')
        self.sql((ROOT/'migrations/empiredb/proposals/crm_search_evidence_reader.sql').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
