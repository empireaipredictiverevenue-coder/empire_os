"""Independent acceptance of NVIDIA's actual connector on live synthetic data.

This is NOT NLP. It checks whether the underlying NVIDIA connector can
execute six known SQL questions against the isolated runtime's SQLite source,
and whether the authenticated frontend exposes the four canonical terms.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import httpx

from scripts.benchmark_nvidia_ontology_shadow_20261116 import (
    EXPECTED_COMMIT, load_real_nvidia_sqlite_connector,
)
from empire_os.nvidia_ontology_shadow import SOURCE_TABLES, TABLE_DESCRIPTIONS

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
SOURCE = ROOT / "empire_graph.sqlite"
RECEIPT = ROOT / "nvidia_live_synthetic_sql_six_case_receipt_20261116.json"
QUERIES = {
    "buyer_demand_edge_count": (
        "SELECT COUNT(*) value FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE'",2
    ),
    "capacity_edge_count": (
        "SELECT COUNT(*) value FROM ontology_edges WHERE relation='BUYER_HAS_CAPACITY_FOR_LANE'",1
    ),
    "unknown_demand_is_not_zero": (
        "SELECT COUNT(*) value FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE' AND demand_units IS NULL",1
    ),
    "confirmed_zero_is_distinct": (
        "SELECT COUNT(*) value FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE' AND demand_units=0",1
    ),
    "joined_product_market_lanes": (
        "SELECT COUNT(*) value FROM ontology_edges d "
        "JOIN ontology_edges p ON p.target_node_id=d.target_node_id AND p.relation='PRODUCT_DEFINES_LANE' "
        "JOIN ontology_edges m ON m.target_node_id=d.target_node_id AND m.relation='MARKET_DEFINES_LANE' "
        "WHERE d.relation='BUYER_DEMANDS_LANE'",2
    ),
    "recorded_capacity_on_matching_demand": (
        "SELECT COUNT(*) value FROM ontology_edges d "
        "JOIN ontology_edges c ON d.source_node_id=c.source_node_id AND d.target_node_id=c.target_node_id "
        "AND c.relation='BUYER_HAS_CAPACITY_FOR_LANE' "
        "WHERE d.relation='BUYER_DEMANDS_LANE' AND c.capacity_remaining>0",1
    ),
}


def main():
    if RECEIPT.exists():
        raise RuntimeError("existing acceptance receipt must remain immutable")
    if not SOURCE.is_file() or SOURCE.stat().st_mode & 0o077:
        raise RuntimeError("private isolated source missing or permissions unsafe")
    keys=dict(s.split("=",1) for s in (ROOT/".env").read_text().splitlines() if "=" in s)
    if keys["CONNECTION_STRINGS"]!="sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("not isolated source")
    probe=sqlite3.connect(f"file:{SOURCE}?mode=ro",uri=True)
    try:
        actual_tables={r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if actual_tables != set(SOURCE_TABLES):
            raise RuntimeError("unrecognised schema")
        privacy=all(word not in SOURCE.read_bytes() for word in
                    (b"private.alpha@example.test",b"private.beta@example.test",b"buyer-alpha",b"buyer-beta"))
    finally:
        probe.close()
    if not privacy:
        raise RuntimeError("synthetic PII/privacy gate failed")
    model=load_real_nvidia_sqlite_connector()
    vendor=model(str(SOURCE))
    try:
        vendor.execute("PRAGMA query_only=ON")
        if int(vendor.execute("PRAGMA query_only").iloc[0,0]) != 1:
            raise RuntimeError("vendor read-only gate failed")
        results={}
        for name,(sql,expected) in QUERIES.items():
            rows=vendor.execute(sql,timeout_s=12)
            actual=int(rows.iloc[0]["value"])
            results[name]={"expected":expected,"actual":actual,"pass":actual==expected}
        foreign_keys=len(vendor.get_fks())
    finally:
        close=getattr(vendor,"close",None)
        if callable(close):
            close()
    if foreign_keys != 4:
        raise RuntimeError("synthetic foreign-key schema mismatch")
    with httpx.Client(base_url="http://localhost:33000",trust_env=False,timeout=18,
                      headers={"Origin":"http://localhost:33000"}) as client:
        auth=client.post("/api/auth/sign-in/email",json={
            "email":keys["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password":keys["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if auth.status_code!=200 or not client.cookies:
            raise RuntimeError("NVIDIA authenticated catalog read failed")
        current=client.get("/api/terms?limit=50")
        current.raise_for_status()
        observed={item["name"]:item["description"]
                  for item in current.json().get("terms",[])}
        terms_good=len(observed)==4 and all(
            observed.get(table.replace("_"," ").title())==desc
            for table,desc in TABLE_DESCRIPTIONS.items())
    data={
        "verdict":"PASS" if all(x["pass"] for x in results.values()) and terms_good else "FAIL",
        "scope":"REAL_NVIDIA_CONNECTOR_LIVE_SYNTHETIC_SQL_AND_AUTH_CATALOG",
        "not_natural_language":True,
        "upstream_commit":EXPECTED_COMMIT,
        "actual_running_fixture":str(SOURCE),
        "table_count":len(SOURCE_TABLES),
        "foreign_key_count":foreign_keys,
        "hmac_privacy":privacy,
        "canonical_semantic_terms_verified":4 if terms_good else 0,
        "cases":results,
        "passed_count":sum(x["pass"] for x in results.values()),
        "total_count":len(results),
        "paid_models":False,
        "production_data_modified":False,
        "secrets_disclosed":False,
    }
    fd=os.open(RECEIPT,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(data,f,indent=2)
    print(json.dumps(data,indent=2,sort_keys=True))
    if data["verdict"]!="PASS":
        raise RuntimeError("NVIDIA SQL acceptance did not pass")


if __name__=="__main__":
    main()
