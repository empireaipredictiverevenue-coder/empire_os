"""HTTP -> real CRM transport -> temporary PostgreSQL; no production DSN."""
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from empire_os import revenue_crm_api as api
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
import test_crm_search_reader_ephemeral as fixture


@unittest.skipUnless(hasattr(api, "AuthenticatedRevenueCrmRead"),
                     "Requires the authenticated CRM owner branch")
class SearchEvidenceEndToEndTests(fixture.SearchReaderPostgresTests):
    def client(self, login="crm_a", tenant=fixture.T, authenticated=True):
        repo = PostgresRevenueCrmRepository(
            f"host={self.sock} dbname=crm_search_fixture user={login}",
            tenant_id=tenant,
        )
        access = api.AuthenticatedRevenueCrmRead(tenant, repo)
        app = FastAPI()
        app.include_router(api.create_revenue_crm_router(
            resolve_authenticated_read=lambda request: access if authenticated else None,
        ))
        return TestClient(app)

    def request(self, client, prospect=fixture.P, site=fixture.S):
        return client.get(f"/v1/revenue-crm/prospects/{prospect}/search-growth",
                          params={"site_id": site, "query": "roofing", "engine": "fixture-engine"})

    def test_http_real_stored_evidence_and_revocation(self):
        self.sql(f"""
          INSERT INTO seo_ai_visibility_observations VALUES
            ('{fixture.P}','{fixture.S}','roofing','fixture-engine','https://a.example/guide',
             NULL,1,NULL,ARRAY['fixture:real-db-citation'],now());
        """)
        with self.client() as client:
            response = self.request(client)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["status"], "CONNECTED_OBSERVATIONS")
            self.assertTrue(body["brief"]["ai_visibility"]["empire_cited"])
            self.assertEqual(body["brief"]["evidence_count"], 1)
            self.assertEqual(body["brief"]["evidence_refs"], ["fixture:real-db-citation"])
            self.sql(f"UPDATE crm_search_site_bindings SET active=false WHERE site_id='{fixture.S}'")
            after = self.request(client)
            self.assertEqual(after.status_code, 200, after.text)
            self.assertEqual(after.json()["status"], "NOT_CONNECTED")
            self.assertIsNone(after.json()["brief"])

    def test_http_tenant_b_receives_only_own_scope(self):
        with self.client("crm_b", fixture.U) as client:
            own = self.request(client, fixture.Q, fixture.Z)
            self.assertEqual(own.status_code, 200, own.text)
            self.assertEqual(own.json()["site_id"], fixture.Z)
            foreign = self.request(client)
            self.assertEqual(foreign.status_code, 503, foreign.text)
            self.assertEqual(foreign.json()["detail"],
                             "authenticated_crm_search_evidence_unavailable")

    def test_http_session_tenant_mismatch_fails(self):
        with self.client("crm_b", fixture.T) as client:
            self.assertEqual(self.request(client).status_code, 503)

    def test_http_without_login_is_unauthorized(self):
        with self.client(authenticated=False) as client:
            self.assertEqual(self.request(client).status_code, 401)

    def test_http_missing_source_privilege_is_not_empty_success(self):
        self.sql("REVOKE SELECT ON seo_ai_visibility_observations FROM empiredb_migrator")
        try:
            with self.client() as client:
                response = self.request(client)
                self.assertEqual(response.status_code, 503, response.text)
                self.assertNotIn("permission", response.text.lower())
        finally:
            self.sql("GRANT SELECT ON seo_ai_visibility_observations TO empiredb_migrator")


if __name__ == "__main__":
    unittest.main(verbosity=2)
