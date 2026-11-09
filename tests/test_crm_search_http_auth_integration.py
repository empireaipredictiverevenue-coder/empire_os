"""Run against the authenticated CRM owner branch with the mount patch applied."""
import copy
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from empire_os import revenue_crm_api as api
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

T,P,E,S,OTHER=[f'00000000-0000-0000-0000-{n:012d}' for n in range(1,6)]


@unittest.skipUnless(hasattr(api, 'AuthenticatedRevenueCrmRead'),
                     'Requires authenticated CRM owner branch and route mount')
class SearchHttpTests(unittest.TestCase):
    def setUp(self):
        self.repo=PostgresRevenueCrmRepository('fixture-only', tenant_id=T,
                                             connect_factory=lambda _: None)
        self.payload=dict(status='CONNECTED_NO_OBSERVATIONS', prospect_id=P,site_id=S,
                          entity_id=E,base_url='https://example.com',
                          binding_evidence_ref='fixture:binding',query='roofing',engine='fixture',
                          backlinks=[],citations=[],backlinks_truncated=False,citations_truncated=False)
        self.repo._fetch_all=Mock(side_effect=lambda *_:[dict(tenant_id=T,payload=copy.deepcopy(self.payload))])
        self.access=api.AuthenticatedRevenueCrmRead(T,self.repo)
        app=FastAPI()
        app.include_router(api.create_revenue_crm_router(resolve_authenticated_read=lambda _:self.access))
        self.client=TestClient(app)
        self.url=f'/v1/revenue-crm/prospects/{P}/search-growth'
        self.params=dict(site_id=S,query='roofing',engine='fixture')

    def get(self, **changes):
        return self.client.get(self.url,params=dict(self.params,**changes))

    def test_authenticated_empty_read_stays_unknown(self):
        r=self.get()
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['status'],'CONNECTED_NO_OBSERVATIONS')
        self.assertIsNone(r.json()['brief']['ai_visibility']['empire_cited'])
        self.assertEqual(self.repo._fetch_all.call_args.args[1],(P,S,'roofing','fixture',100))

    def test_missing_login_cannot_reach_reader(self):
        self.access=None
        self.assertEqual(self.get().status_code,401)
        self.repo._fetch_all.assert_not_called()

    def test_unavailable_database_is_sanitized(self):
        self.repo._fetch_all=Mock(side_effect=RuntimeError('SECRET fixture database detail'))
        r=self.get()
        self.assertEqual(r.status_code,503)
        self.assertNotIn('SECRET',r.text)

    def test_foreign_tenant_result_rejected(self):
        self.repo._fetch_all=Mock(return_value=[dict(tenant_id=OTHER,payload=self.payload)])
        self.assertEqual(self.get().status_code,503)

    def test_foreign_site_or_query_rejected(self):
        for key,value in [('site_id',OTHER),('query','other')]:
            original=self.payload[key]
            self.payload[key]=value
            self.assertEqual(self.get().status_code,503)
            self.payload[key]=original

    def test_not_connected_has_no_brief(self):
        self.payload={'status':'NOT_CONNECTED'}
        r=self.get()
        self.assertEqual(r.status_code,200)
        self.assertIsNone(r.json()['brief'])

    def test_invalid_limit_or_uuid_does_not_query(self):
        for params in [dict(limit=101),dict(site_id='invalid'),dict(query=' ')]:
            self.assertEqual(self.get(**params).status_code,422)
        self.repo._fetch_all.assert_not_called()

    def test_observed_citation_returns_existing_growth_brief(self):
        self.payload['status']='CONNECTED_OBSERVATIONS'
        self.payload['citations']=[dict(id=E,site_id=S,query='roofing',engine='fixture',
            cited_url='https://example.com/guide',observed_at='2026-10-25T12:00:00Z',
            provenance=['fixture:citation'])]
        r=self.get()
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(r.json()['brief']['ai_visibility']['empire_cited'])
        self.assertEqual(r.json()['brief']['evidence_count'],1)


if __name__=='__main__':
    unittest.main(verbosity=2)
