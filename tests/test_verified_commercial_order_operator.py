"""Private original-order operator; synthetic fixtures only, no real DB access."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from empire_os.commercial_verified_learning_review import original_order_reader_capability
from scripts.review_verified_commercial_order_20261020 import review_explicit_order_request
from test_authenticated_commercial_outcome_intelligence import (
    TENANT, ORDER, NOW, original_verified_feedback, repository,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = "scripts.review_verified_commercial_order_20261020"


def _cli(*flags, dsn=None):
    env = dict(os.environ)
    env.pop("EMPIREDB_DSN", None)
    if dsn is not None:
        env["EMPIREDB_DSN"] = dsn
    return subprocess.run(
        [sys.executable, "-B", "-m", MODULE, "--repo-root", str(ROOT), *flags],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=15,
    )


def test_owner_not_deployed_does_not_connect_even_with_explicit_order_scope(tmp_path):
    # An isolated Git owner repository without the reader must fail closed
    # even if the actual installed Python module already exposes the method.
    from test_canonical_order_reader_release_integrity import repo, NO_METHOD
    root, _ = repo(tmp_path, NO_METHOD)
    result = _cli("--read-only", "--tenant-id", TENANT, "--order-id", ORDER,
                  "--repo-root", str(root),
                  dsn="dont-connect://private-user:private-secret@localhost")
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert body["status"] == "CANONICAL_OWNER_READER_NOT_DEPLOYED"
    assert body["verified_financial_results"] is None
    assert "private-secret" not in result.stdout + result.stderr
    assert TENANT not in result.stdout and ORDER not in result.stdout


def test_cli_requires_explicit_read_only_and_tenant():
    r = _cli("--tenant-id", TENANT, "--order-id", ORDER)
    assert r.returncode != 0
    assert "--read-only" in r.stderr
    r = _cli("--read-only", "--order-id", ORDER)
    assert r.returncode != 0
    assert "--tenant-id" in r.stderr


def test_invalid_or_duplicate_order_scope_fail_before_any_source_access():
    for ids in ([ORDER, ORDER], ["not-an-order"], [ORDER] * 21):
        flags = [flag for order in ids for flag in ("--order-id", order)]
        r = _cli("--read-only", "--tenant-id", TENANT, *flags)
        assert r.returncode == 2
        body = json.loads(r.stdout)
        assert body["status"] == "INVALID_OR_UNAUTHORIZED_REQUEST_SCOPE"
        assert ORDER not in r.stdout


def test_explicit_scope_validated_aggregate_publishes_no_raw_refs(monkeypatch):
    actual = original_verified_feedback()
    repo = repository(monkeypatch, lambda *_a, **_kw: actual)
    r = review_explicit_order_request(
        repository=repo, tenant_id=TENANT, order_ids=[ORDER],
        now=NOW, repo_root=ROOT,
    )
    assert r["original_order_proof"]["independently_validated_outcome_count"] == 1
    assert r["original_order_proof"]["recognized_revenue_cents_for_complete_selected_cohort"] == 1000
    assert r["original_prediction_provenance_checked"] is False
    assert r["financial_or_model_optimisation_executed"] is False
    assert r["execution_authority"] == "none"
    assert ORDER not in json.dumps(r) and TENANT not in json.dumps(r)


def test_static_owner_capability_can_switch_when_method_published(monkeypatch):
    from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
    monkeypatch.delattr(ExecutionBusDataRepository, "verified_outcome_feedback", raising=False)
    assert original_order_reader_capability()["status"] == "ORIGINAL_ORDER_OWNER_READER_NOT_DEPLOYED"
    monkeypatch.setattr(
        ExecutionBusDataRepository, "verified_outcome_feedback", lambda *_a, **_k: None,
        raising=False,
    )
    cap = original_order_reader_capability()
    assert cap["status"] == "ORIGINAL_ORDER_READER_METHOD_PRESENT_RELEASE_NOT_ATTESTED"
    assert cap["owner_reader_release_approved_by_this_check"] is False
    assert cap["canonical_database_proof_observed"] is False
    assert cap["authenticated_tenant_and_order_selected"] is False
    assert cap["verified_revenue_cents"] is None


def test_error_from_original_owner_is_held_not_leaked(monkeypatch):
    def rejected(*_a, **_kw):
        raise ValueError("original SQL connector secret and contact private@example.invalid")
    repo = repository(monkeypatch, rejected)
    r = review_explicit_order_request(
        repository=repo, tenant_id=TENANT, order_ids=[ORDER], now=NOW,
        repo_root=ROOT,
    )
    assert r["status"] == "CANONICAL_ORDER_EVIDENCE_PARTIAL_HOLD"
    assert r["original_order_proof"]["recognized_revenue_cents_for_complete_selected_cohort"] is None
    assert "private@example.invalid" not in json.dumps(r)
