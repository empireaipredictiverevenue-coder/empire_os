"""Private, evidence-bounded EmpireOS projection for NVIDIA Auto Ontology evaluation.

This is a staging interchange adapter, not an Auto Ontology server or an
execution bridge. All identity/evidence fields pass through EmpireOS's
existing HMAC pseudonymization and canonical graph validators.
"""
from __future__ import annotations

from pathlib import Path
import os
import sqlite3
from typing import Any

from empire_os.buyer_demand_graph import BuyerDemandGraph
from empire_os.graphify_dual_bridge import project_buyer_demand

SCHEMA_VERSION = "empire.nvidia_ontology.shadow.v1"
SOURCE_TABLES: dict[str, tuple[tuple[str, str], ...]] = {
    "ontology_nodes": (
        ("id", "TEXT"), ("node_type", "TEXT"), ("category_label", "TEXT"),
        ("verification_status", "TEXT"), ("evidence_count", "INTEGER"),
    ),
    "ontology_edges": (
        ("id", "TEXT"), ("source_node_id", "TEXT"), ("target_node_id", "TEXT"),
        ("relation", "TEXT"), ("observed_at", "TEXT"),
        ("verification_status", "TEXT"), ("demand_units", "INTEGER"),
        ("capacity_remaining", "INTEGER"), ("evidence_count", "INTEGER"),
    ),
    "node_evidence_fingerprints": (("node_id", "TEXT"), ("fingerprint", "TEXT")),
    "edge_evidence_fingerprints": (("edge_id", "TEXT"), ("fingerprint", "TEXT")),
}
TABLE_DESCRIPTIONS = {
    "ontology_nodes": (
        "Pseudonymized EmpireOS buyer-demand graph nodes. Evidence referenced "
        "does not establish verified buyer identity or customer status."
    ),
    "ontology_edges": (
        "Explicit evidence-referenced graph relationships. Never treat a "
        "relationship as an independently verified sale, demand confirmation, "
        "buyer approval, or execution authority. NULL quantity means unknown."
    ),
    "node_evidence_fingerprints": "HMAC fingerprints of node evidence refs; no raw source data.",
    "edge_evidence_fingerprints": "HMAC fingerprints of edge evidence refs; no raw source data.",
}


def _project(graph: BuyerDemandGraph, *, privacy_key: bytes,
             approved_category_labels: frozenset[str]) -> dict[str, Any]:
    # Existing owner code revalidates all graph counts, types, edges, and
    # read-only invariants before pseudonymizing identifiers and evidence.
    return project_buyer_demand(
        graph, privacy_key=privacy_key,
        approved_category_labels=approved_category_labels,
    )


def build_nvidia_model_document() -> dict[str, Any]:
    """Native NVIDIA Auto Ontology model-interchange document, no sample PII."""
    tables: list[dict[str, Any]] = []
    terms: list[dict[str, Any]] = []
    for name, columns in SOURCE_TABLES.items():
        table_id = "empire-shadow-" + name
        pk = (["id"] if name in {"ontology_nodes", "ontology_edges"} else
              ["node_id", "fingerprint"] if name == "node_evidence_fingerprints" else
              ["edge_id", "fingerprint"])
        cols = [
            {"id": f"{table_id}-{column_name}", "name": column_name,
             "description": "", "type": column_type, "sample_values": [],
             "is_nullable": column_name in {"demand_units", "capacity_remaining"},
             "is_unique": column_name == "id"}
            for column_name, column_type in columns
        ]
        tables.append({"id": table_id, "name": name,
                       "description": TABLE_DESCRIPTIONS[name],
                       "pk": pk, "type": "table", "columns": cols})
        terms.append({
            "id": "term-" + name, "name": name.replace("_", " ").title(),
            "description": TABLE_DESCRIPTIONS[name],
            "represents": [table_id],
            "columns_attributes": [
                {"id": f"attribute-{table_id}-{col['name']}",
                 "name": col["name"].replace("_", " "),
                 "description": (TABLE_DESCRIPTIONS[name] if col["name"]
                                 == "verification_status" else ""),
                 "column_id": col["id"]}
                for col in cols
            ],
        })
    return {
        "data_layer": {
            "databases": [{"id": "empire-ontology-shadow", "dialect": "sqlite",
                           "schemas": [{"id": "empire-shadow-main", "name": "main",
                                        "database_name": "empire_ontology_shadow",
                                        "tables": tables}]}],
            "foreign_keys": [
                {"source_column_id": "empire-shadow-ontology_edges-source_node_id",
                 "target_column_id": "empire-shadow-ontology_nodes-id"},
                {"source_column_id": "empire-shadow-ontology_edges-target_node_id",
                 "target_column_id": "empire-shadow-ontology_nodes-id"},
                {"source_column_id": "empire-shadow-node_evidence_fingerprints-node_id",
                 "target_column_id": "empire-shadow-ontology_nodes-id"},
                {"source_column_id": "empire-shadow-edge_evidence_fingerprints-edge_id",
                 "target_column_id": "empire-shadow-ontology_edges-id"},
            ],
            "joins": [],
        },
        "semantic_layer": {"terms": terms, "semantic_fks": [],
                           "sql_attributes": {"manual": [], "table": [],
                                              "sql": [], "bridge_table": []},
                           "custom_analyses": []},
        "zones": [],
    }


