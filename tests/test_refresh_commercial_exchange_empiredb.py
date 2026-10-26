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
        if table=='commercial_evidence_registry':
            return []
        if table=='intelligence_scores':
            return []
        raise AssertionError(table)


def test_empiredb_projection_is_driven_by_qualified_supply_not_raw_recency():
    gateway=FakeGateway()
    snapshot=module.build_runtime_snapshot(gateway,limit=200)
    tables=[call[0] for call in gateway.calls]
    assert tables==['prospect_qualifications','prospects','prospect_qualifications','prospect_entity_links','buyers','fulfilment_orders','commercial_evidence_registry','intelligence_scores']
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


def test_verified_market_prices_include_only_valid_verified_per_lead_evidence():
    class G(FakeGateway):
        def query(self, table, columns='*', *, filters=(), order=(), limit=1000, offset=0):
            if table=='commercial_evidence_registry':
                self.calls.append((table,columns,filters,order,limit,offset))
                return [
                    {'id':'e1','evidence_kind':'price','niche':'roofing','metro':'Austin, TX','amount_cents':12500,'currency':'USD','unit':'per_lead','source_type':'buyer_stated','source_reference':'reply:r1:price','status':'verified','observed_at':'2026-10-01T09:00:00Z','valid_until':None,'verified_at':'2026-10-01T09:01:00Z'},
                    {'id':'e2','evidence_kind':'price','niche':'roofing','metro':'Austin, TX','amount_cents':99900,'currency':'USD','unit':'per_month','source_type':'founder_approved','source_reference':'catalog:x','status':'verified','observed_at':'2026-10-01T09:00:00Z','valid_until':None,'verified_at':'2026-10-01T09:01:00Z'},
                    {'id':'e3','evidence_kind':'price','niche':'roofing','metro':'Austin, TX','amount_cents':15000,'currency':'USD','unit':'per_lead','source_type':'buyer_stated','source_reference':'reply:r3:price','status':'pending','observed_at':'2026-10-01T09:00:00Z','valid_until':None,'verified_at':None},
                    {'id':'e4','evidence_kind':'price','niche':'roofing','metro':'Austin, TX','amount_cents':14000,'currency':'USD','unit':'per_lead','source_type':'buyer_stated','source_reference':'reply:r4:price','status':'verified','observed_at':'2026-09-01T09:00:00Z','valid_until':'2026-09-30T00:00:00Z','verified_at':'2026-09-01T09:01:00Z'},
                ]
            return super().query(table,columns,filters=filters,order=order,limit=limit,offset=offset)
    rows=module.fetch_verified_market_prices(
        G(), observed_at=__import__('datetime').datetime(2026,10,2,tzinfo=__import__('datetime').timezone.utc)
    )
    assert rows==[{
        'evidence_id':'e1','niche':'roofing','metro':'Austin, TX','amount_cents':12500,
        'currency':'USD','unit':'per_lead','source_type':'buyer_stated',
        'source_reference':'reply:r1:price','observed_at':'2026-10-01T09:00:00Z',
        'valid_until':None,'verified_at':'2026-10-01T09:01:00Z',
        'evidence_ref':'commercial_evidence:e1',
    }]


def test_runtime_snapshot_never_promotes_buyer_observed_rate_to_verified_price():
    gateway=FakeGateway()
    snapshot=module.build_runtime_snapshot(gateway,limit=200)
    assert snapshot['verified_market_prices']==[]
    assert snapshot['verified_market_price_count']==0
    assert snapshot['commercial_price_source']=='canonical_empiredb_commercial_evidence_registry'


def test_omega_canonical_scoring_overlay_accepts_only_exact_v2_identity_evidence():
    from empire_os.intelligence.omega import MODEL_VERSION
    from empire_os.omega_worker import SCORE_TYPE

    class OmegaGateway(FakeGateway):
        def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
            if table == "intelligence_scores":
                return [
                    {
                        "id": "score-wrong", "entity_type": "company", "entity_id": "other",
                        "score_type": SCORE_TYPE, "model_key": MODEL_VERSION,
                        "score": 95, "confidence": .6,
                        "features": {"prospect_id": "p1", "qualification_id": "q1",
                                     "evaluation_grade": "A"},
                    },
                    {
                        "id": "score-good", "entity_type": "company", "entity_id": "e1",
                        "score_type": SCORE_TYPE, "model_key": MODEL_VERSION,
                        "score": 72, "confidence": .6,
                        "features": {"prospect_id": "p1", "qualification_id": "q1",
                                     "evaluation_grade": "B"},
                    },
                ]
            return super().query(
                table, columns, filters=filters, order=order,
                limit=limit, offset=offset,
            )
    snapshot = module.build_runtime_snapshot(OmegaGateway(), limit=20)
    overlay = snapshot["inventory"][0]["omega_evidence"]
    assert overlay["score"] == 72
    assert overlay["evaluation_grade"] == "B"
    assert overlay["evidence_ref"] == "canonical:intelligence_scores:score-good"
    assert snapshot["omega_scoring"]["scores_with_exact_qualification_and_identity"] == 1
    assert snapshot["omega_scoring"]["changes_inventory_eligibility"] is False
    assert snapshot["allocation_candidate_count"] == 0


