"""Shadow bridge contract: private provenance, canonical graph authority and NVIDIA syntax."""
from __future__ import annotations

from dataclasses import replace
import json
import sqlite3

import pytest

from empire_os.buyer_demand_graph import (
    BuyerDemandGraphNode, BuyerDemandGraphEdge, build_buyer_demand_graph,
)
from empire_os.nvidia_ontology_shadow import (
    build_nvidia_model_document, write_private_sqlite_shadow,
)


def _graph(*, unknown=True):
    nodes = [
        BuyerDemandGraphNode("buyer-private-1", "BUYER", "buyer@example.test", ("source:buyer",)),
        BuyerDemandGraphNode("product-1", "PRODUCT", "Permit intelligence", ("source:product",)),
        BuyerDemandGraphNode("market-1", "MARKET", "Austin", ("source:market",)),
        BuyerDemandGraphNode("lane-1", "LANE", "lane/private", ("source:lane",)),
        BuyerDemandGraphNode("signal-1", "SIGNAL", "signal/private", ("source:signal",)),
    ]
    def edge(id, a, b, relation, **kwargs):
        return BuyerDemandGraphEdge(
            id, a, b, relation, "2026-11-16T19:00:00+00:00",
            ("source:secret-evidence",), **kwargs,
        )
    return build_buyer_demand_graph(nodes=nodes, edges=[
        edge("product-edge", "product-1", "lane-1", "PRODUCT_DEFINES_LANE"),
        edge("market-edge", "market-1", "lane-1", "MARKET_DEFINES_LANE"),
        edge("demand-edge", "buyer-private-1", "lane-1", "BUYER_DEMANDS_LANE",
             demand_units=None if unknown else 0),
        edge("capacity-edge", "buyer-private-1", "lane-1",
             "BUYER_HAS_CAPACITY_FOR_LANE", capacity_remaining=10),
        edge("signal-edge", "signal-1", "lane-1", "SIGNAL_SUPPORTS_LANE"),
    ])


def _write(tmp_path, graph):
    return write_private_sqlite_shadow(
        graph, destination=tmp_path / "private_shadow.sqlite",
        privacy_key=b"development-fixture-only-not-a-real-secret-0001",
        approved_category_labels=frozenset({"Permit intelligence", "Austin"}),
    )


def test_privacy_unknown_capacity_and_join_truth(tmp_path):
    report = _write(tmp_path, _graph())
    assert report["mode"] == "OBSERVE"
    assert report["execution_authority"] == "none"
    assert report["identity_authenticated"] is False
    assert report["unknown_demand_quantity_count"] == 1
    assert report["node_count"] == 5
    assert report["edge_count"] == 5
    with sqlite3.connect(report["shadow_path"]) as con:
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        match = con.execute(
            """SELECT p.category_label, m.category_label, demand.demand_units,
                   capacity.capacity_remaining, demand.verification_status
               FROM ontology_edges demand
               JOIN ontology_nodes buyer ON buyer.id=demand.source_node_id
               JOIN ontology_nodes lane ON lane.id=demand.target_node_id
               JOIN ontology_edges pd ON pd.target_node_id=lane.id
                   AND pd.relation='PRODUCT_DEFINES_LANE'
               JOIN ontology_nodes p ON p.id=pd.source_node_id
               JOIN ontology_edges md ON md.target_node_id=lane.id
                   AND md.relation='MARKET_DEFINES_LANE'
               JOIN ontology_nodes m ON m.id=md.source_node_id
               LEFT JOIN ontology_edges capacity
                 ON capacity.source_node_id=buyer.id
                AND capacity.target_node_id=lane.id
                AND capacity.relation='BUYER_HAS_CAPACITY_FOR_LANE'
              WHERE demand.relation='BUYER_DEMANDS_LANE'"""
        ).fetchall()
    assert match == [
        ("Permit intelligence", "Austin", None, 10,
         "EVIDENCE_REFERENCED_NOT_AUTHENTICATED")
    ]
    raw = (tmp_path / "private_shadow.sqlite").read_bytes()
    for sensitive in (b"buyer@example.test", b"source:secret-evidence",
                      b"buyer-private-1", b"lane/private"):
        assert sensitive not in raw
    assert (tmp_path / "private_shadow.sqlite").stat().st_mode & 0o077 == 0


def test_known_zero_is_not_unknown(tmp_path):
    report = _write(tmp_path, _graph(unknown=False))
    assert report["unknown_demand_quantity_count"] == 0
    with sqlite3.connect(report["shadow_path"]) as con:
        assert con.execute(
            "SELECT demand_units FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE'"
        ).fetchone()[0] == 0


def test_fail_closed_on_mutated_graph_and_existing_output(tmp_path):
    invalid = replace(_graph(), mode="ACTION")
    with pytest.raises(ValueError):
        _write(tmp_path, invalid)
    report = _write(tmp_path, _graph())
    with pytest.raises(ValueError, match="destination"):
        _write(tmp_path, _graph())
    assert report["node_count"] == 5


def test_nvidia_model_is_scoped_and_has_no_claimed_outcomes():
    doc = build_nvidia_model_document()
    assert len(doc["data_layer"]["databases"]) == 1
    assert len(doc["semantic_layer"]["terms"]) == 4
    assert len(doc["data_layer"]["foreign_keys"]) == 4
    assert not doc["semantic_layer"]["sql_attributes"]["manual"]
    wire = json.dumps(doc)
    assert "EVIDENCE_REFERENCED_NOT_AUTHENTICATED" not in wire
    assert "verified sale" in wire.lower()
    assert "buyer@example" not in wire


def test_repeated_evidence_refs_cannot_duplicate_shadow_rows(tmp_path):
    original = _graph()
    nodes = [
        replace(BuyerDemandGraphNode(**row),
                evidence_refs=("source:repeated", "source:repeated"))
        for row in original.nodes
    ]
    edges = [
        replace(BuyerDemandGraphEdge(**row),
                evidence_refs=("source:repeated", "source:repeated"))
        for row in original.edges
    ]
    report = _write(
        tmp_path, build_buyer_demand_graph(nodes=nodes, edges=edges)
    )
    with sqlite3.connect(report["shadow_path"]) as con:
        assert con.execute("SELECT count(*) FROM node_evidence_fingerprints").fetchone()[0] == 5
        assert con.execute("SELECT count(*) FROM edge_evidence_fingerprints").fetchone()[0] == 5
