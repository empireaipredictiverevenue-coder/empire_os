"""Exact-source review guard for the existing isolated Data Cloud meter DDL."""
from __future__ import annotations
import hashlib, importlib.util
from pathlib import Path
import pytest

MODULE=Path(__file__).resolve().parents[1]/"scripts/review_data_cloud_sql_hardening_20261107.py"
SPEC=importlib.util.spec_from_file_location("review_data_cloud_ledger",MODULE)
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

def test_source_pinned_before_hardening():
    b=mod.ORIGINAL.read_bytes()
    assert hashlib.sha256(b).hexdigest()==mod.EXPECTED_ORIGINAL_SHA256

def test_hardened_ddl_matches_exact_source_and_sha():
    candidate=mod.render(mod.ORIGINAL.read_text())
    assert hashlib.sha256(candidate.encode()).hexdigest()=="32d4c5c680b9be8021422c9173f662175ae42b1eaef1fb82205c06e1a3684e53"
    pinned=Path(__file__).resolve().parents[1]/"docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql"
    assert pinned.read_bytes()==candidate.encode()
    assert "CREATE ROLE empire_data_cloud_api_owner NOLOGIN" in candidate
    assert "CREATE ROLE empire_data_cloud_meter_login NOLOGIN" in candidate
    assert candidate.count("SECURITY DEFINER")==4
    assert candidate.count("OWNER TO empire_data_cloud_api_owner")==8
    assert "p_target_host IS NULL OR NOT p_target_host=ANY(p.allowed_hosts)" in candidate
    assert "p_reported_cost_micros IS NULL OR p_evidence_ref IS NULL" in candidate
    assert "GRANT USAGE ON SCHEMA empire_data_cloud_api TO empire_data_cloud_meter_login;" in candidate
    assert "GRANT SELECT ON" not in candidate
    assert "COMMIT;" in candidate

def test_any_baseline_drift_fails_before_write():
    original=mod.ORIGINAL.read_text()
    with pytest.raises(ValueError,match="baseline drift"):
        mod.render(original.replace("IF p_state NOT IN('completed','provider_error') THEN","-- deleted"))
