"""NVIDIA evaluation receipts: fail-closed performance vs data-plane status.

These tests prevent a successful SQL connector check from being presented
as successful NVIDIA NLP/agent execution. Runtime receipts are private.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
SQL=ROOT/"nvidia_live_synthetic_sql_six_case_receipt_20261116.json"
NLP=ROOT/"nvidia_first_nlp_sql_result_20261116.json"
MODEL=ROOT/"qwen7b_model_capability_probe_20261116.json"


def _receipt(path:Path):
    if not path.is_file():
        pytest.skip("this machine has no local NVIDIA evaluation receipt")
    assert path.stat().st_mode & 0o077 == 0
    return json.loads(path.read_text())


def test_six_live_synthetic_sql_cases_and_data_isolation():
    data=_receipt(SQL)
    assert data["verdict"]=="PASS"
    assert data["not_natural_language"] is True
    assert data["passed_count"]==data["total_count"]==6
    assert data["table_count"]==4 and data["foreign_key_count"]==4
    assert data["canonical_semantic_terms_verified"]==4
    assert data["hmac_privacy"] is True
    assert data["production_data_modified"] is False
    assert data["paid_models"] is False
    assert all(v["pass"] and v["expected"]==v["actual"]
               for v in data["cases"].values())


def test_nlp_acceptance_is_not_falsely_promoted():
    data=_receipt(NLP)
    assert data["status"]=="NOT_VERIFIED"
    assert data["http"]==200
    assert data["expected_count"]==2
    assert data["database_count"] is None
    assert data["sql_matches_expected_table_and_relation"] is False
    assert data["result_event_seen"] is False
    assert data["timed_out"] is True
    assert data["cancel_status_if_incomplete"]==200


def test_qwen7b_structured_benchmark_is_not_falsely_promoted():
    data=_receipt(MODEL)
    assert data["source"]=="LOCAL_PREINSTALLED_OLLAMA"
    assert data["model"]=="qwen2.5-coder:7b"
    assert data["structured_pass"] is False
    assert data["error_kind"]=="ReadTimeout"
    assert data["duration_s"] >= 170
