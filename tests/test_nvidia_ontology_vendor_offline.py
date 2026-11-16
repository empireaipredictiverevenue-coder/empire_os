"""Optional offline NVIDIA integration regression: requires separately pinned vendor code.

This test never connects to production sources, invokes inference or deploys
vendor services. Skip when the optional sandbox is not present.
"""
from pathlib import Path

import pytest

from scripts.benchmark_nvidia_ontology_shadow_20261116 import (
    DEPS, UPSTREAM, EXPECTED_COMMIT,
    load_real_nvidia_sqlite_connector, run_benchmark,
)

pytestmark = pytest.mark.skipif(
    not (DEPS.is_dir() and UPSTREAM.is_dir()),
    reason="separately pinned NVIDIA sandbox dependencies absent",
)


def test_nvidia_connector_schema_and_six_query_baseline():
    report = run_benchmark()
    assert report["status"] == "PASS", report
    assert report["run_type"] == "REAL_NVIDIA_SQLITE_CONNECTOR_OFFLINE_BENCHMARK"
    assert report["vendor_connector_executed"]
    assert report["upstream_commit"] == EXPECTED_COMMIT
    assert report["sql_queries_checked"] == report["sql_queries_passed"] == 6
    assert report["foreign_key_count"] == 4
    assert report["privacy_excluded_raw_identifiers"]
    assert report["revenue_claim_not_answerable"]
    assert report["synthetic_only"]
    assert not report["production_data_accessed"]
    assert not report["mcp_runtime_tested"]
    assert not report["client_model_inference_tested"]
    assert not report["commercial_buyer_verified"]


def test_vendor_source_is_actual_pinned_component(monkeypatch):
    monkeypatch.setattr(
        "scripts.benchmark_nvidia_ontology_shadow_20261116.EXPECTED_COMMIT",
        "0" * 40,
    )
    with pytest.raises(RuntimeError, match="changed"):
        load_real_nvidia_sqlite_connector()
