from datetime import datetime, timezone
from empire_os.revenue_exchange_observation_planner import (
    MarketEvidence, MarketPriceEvidence, plan_revenue_exchange_observations,
    plan_from_runtime_artifacts,
)
NOW=datetime(2026,10,2,10,0,tzinfo=timezone.utc)

def test_complete_same_market_evidence_builds_dry_run_proposal_only():
    payload=plan_revenue_exchange_observations(
        inventory=[MarketEvidence('roofing','Dallas',12,'canonical_empiredb_inventory',('inv:1',),True)],
        capacity=[MarketEvidence('roofing','Dallas',4,'canonical_empiredb_capacity',('cap:1',),True)],
        prices=[MarketPriceEvidence('roofing','Dallas',12500,'USD','per_lead','VERIFIED','canonical_empiredb_price',('price:1',),True)],
        generated_at=NOW,
    )
    assert payload['proposal_ready_count']==1
    proposal=payload['candidates'][0]['proposal']
    assert proposal['qualified_inventory_count']==12
    assert proposal['active_buyer_capacity']==4
    assert proposal['verified_price_per_lead_cents']==(12500,)
    assert proposal['evidence']['evidence_refs']==['inv:1','cap:1','price:1']
    assert payload['database_write'] is False
    assert payload['execution_authority']=='none'


def test_supabase_inventory_is_rejected():
    payload=plan_revenue_exchange_observations(
        inventory=[MarketEvidence('roofing','Dallas',5,'canonical_supabase_projection',('x',),False)],
        capacity=[], prices=[], generated_at=NOW,
    )
    assert payload['proposal_ready_count']==0
    assert any(r['reason']=='noncanonical_source' for r in payload['rejected_sources'])
    assert 'canonical_market_inventory_unavailable' in payload['global_blockers']


def test_non_per_lead_price_is_rejected():
    payload=plan_revenue_exchange_observations(
        inventory=[], capacity=[],
        prices=[MarketPriceEvidence('search','London',29900,'USD','per_month','VERIFIED','canonical_empiredb_catalog',('p',),True)],
        generated_at=NOW,
    )
    assert payload['proposal_ready_count']==0
    assert any(r['reason']=='price_unit_not_per_lead' for r in payload['rejected_sources'])


def test_aggregate_capacity_cannot_become_market_capacity():
    payload=plan_revenue_exchange_observations(
        inventory=[],
        capacity=[MarketEvidence('','',3,'canonical_empiredb_buyer_capacity_readiness_aggregate',('cap',),True,False)],
        prices=[], generated_at=NOW,
    )
    assert payload['proposal_ready_count']==0
    assert any(r['reason']=='market_key_missing' for r in payload['rejected_sources'])


def test_current_runtime_shape_fails_closed_without_writes():
    commercial_exchange={
        'source':'canonical_supabase_projection',
        'inventory':[],
    }
    buyer_capacity={'capacity_verified':0}
    catalog={'products':[{
        'binding_terms_ready':True,
        'product_family':'search_intelligence',
        'currency':'USD',
        'price_basis':{'amount_cents':14900,'currency':'USD','unit':'per_month','state':'VERIFIED'},
        'evidence_refs':['catalog:1'],
    }]}
    payload=plan_from_runtime_artifacts(
        commercial_exchange=commercial_exchange,
        buyer_capacity_readiness=buyer_capacity,
        commercial_catalog=catalog,
        generated_at=NOW,
    )
    assert payload['proposal_ready_count']==0
    assert payload['database_write'] is False
    assert payload['runtime_source_truth']['commercial_exchange_source']=='canonical_supabase_projection'
    assert payload['runtime_source_truth']['buyer_capacity_snapshot_is_market_specific'] is False
    assert 'canonical_market_inventory_unavailable' in payload['global_blockers']
    assert 'verified_market_capacity_unavailable' in payload['global_blockers']
    assert 'verified_per_lead_price_unavailable' in payload['global_blockers']
