"""End-to-end CLI test with synthetic files: no delivery, no file mutations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from empire_os.revenue_distribution_review import REVIEW_SOURCES

ROOT = Path(__file__).resolve().parents[1]
MODULE = "scripts.review_commercial_conversation_casebook_20261020"


def _prepare(root: Path):
    generated = "2026-10-20T09:00:00Z"
    files = {
        "runtime/commercial_catalog/latest.json": {
            "schema_version": "empire.commercial-product-catalog.v1",
            "execution_authority": "none",
            "generated_at": generated,
            "products": [{
                "product_code": "research_only_report",
                "active": True, "binding_terms_ready": True,
                "catalog_state": "VERIFIED", "version_state": "VERIFIED",
                "price_basis": {"amount_cents": 2500, "currency": "USD", "unit": "each"},
                "readiness_blockers": [],
            }],
        },
        "runtime/revenue_distribution/latest.json": {
            "schema_version": "empire.revenue_distribution.v1",
            "execution_authority": "none",
            "generated_at": "2026-10-14T00:00:00Z",
            "opportunities": [],
        },
        "runtime/predictive_revenue/commercial_offer_book/latest.json": {
            "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
            "generated_at": "2026-09-30T00:00:00Z",
            "execution_authority": "none",
            "targets": [],
        },
        "runtime/conversation_recovery/latest.json": {
            "schema_version": "empire.conversation_recovery.v1",
            "execution_authority": "none",
            "send_executed": False,
            "observed_at": generated,
            "items": [{
                "root_intent_id": "synthetic-thread-1",
                "recipient": "private@example.invalid",
                "recoverable": True,
                "recovery_reason": "due_now",
            }],
        },
    }
    for label, rel in REVIEW_SOURCES.items():
        if label == "conversations":
            # Relevant owner packet is the same canonical conversation recovery.
            continue
        if label == "promotion":
            files[rel] = {
                "generated_at": generated,
                "proposals": [{
                    "proposed_prospect_payload": {
                        "business_name": "Synthetic Partner"
                    },
                    "domain": "synthetic.invalid",
                    "target_product_codes": ["research_only_report"],
                }],
            }
        else:
            files[rel] = {}
    # The original owner derives matches by business name against the first
    # touch row, so provide one source row matching the synthetic proposal.
    files["runtime/conversation_recovery/latest.json"]["items"][0]["business_name"] = "Synthetic Partner"
    files["runtime/conversation_recovery/latest.json"]["items"][0]["recipient"] = "private@synthetic.invalid"
    files["runtime/conversation_recovery/latest.json"]["items"][0]["root_intent_id"] = "synthetic-thread-1"

    paths = []
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content))
        paths.append(path)
    return paths


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_synthetic_cli_is_exact_match_private_and_read_only(tmp_path):
    paths = _prepare(tmp_path)
    hashes = {_hash(p): str(p) for p in paths}
    r = subprocess.run(
        [sys.executable, "-B", "-m", MODULE, "--read-only", "--repo-root", str(tmp_path)],
        text=True, capture_output=True, timeout=25, cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["outbound_authorized"] is False
    assert data["database_writes"] is False
    assert data["agent_tasks_created"] is False
    assert data["distinct_offer_thread_refs"] == 1
    assert data["exact_recovery_matches"] == 1
    assert data["manual_operator_cases"][0]["recovery_source_row_numbers"] == [1]
    assert "private@" not in r.stdout
    assert "synthetic-thread-1" not in r.stdout
    assert "Synthetic Partner" not in r.stdout
    assert {_hash(p): str(p) for p in paths} == hashes
    assert sorted(tmp_path.rglob("*.json")) == sorted(paths)


def test_cli_requires_explicit_read_only_flag(tmp_path):
    _prepare(tmp_path)
    r = subprocess.run(
        [sys.executable, "-B", "-m", MODULE, "--repo-root", str(tmp_path)],
        text=True, capture_output=True, timeout=15, cwd=ROOT,
    )
    assert r.returncode != 0
    assert "required" in r.stderr


PROOF_MODULE = "scripts.review_sales_director_original_proof_20261020"


def test_original_proof_handoff_missing_owner_receipts_stays_held_without_writes(tmp_path):
    paths = _prepare(tmp_path)
    before = {_hash(p): str(p) for p in paths}
    r = subprocess.run(
        [sys.executable, "-B", "-m", PROOF_MODULE,
         "--read-only", "--repo-root", str(tmp_path)],
        text=True, capture_output=True, timeout=25, cwd=ROOT,
    )
    assert r.returncode == 0, r.stderr
    report = json.loads(r.stdout)
    assert report["case_count"] == 1
    assert report["status"] == "ORIGINAL_AUTHENTICATED_REPLY_EVIDENCE_HOLD"
    assert report["source_blockers_allowlisted"]
    assert report["original_inbox_accessed"] is False
    assert report["outbound_authorized"] is False
    assert report["database_writes"] is False
    assert "private@" not in r.stdout
    assert "Synthetic Partner" not in r.stdout
    assert "synthetic-thread-1" not in r.stdout
    assert {_hash(p): str(p) for p in paths} == before
    assert sorted(tmp_path.rglob("*.json")) == sorted(paths)


def test_original_proof_cli_requires_readonly_flag(tmp_path):
    _prepare(tmp_path)
    r = subprocess.run(
        [sys.executable, "-B", "-m", PROOF_MODULE,
         "--repo-root", str(tmp_path)],
        text=True, capture_output=True, timeout=15, cwd=ROOT,
    )
    assert r.returncode != 0
    assert "required" in r.stderr
