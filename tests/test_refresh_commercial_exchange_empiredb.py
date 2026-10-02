from empire_os.data_cloud_contract import DataBackend
from empire_os.canonical_data_gateway import GatewaySnapshot
from empire_os.data_query import FilterOperator
from scripts import refresh_commercial_exchange as module


class FakeGateway:
    def __init__(self):
        self.calls=[]
        self.qualification_calls=0
    def snapshot(self):
        return GatewaySnapshot(primary_backend=DataBackend.EMPIREDB, configured=True)
    def query(self, table, columns='*', *, filters=(), order=(), limit=1000, offset=0):
        self.calls.append((table,columns,filters,order,limit,offset))
        if table=='prospect_qualifications':
            self.qualification_calls += 1
            if self.qualification_calls == 1:
                return [{'prospect_id':'p1','evidence_confidence':0.60,'scored_at':'2026-10-01T00:00:00Z'}]
            return [{'id':'q1','prospect_id':'p1','entity_id':'e1','score':80,'tier':'hot','status':'scored','scoring_engine':'empire_os.lead_scoring','scoring_version':'v2','evidence_confidence':0.60,'observed_dimensions':{},'unknown_dimensions':[], 'scored_at':'2026-10-01T00:00:00Z'}]
        if table=='prospects':
            return [{'id':'p1','business_name':'A','niche':'roofing','metro':'Austin, TX','created_at':'2026-01-01T00:00:00Z','status':'active'}]
        if table=='prospect_entity_links':
            return [{'prospect_id':'p1','entity_id':'e1','match_score':1.0,'active':True,'created_at':'2026-10-01T00:00:00Z'}]
        if table=='buyers':
            return []
        if table=='fulfilment_orders':
            return []
        raise AssertionError(table)


def test_empiredb_projection_is_driven_by_qualified_supply_not_raw_recency():
    gateway=FakeGateway()
    snapshot=module.build_runtime_snapshot(gateway,limit=200)
    tables=[call[0] for call in gateway.calls]
    assert tables==['prospect_qualifications','prospects','prospect_qualifications','prospect_entity_links','buyers','fulfilment_orders']
    first=gateway.calls[0]
    filters=first[2]
    assert any(item.column=='status' and item.value=='scored' for item in filters)
    assert any(item.column=='tier' and item.operator is FilterOperator.IN for item in filters)
    assert any(item.column=='evidence_confidence' and item.operator is FilterOperator.GTE and item.value==module.MIN_DECISION_CONFIDENCE for item in filters)
    assert snapshot['source']=='canonical_empiredb_projection'
    assert snapshot['canonical_backend']=='empiredb'
    assert snapshot['candidate_selection']=='qualification_driven'
    assert snapshot['qualified_candidates_selected']==1
    assert snapshot['qualified_v2_candidates_selected']==1
    assert snapshot['qualified_v1_fallback_candidates_selected']==0
    assert snapshot['prospects_scanned']==1
    assert snapshot['qualification_rows_available']==1
    assert snapshot['identity_links_available']==1
    assert snapshot['execution_authority']=='none'
    assert snapshot['automatic_external_delivery'] is False


def test_qualified_candidate_order_and_dedup_are_deterministic():
    class G(FakeGateway):
        def query(self, table, columns='*', *, filters=(), order=(), limit=1000, offset=0):
            if table=='prospect_qualifications':
                return [
                    {'prospect_id':'p2','evidence_confidence':0.8},
                    {'prospect_id':'p2','evidence_confidence':0.7},
                    {'prospect_id':'p1','evidence_confidence':0.6},
                ]
            return super().query(table,columns,filters=filters,order=order,limit=limit,offset=offset)
    g=G()
    assert module.fetch_qualified_candidate_ids(g,200)==['p2','p1']


def test_qualification_prefers_v2_and_identity_ambiguity_fails_closed():
    class G(FakeGateway):
        def query(self, table, columns='*', *, filters=(), order=(), limit=1000, offset=0):
            if table=='prospect_qualifications':
                return [
                    {'prospect_id':'p1','scoring_version':'v1'},
                    {'prospect_id':'p1','scoring_version':'v2'},
                ]
            if table=='prospect_entity_links':
                return [
                    {'prospect_id':'p1','entity_id':'e1'},
                    {'prospect_id':'p1','entity_id':'e2'},
                ]
            return super().query(table,columns,filters=filters,order=order,limit=limit,offset=offset)
    g=G()
    assert module.fetch_qualification_map(g,['p1'])['p1']['scoring_version']=='v2'
    assert module.fetch_identity_map(g,['p1'])['p1'] is None


def test_empty_ids_do_not_issue_dependent_queries():
    g=FakeGateway()
    assert module.fetch_prospects_by_ids(g,[])==[]
    assert module.fetch_qualification_map(g,[])=={}
    assert module.fetch_identity_map(g,[])=={}
    assert module.fetch_allocated_prospect_ids(g,[])==set()
    assert g.calls==[]
