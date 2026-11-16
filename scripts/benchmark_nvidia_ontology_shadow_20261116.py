"""Isolated NVIDIA Auto Ontology SQLite connector vs canonical EmpireOS demand graph.

Uses only synthetic evidence. Pinned vendor source and local-only temp database.
Does not deploy NVIDIA's server or call a model provider.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import secrets
import subprocess
import sys
import tempfile
import types
from pathlib import Path

from empire_os.buyer_demand_graph import (
    BuyerDemandGraphEdge, BuyerDemandGraphNode, build_buyer_demand_graph,
)
from empire_os.nvidia_ontology_shadow import (
    build_nvidia_model_document, write_private_sqlite_shadow,
)

UPSTREAM = Path("/tmp/empire-nvidia-auto-ontology-source-audit-20261116")
DEPS = Path("/tmp/empire-nvidia-ontology-deps-20261116")
EXPECTED_COMMIT = "3825917ac61ff3081035ae61445025f1314d157a"


def load_real_nvidia_sqlite_connector():
    """Load the upstream connector and dependencies without its optional server stack."""
    if not UPSTREAM.is_dir() or not DEPS.is_dir():
        raise RuntimeError("required pinned upstream/deps missing; no silent fallback")
    sha = subprocess.check_output(
        ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True,
    ).strip()
    if sha != EXPECTED_COMMIT:
        raise RuntimeError("NVIDIA source commit changed; review before executing")
    sys.path.insert(0, str(DEPS))
    # Normal package import eagerly imports every cloud connector. Instead,
    # restrict imports to the actual NVIDIA base, SQLite and catalog modules.
    for pkg in ("auto_ontology", "auto_ontology.catalog",
                "auto_ontology.connectors", "auto_ontology.utils"):
        if pkg not in sys.modules:
            package = types.ModuleType(pkg)
            package.__path__ = [str(UPSTREAM.joinpath(*pkg.split(".")))]
            sys.modules[pkg] = package
    return importlib.import_module("auto_ontology.connectors.sqlite").SQLiteDatabase


def synthetic_graph():
    """Explicit facts, deliberately ambiguous zero/unknown and absent revenue."""
    timestamp = "2026-11-16T19:00:00+00:00"
    nodes = [
        BuyerDemandGraphNode("buyer-alpha", "BUYER", "private.alpha@example.test",
                            ("fixture:buyer-alpha",)),
        BuyerDemandGraphNode("buyer-beta", "BUYER", "private.beta@example.test",
                            ("fixture:buyer-beta",)),
        BuyerDemandGraphNode("product-permit", "PRODUCT", "Permit intelligence",
                            ("fixture:product-permit",)),
        BuyerDemandGraphNode("product-roofing", "PRODUCT", "Roofing intelligence",
                            ("fixture:product-roofing",)),
        BuyerDemandGraphNode("market-austin", "MARKET", "Austin",
                            ("fixture:market-austin",)),
        BuyerDemandGraphNode("market-dfw", "MARKET", "DFW",
                            ("fixture:market-dfw",)),
        BuyerDemandGraphNode("lane-permit", "LANE", "private-lane-permit",
                            ("fixture:lane-permit",)),
        BuyerDemandGraphNode("lane-roofing", "LANE", "private-lane-roofing",
                            ("fixture:lane-roofing",)),
    ]
    def edge(id, source, target, relation, **kw):
        return BuyerDemandGraphEdge(
            id, source, target, relation, timestamp,
            ("fixture:explicit-source",), **kw,
        )
    edges = [
        edge("pd1", "product-permit", "lane-permit", "PRODUCT_DEFINES_LANE"),
        edge("md1", "market-austin", "lane-permit", "MARKET_DEFINES_LANE"),
        edge("bd1", "buyer-alpha", "lane-permit", "BUYER_DEMANDS_LANE"),
        edge("bc1", "buyer-alpha", "lane-permit",
             "BUYER_HAS_CAPACITY_FOR_LANE", capacity_remaining=10),
        edge("pd2", "product-roofing", "lane-roofing", "PRODUCT_DEFINES_LANE"),
        edge("md2", "market-dfw", "lane-roofing", "MARKET_DEFINES_LANE"),
        edge("bd2", "buyer-beta", "lane-roofing", "BUYER_DEMANDS_LANE",
             demand_units=0),
    ]
    return build_buyer_demand_graph(nodes=nodes, edges=edges)


def model_schema_valid():
    """Validate with genuine NVIDIA's Pydantic interchange schema."""
    path = UPSTREAM / "auto_ontology/server/model_interchange/schemas.py"
    spec = importlib.util.spec_from_file_location("nvidia_interchange_schema", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.AutoOntologyModelDocument.model_validate(
        build_nvidia_model_document(),
    )


def run_benchmark():
    cls = load_real_nvidia_sqlite_connector()
    model = model_schema_valid()
    graph = synthetic_graph()
    with tempfile.TemporaryDirectory(
        prefix="empire-nvidia-ontology-", dir="/tmp",
    ) as d:
        dbpath = Path(d) / "shadow.sqlite"
        packet = write_private_sqlite_shadow(
            graph, destination=dbpath, privacy_key=secrets.token_bytes(32),
            approved_category_labels=frozenset(
                {"Austin", "DFW", "Permit intelligence", "Roofing intelligence"}
            ),
        )
        vendor = cls(str(dbpath))
        try:
            vendor.execute("PRAGMA query_only=ON")
            if int(vendor.execute("PRAGMA query_only").iloc[0, 0]) != 1:
                raise AssertionError("NVIDIA connector is not read-only")
            catalog = vendor.get_tables()
            columns = vendor.get_columns()
            fks = vendor.get_fks()
            expected_types = {table.name for table in
                model.data_layer.databases[0].schemas[0].tables}
            actual_types = set(catalog["table_name"].tolist())
            if actual_types != expected_types:
                raise AssertionError(f"vendor discovered {actual_types}, expected {expected_types}")
            if len(fks) != 4:
                raise AssertionError(f"vendor FK mismatch: {len(fks)}")
            # These are NVIDIA connector executions against a real isolated DB,
            # NOT NVIDIA's MCP/LLM-generated answers.
            questions = {
                "explicit_buyer_demand_edges": (
                    "SELECT COUNT(*) AS value FROM ontology_edges "
                    "WHERE relation='BUYER_DEMANDS_LANE'", graph.demand_edge_count),
                "explicit_capacity_edges": (
                    "SELECT COUNT(*) AS value FROM ontology_edges "
                    "WHERE relation='BUYER_HAS_CAPACITY_FOR_LANE'", graph.capacity_edge_count),
                "unknown_demand_not_zero": (
                    "SELECT COUNT(*) AS value FROM ontology_edges "
                    "WHERE relation='BUYER_DEMANDS_LANE' AND demand_units IS NULL",
                    graph.unknown_demand_quantity_count),
                "known_zero_demand": (
                    "SELECT COUNT(*) AS value FROM ontology_edges "
                    "WHERE relation='BUYER_DEMANDS_LANE' AND demand_units=0", 1),
                "explicit_product_market_lanes": (
                    "SELECT COUNT(*) AS value FROM ontology_edges d "
                    "JOIN ontology_edges p ON p.target_node_id=d.target_node_id "
                    "AND p.relation='PRODUCT_DEFINES_LANE' "
                    "JOIN ontology_edges m ON m.target_node_id=d.target_node_id "
                    "AND m.relation='MARKET_DEFINES_LANE' "
                    "WHERE d.relation='BUYER_DEMANDS_LANE'", 2),
                "known_capacity_for_demand": (
                    "SELECT COUNT(*) AS value FROM ontology_edges d "
                    "JOIN ontology_edges c ON d.source_node_id=c.source_node_id "
                    "AND d.target_node_id=c.target_node_id "
                    "AND c.relation='BUYER_HAS_CAPACITY_FOR_LANE' "
                    "WHERE d.relation='BUYER_DEMANDS_LANE' "
                    "AND c.capacity_remaining>0", 1),
            }
            results = {}
            for name, (query, expected) in questions.items():
                rows = vendor.execute(query, timeout_s=5)
                actual = int(rows.iloc[0]["value"])
                results[name] = {"expected": expected, "actual": actual,
                                 "pass": actual == expected}
            raw = dbpath.read_bytes()
            privacy_pass = not any(
                secret in raw for secret in (
                    b"private.alpha@example.test", b"private.beta@example.test",
                    b"fixture:explicit-source", b"buyer-alpha", b"buyer-beta",
                )
            )
            cannot_answer_revenue = not any(
                "revenue" in name.lower() or "sale" in name.lower()
                for name in columns["column_name"].tolist()
            )
            success = all(item["pass"] for item in results.values())
            success &= privacy_pass and cannot_answer_revenue
            return {
                "status": "PASS" if success else "FAIL",
                "run_type": "REAL_NVIDIA_SQLITE_CONNECTOR_OFFLINE_BENCHMARK",
                "upstream_commit": EXPECTED_COMMIT,
                "synthetic_only": True,
                "vendor_connector_executed": True,
                "model_schema_validated": True,
                "catalog_table_count": len(catalog),
                "catalog_column_count": len(columns),
                "foreign_key_count": len(fks),
                "nvidia_model_term_count": len(model.semantic_layer.terms),
                "sql_queries_checked": len(questions),
                "sql_queries_passed": sum(x["pass"] for x in results.values()),
                "privacy_excluded_raw_identifiers": privacy_pass,
                "revenue_claim_not_answerable": cannot_answer_revenue,
                "client_model_inference_tested": False,
                "mcp_runtime_tested": False,
                "production_data_accessed": False,
                "commercial_buyer_verified": False,
                "results": results,
            }
        finally:
            vendor.close()


def main():
    result = run_benchmark()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
