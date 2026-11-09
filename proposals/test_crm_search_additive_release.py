"""Run against the unchanged deployed CRM plus isolated PostgreSQL."""
import sys, unittest
from pathlib import Path
W=Path(__file__).resolve().parents[1]
R=Path("/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1")
sys.path=[str(R),str(W/"proposals"),str(W/"tests")]+[p for p in sys.path if p and p!=str(W)]
from fastapi import FastAPI
from fastapi.testclient import TestClient
from empire_os import revenue_crm_api as api
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
from crm_search_additive_20261109.mount import attach_search_evidence
from test_crm_search_evidence_end_to_end import SearchEvidenceEndToEndTests
import test_crm_search_reader_ephemeral as fixture

class AdditiveReleaseTests(SearchEvidenceEndToEndTests):
    def client(self,login="crm_a",tenant=fixture.T,authenticated=True):
        repo=PostgresRevenueCrmRepository(
            f"host={self.sock} dbname=crm_search_fixture user={login}",tenant_id=tenant)
        access=api.AuthenticatedRevenueCrmRead(tenant,repo)
        resolver=lambda request: access if authenticated else None
        app=FastAPI()
        app.include_router(api.create_revenue_crm_router(resolve_authenticated_read=resolver))
        before=list(app.routes)
        attach_search_evidence(app,resolver)
        assert app.routes[:len(before)]==before
        return TestClient(app)
    def test_duplicate_mount_rejected(self):
        app=FastAPI()
        attach_search_evidence(app,lambda request: None)
        with self.assertRaisesRegex(RuntimeError,"already mounted"):
            attach_search_evidence(app,lambda request: None)

if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AdditiveReleaseTests))
    assert result.testsRun==21 and not result.skipped
    sys.exit(0 if result.wasSuccessful() else 1)