def write_private_sqlite_shadow(
    graph: BuyerDemandGraph, *, destination: str | Path, privacy_key: bytes,
    approved_category_labels: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Create a new, non-overwriting pseudonymized SQLite evaluation snapshot.

    Does not connect to any source database, scrape, publish, or send data
    to NVIDIA. Caller owns its tenant and source-authority checks.
    """
    projection = _project(graph, privacy_key=privacy_key,
                          approved_category_labels=approved_category_labels)
    path = Path(destination)
    if not path.is_absolute() or path.is_symlink() or path.exists():
        raise ValueError("destination must be a new absolute non-symlink path")
    if not path.parent.is_dir():
        raise ValueError("destination parent directory must exist")
    nodes = projection["nodes"]
    edges = projection["edges"]
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("shadow destination already exists") from exc
    os.close(fd)
    try:
        with sqlite3.connect(path) as con:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("CREATE TABLE ontology_nodes (id TEXT PRIMARY KEY, "
                        "node_type TEXT NOT NULL, category_label TEXT NOT NULL, "
                        "verification_status TEXT NOT NULL, "
                        "evidence_count INTEGER NOT NULL)")
            con.execute("CREATE TABLE ontology_edges (id TEXT PRIMARY KEY, "
                        "source_node_id TEXT NOT NULL REFERENCES ontology_nodes(id), "
                        "target_node_id TEXT NOT NULL REFERENCES ontology_nodes(id), "
                        "relation TEXT NOT NULL, observed_at TEXT NOT NULL, "
                        "verification_status TEXT NOT NULL, demand_units INTEGER, "
                        "capacity_remaining INTEGER, evidence_count INTEGER NOT NULL)")
            con.execute("CREATE TABLE node_evidence_fingerprints "
                        "(node_id TEXT NOT NULL REFERENCES ontology_nodes(id), "
                        "fingerprint TEXT NOT NULL, PRIMARY KEY(node_id,fingerprint))")
            con.execute("CREATE TABLE edge_evidence_fingerprints "
                        "(edge_id TEXT NOT NULL REFERENCES ontology_edges(id), "
                        "fingerprint TEXT NOT NULL, PRIMARY KEY(edge_id,fingerprint))")
            for node in nodes:
                evidence = sorted(set(node["evidence_fingerprints"]))
                con.execute("INSERT INTO ontology_nodes VALUES (?,?,?,?,?)",
                            (node["id"], node["type"], node["label"],
                             node["verification_status"], len(evidence)))
                con.executemany("INSERT INTO node_evidence_fingerprints VALUES (?,?)",
                                [(node["id"], fingerprint) for fingerprint
                                 in evidence])
            for edge in edges:
                evidence = sorted(set(edge["evidence_fingerprints"]))
                con.execute("INSERT INTO ontology_edges VALUES (?,?,?,?,?,?,?,?,?)",
                            (edge["id"], edge["source"], edge["target"],
                             edge["relation"], edge["observed_at"],
                             edge["verification_status"], edge["demand_units"],
                             edge["capacity_remaining"], len(evidence)))
                con.executemany("INSERT INTO edge_evidence_fingerprints VALUES (?,?)",
                                [(edge["id"], fingerprint) for fingerprint
                                 in evidence])
            if con.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("shadow foreign-key integrity failure")
        os.chmod(path, 0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"schema_version": SCHEMA_VERSION, "mode": "OBSERVE",
            "execution_authority": "none", "identity_authenticated": False,
            "node_count": len(nodes), "edge_count": len(edges),
            "unknown_demand_quantity_count":
                projection["unknown_demand_quantity_count"],
            "shadow_path": str(path),
            "nvidia_model": build_nvidia_model_document()}
