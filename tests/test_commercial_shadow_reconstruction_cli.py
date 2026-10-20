"""CLI-level evidence of no data refresh writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts.review_commercial_shadow_reconstruction_20261020"


def _write(root: Path, rel: str, data):
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data))
    return target


def _inputs(tmp_path):
    paths = []
    paths.append(_write(tmp_path, "runtime/commercial_catalog/latest.json", {
        "schema_version": "empire.commercial-product-catalog.v1",
        "generated_at": "2026-10-20T08:00:00Z",
        "execution_authority": "none",
        "products": [{
            "product_code": "report",
            "active": True,
            "binding_terms_ready": True,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
            "price_basis": {"amount_cents": 9900, "currency": "USD", "unit": "per_report"},
            "readiness_blockers": [],
        }],
    }))
    paths.append(_write(tmp_path, "runtime/revenue_distribution/latest.json", {
        "schema_version": "empire.revenue_distribution.v1",
        "generated_at": "2026-10-14T08:00:00Z",
        "execution_authority": "none",
        "opportunities": [],
    }))
    paths.append(_write(tmp_path, "runtime/predictive_revenue/commercial_offer_book/latest.json", {
        "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
        "generated_at": "2026-09-30T00:00:00Z",
        "execution_authority": "none",
        "targets": [],
    }))
    paths.append(_write(tmp_path, "runtime/buyer_acquisition/promotion_plan_latest.json", {
        "generated_at": "2026-10-20T08:00:00Z",
        "proposals": [{
            "proposed_prospect_payload": {"business_name": "Synthetic Company"},
            "domain": "example.invalid",
            "target_product_codes": ["report"],
        }],
    }))
    return paths


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_shadow_cli_does_not_touch_source_or_create_output(tmp_path):
    paths = _inputs(tmp_path)
    before = {p: _digest(p) for p in paths}
    result = subprocess.run(
        [
            sys.executable, "-B", "-m", SCRIPT,
            "--read-only", "--repo-root", str(tmp_path),
        ],
        text=True, capture_output=True, timeout=20, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    packet = json.loads(result.stdout)
    assert packet["status"] == "SOURCE_FRESHNESS_HOLD"
    assert packet["in_memory_reconstructed_offer_book"]["target_count"] == 1
    assert packet["reconstructed_ready_catalog_product_count"] == 1
    assert packet["target_count_delta_not_a_new_leads_count"] == 1
    assert packet["canonical_files_written"] is False
    assert packet["outbound_authorized"] is False
    assert packet["database_writes"] is False
    assert "Synthetic Company" not in result.stdout
    after = {p: _digest(p) for p in paths}
    assert before == after
    assert sorted(p for p in tmp_path.rglob("*.json")) == sorted(paths)


def test_cli_requires_explicit_read_only_flag(tmp_path):
    _inputs(tmp_path)
    result = subprocess.run(
        [sys.executable, "-B", "-m", SCRIPT, "--repo-root", str(tmp_path)],
        text=True, capture_output=True, timeout=15, cwd=ROOT,
    )
    assert result.returncode != 0
    assert "required" in result.stderr