def test_missing_omega_data_is_unknown_not_zero_and_does_not_block_exchange():
    snapshot = module.build_runtime_snapshot(FakeGateway(), limit=20)
    assert snapshot["omega_scoring"]["state"] == "CANONICAL_SCORE_JOIN_AVAILABLE"
    assert snapshot["omega_scoring"]["scores_with_exact_qualification_and_identity"] == 0
    assert "omega_evidence" not in snapshot["inventory"][0]
    assert snapshot["omega_scoring"]["missing_or_unverified_is_not_zero_score"]


def test_stale_omega_qualification_id_is_rejected():
    from empire_os.intelligence.omega import MODEL_VERSION
    class G:
        def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
            return [{
                "id": "s1", "entity_type": "company", "entity_id": "e1",
                "score_type": "omega_opportunity", "model_key": MODEL_VERSION,
                "score": 80, "confidence": .75,
                "features": {"prospect_id": "p1", "qualification_id": "OLD"},
            }]
    rows = module.fetch_verified_omega_projection_map(
        G(),
        qualifications={"p1": {
            "id": "q1", "entity_id": "e1",
            "scoring_version": "v2", "status": "scored",
            "evidence_confidence": .75,
        }},
        identity_links={"p1": {
            "entity_id": "e1", "prospect_id": "p1", "active": True,
        }},
    )
    assert rows == {}


def test_omega_reader_failure_does_not_block_exchange():
    class NoScoreGrant(FakeGateway):
        def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
            if table == "intelligence_scores":
                raise RuntimeError("score projection inaccessible")
            return super().query(
                table, columns, filters=filters, order=order, limit=limit, offset=offset,
            )
    snapshot = module.build_runtime_snapshot(NoScoreGrant(), limit=20)
    assert snapshot["inventory_count"] == 1
    assert snapshot["omega_scoring"]["state"] == "CANONICAL_SCORE_JOIN_UNAVAILABLE"
    assert snapshot["omega_scoring"]["scores_with_exact_qualification_and_identity"] == 0
    assert snapshot["automatic_external_delivery"] is False


def test_population_census_counts_full_version_scoped_cohort_not_display_window():
    class CountGateway:
        def count(self, table, filters=None):
            if table == "prospects":
                return 32940
            assert table == "prospect_qualifications"
            assert filters["scoring_engine"] == "empire_os.lead_scoring"
            assert filters["scoring_version"] == "v2"
            return {
                (None, None): 3190,
                ("scored", None): 3190,
                ("scored", "hot"): 175,
                ("scored", "warm"): 50,
                ("scored", "insufficient_evidence"): 2965,
            }[(filters.get("status"), filters.get("tier"))]
    result = module.read_qualification_population_counts(CountGateway())
    assert result["state"] == "CANONICAL_COUNT_AVAILABLE"
    assert result["canonical_prospect_total"] == 32940
    assert result["v2_scored_prospect_total"] == 3190
    assert result["v2_qualification_record_total"] == 3190
    assert result["prospects_without_v2_record"] == 29750
    assert result["v2_hot_tier_total"] == 175
    assert result["v2_warm_tier_total"] == 50
    assert result["saleable_prospect_count"] is None
    assert result["independent_count_queries_not_atomic_snapshot"] is True


def test_population_count_unavailable_never_fabricates_zero_or_blocks_inventory():
    class Denied(FakeGateway):
        def count(self, table, filters=None):
            raise PermissionError("no aggregate reader")
    snapshot = module.build_runtime_snapshot(Denied(), limit=1)
    assert snapshot["inventory_count"] == 1
    assert snapshot["selection_window"]["limit_reached"] is True
    assert snapshot["qualification_population_census"]["state"] == "COUNT_UNAVAILABLE"
    assert snapshot["qualification_population_census"]["v2_scored_prospect_total"] is None
    assert snapshot["qualification_population_census"]["saleable_prospect_count"] is None


def test_population_inconsistent_values_fail_closed():
    class Inconsistent:
        def count(self, table, filters=None):
            return 10 if table == "prospects" else 20
    result = module.read_qualification_population_counts(Inconsistent())
    assert result["state"] == "COUNT_UNAVAILABLE"
    assert result["prospects_without_v2_record"] is None
