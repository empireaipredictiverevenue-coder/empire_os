"""Evidence-only Buyer Demand Graph for EmpireOS.

Models buyer/product/market relationships through explicit Demand Lane nodes.
No edge is inferred and the graph grants no execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

NODE_TYPES = frozenset({'BUYER','PRODUCT','MARKET','LANE','SIGNAL'})
RELATION_TYPES = frozenset({
    'PRODUCT_DEFINES_LANE',
    'MARKET_DEFINES_LANE',
    'BUYER_DEMANDS_LANE',
    'BUYER_HAS_CAPACITY_FOR_LANE',
    'SIGNAL_SUPPORTS_LANE',
})
RELATION_NODE_TYPES = {
    'PRODUCT_DEFINES_LANE': ('PRODUCT','LANE'),
    'MARKET_DEFINES_LANE': ('MARKET','LANE'),
    'BUYER_DEMANDS_LANE': ('BUYER','LANE'),
    'BUYER_HAS_CAPACITY_FOR_LANE': ('BUYER','LANE'),
    'SIGNAL_SUPPORTS_LANE': ('SIGNAL','LANE'),
}

@dataclass(frozen=True)
class BuyerDemandGraphNode:
    node_id: str
    node_type: str
    label: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.node_id.strip():
            raise ValueError('node_id required')
        if self.node_type not in NODE_TYPES:
            raise ValueError('unsupported demand graph node_type')
        if not self.label.strip():
            raise ValueError('node label required')
        if not self.evidence_refs:
            raise ValueError('demand graph node requires evidence refs')

@dataclass(frozen=True)
class BuyerDemandGraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    capacity_remaining: int | None = None
    demand_units: int | None = None

    def validate(self) -> None:
        for label, value in (
            ('edge_id', self.edge_id),
            ('source_node_id', self.source_node_id),
            ('target_node_id', self.target_node_id),
            ('observed_at', self.observed_at),
        ):
            if not str(value or '').strip():
                raise ValueError(f'{label} required')
        if self.relation not in RELATION_TYPES:
            raise ValueError('unsupported demand graph relation')
        if not self.evidence_refs:
            raise ValueError('demand graph edge requires evidence refs')
        try:
            observed = datetime.fromisoformat(self.observed_at.replace('Z', '+00:00'))
        except ValueError as exc:
            raise ValueError('observed_at must be ISO-8601') from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError('observed_at must be timezone-aware')
        if self.capacity_remaining is not None and self.capacity_remaining < 0:
            raise ValueError('capacity_remaining must be nonnegative')
        if self.demand_units is not None and self.demand_units < 0:
            raise ValueError('demand_units must be nonnegative')
        if self.relation == 'BUYER_HAS_CAPACITY_FOR_LANE' and self.capacity_remaining is None:
            raise ValueError('capacity relation requires capacity_remaining')

@dataclass(frozen=True)
class BuyerDemandGraph:
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    node_count: int
    edge_count: int
    buyer_count: int
    lane_count: int
    demand_edge_count: int
    capacity_edge_count: int
    quantified_demand_edge_count: int
    unknown_demand_quantity_count: int
    mode: str = 'OBSERVE'
    inferred_edge_count: int = 0
    crawler_scheduling_enabled: bool = False
    outbound_enabled: bool = False
    execution_authority: str = 'none'

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def _dedupe_nodes(nodes: Iterable[BuyerDemandGraphNode]) -> dict[str, BuyerDemandGraphNode]:
    result = {}
    for node in nodes:
        node.validate()
        existing = result.get(node.node_id)
        if existing is None:
            result[node.node_id] = node
        elif existing != node:
            raise ValueError(f'conflicting duplicate node_id: {node.node_id}')
    return result

def _dedupe_edges(edges: Iterable[BuyerDemandGraphEdge]) -> dict[str, BuyerDemandGraphEdge]:
    result = {}
    for edge in edges:
        edge.validate()
        existing = result.get(edge.edge_id)
        if existing is None:
            result[edge.edge_id] = edge
        elif existing != edge:
            raise ValueError(f'conflicting duplicate edge_id: {edge.edge_id}')
    return result

def build_buyer_demand_graph(*, nodes: Iterable[BuyerDemandGraphNode], edges: Iterable[BuyerDemandGraphEdge]) -> BuyerDemandGraph:
    node_map = _dedupe_nodes(nodes)
    edge_map = _dedupe_edges(edges)
    for edge in edge_map.values():
        source = node_map.get(edge.source_node_id)
        target = node_map.get(edge.target_node_id)
        if source is None or target is None:
            raise ValueError(f'edge references unknown node: {edge.edge_id}')
        expected = RELATION_NODE_TYPES[edge.relation]
        actual = (source.node_type, target.node_type)
        if actual != expected:
            raise ValueError(f'invalid node types for {edge.relation}: {actual[0]}->{actual[1]}')
    node_rows = tuple(asdict(node) for node in sorted(node_map.values(), key=lambda item: item.node_id))
    edge_rows = tuple(asdict(edge) for edge in sorted(edge_map.values(), key=lambda item: item.edge_id))
    demand_edges = [edge for edge in edge_map.values() if edge.relation == 'BUYER_DEMANDS_LANE']
    capacity_edges = [edge for edge in edge_map.values() if edge.relation == 'BUYER_HAS_CAPACITY_FOR_LANE']
    return BuyerDemandGraph(
        nodes=node_rows,
        edges=edge_rows,
        node_count=len(node_rows),
        edge_count=len(edge_rows),
        buyer_count=sum(node.node_type == 'BUYER' for node in node_map.values()),
        lane_count=sum(node.node_type == 'LANE' for node in node_map.values()),
        demand_edge_count=len(demand_edges),
        capacity_edge_count=len(capacity_edges),
        quantified_demand_edge_count=sum(edge.demand_units is not None for edge in demand_edges),
        unknown_demand_quantity_count=sum(edge.demand_units is None for edge in demand_edges),
    )
