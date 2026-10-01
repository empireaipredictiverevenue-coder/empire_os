import pytest
from empire_os.buyer_demand_graph import BuyerDemandGraphEdge, BuyerDemandGraphNode, build_buyer_demand_graph

def node(node_id, node_type):
    return BuyerDemandGraphNode(node_id=node_id,node_type=node_type,label=node_id,evidence_refs=(f'evidence:{node_id}',))

def edge(edge_id, source, target, relation, **kwargs):
    return BuyerDemandGraphEdge(edge_id=edge_id,source_node_id=source,target_node_id=target,relation=relation,observed_at='2026-10-01T10:00:00+00:00',evidence_refs=(f'evidence:{edge_id}',),**kwargs)

def base_graph():
    nodes=[node('buyer:b1','BUYER'),node('product:permit','PRODUCT'),node('market:austin','MARKET'),node('lane:permit:austin','LANE'),node('signal:permit-1','SIGNAL')]
    edges=[
        edge('product-lane','product:permit','lane:permit:austin','PRODUCT_DEFINES_LANE'),
        edge('market-lane','market:austin','lane:permit:austin','MARKET_DEFINES_LANE'),
        edge('buyer-demand','buyer:b1','lane:permit:austin','BUYER_DEMANDS_LANE',demand_units=None),
        edge('buyer-capacity','buyer:b1','lane:permit:austin','BUYER_HAS_CAPACITY_FOR_LANE',capacity_remaining=10),
        edge('signal-lane','signal:permit-1','lane:permit:austin','SIGNAL_SUPPORTS_LANE'),
    ]
    return nodes,edges

def test_graph_preserves_explicit_buyer_product_market_capacity_topology():
    nodes,edges=base_graph(); graph=build_buyer_demand_graph(nodes=nodes,edges=edges)
    assert graph.node_count == 5
    assert graph.edge_count == 5
    assert graph.buyer_count == 1
    assert graph.lane_count == 1
    assert graph.demand_edge_count == 1
    assert graph.capacity_edge_count == 1
    assert graph.unknown_demand_quantity_count == 1
    assert graph.inferred_edge_count == 0
    assert graph.crawler_scheduling_enabled is False
    assert graph.execution_authority == 'none'

def test_missing_demand_quantity_remains_unknown_not_zero():
    nodes,edges=base_graph(); graph=build_buyer_demand_graph(nodes=nodes,edges=edges)
    row=next(item for item in graph.edges if item['relation']=='BUYER_DEMANDS_LANE')
    assert row['demand_units'] is None
    assert graph.quantified_demand_edge_count == 0

def test_capacity_edge_requires_explicit_capacity():
    with pytest.raises(ValueError, match='requires capacity_remaining'):
        build_buyer_demand_graph(nodes=[node('buyer:b1','BUYER'),node('lane:l1','LANE')],edges=[edge('capacity','buyer:b1','lane:l1','BUYER_HAS_CAPACITY_FOR_LANE')])

def test_relation_types_fail_closed():
    with pytest.raises(ValueError, match='invalid node types'):
        build_buyer_demand_graph(nodes=[node('signal:s1','SIGNAL'),node('lane:l1','LANE')],edges=[edge('bad','signal:s1','lane:l1','BUYER_DEMANDS_LANE')])

def test_unknown_node_reference_fails_closed():
    with pytest.raises(ValueError, match='unknown node'):
        build_buyer_demand_graph(nodes=[node('buyer:b1','BUYER')],edges=[edge('bad','buyer:b1','lane:missing','BUYER_DEMANDS_LANE')])

def test_replay_is_idempotent_for_identical_records():
    nodes,edges=base_graph(); graph=build_buyer_demand_graph(nodes=[*nodes,nodes[0]],edges=[*edges,edges[0]])
    assert graph.node_count == 5 and graph.edge_count == 5

def test_conflicting_duplicate_node_fails_closed():
    nodes,edges=base_graph()
    with pytest.raises(ValueError, match='conflicting duplicate node_id'):
        build_buyer_demand_graph(nodes=[*nodes,BuyerDemandGraphNode(node_id='buyer:b1',node_type='PRODUCT',label='wrong',evidence_refs=('evidence:wrong',))],edges=edges)

def test_demand_api_exposes_observe_only_graph_preview():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from empire_os.demand_api import create_demand_router

    app = FastAPI()
    app.include_router(create_demand_router())
    response = TestClient(app).post(
        '/v1/demand/graph/preview',
        json={
            'nodes': [
                {'node_id':'buyer:b1','node_type':'BUYER','label':'Buyer 1','evidence_refs':['buyer:1']},
                {'node_id':'product:p1','node_type':'PRODUCT','label':'Permit Intelligence','evidence_refs':['product:1']},
                {'node_id':'market:austin','node_type':'MARKET','label':'Austin','evidence_refs':['market:1']},
                {'node_id':'lane:p1:austin','node_type':'LANE','label':'Permit Austin','evidence_refs':['lane:1']},
            ],
            'edges': [
                {'edge_id':'e1','source_node_id':'product:p1','target_node_id':'lane:p1:austin','relation':'PRODUCT_DEFINES_LANE','observed_at':'2026-10-01T10:00:00+00:00','evidence_refs':['product-lane:1']},
                {'edge_id':'e2','source_node_id':'market:austin','target_node_id':'lane:p1:austin','relation':'MARKET_DEFINES_LANE','observed_at':'2026-10-01T10:00:00+00:00','evidence_refs':['market-lane:1']},
                {'edge_id':'e3','source_node_id':'buyer:b1','target_node_id':'lane:p1:austin','relation':'BUYER_DEMANDS_LANE','observed_at':'2026-10-01T10:00:00+00:00','evidence_refs':['demand:1'],'demand_units':None},
                {'edge_id':'e4','source_node_id':'buyer:b1','target_node_id':'lane:p1:austin','relation':'BUYER_HAS_CAPACITY_FOR_LANE','observed_at':'2026-10-01T10:00:00+00:00','evidence_refs':['capacity:1'],'capacity_remaining':10},
            ],
        },
    )
    assert response.status_code == 200
    body=response.json()
    assert body['mode'] == 'OBSERVE'
    assert body['crawler_scheduling_enabled'] is False
    assert body['execution_authority'] == 'none'
    assert body['graph']['demand_edge_count'] == 1
    assert body['graph']['capacity_edge_count'] == 1
    assert body['graph']['unknown_demand_quantity_count'] == 1
    assert body['graph']['inferred_edge_count'] == 0
