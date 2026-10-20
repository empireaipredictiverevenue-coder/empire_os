"""No-write CLI replay for adaptive cross-team commercial intelligence.

All fixture records are synthetic tests only. Production CLI reads original
owner artifacts, never artificial customers or transactions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from empire_os.revenue_distribution import SOURCES
from test_commercial_conversation_casebook_cli import _prepare

ROOT = Path(__file__).resolve().parents[1]
MODULE = "scripts.review_commercial_adaptive_intelligence_20261020"


def _test_sources(tmp_path: Path):
    files = _prepare(tmp_path)
    for label, rel in SOURCES.items():
        path = tmp_path / rel
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"generated_at": "2026-10-20T09:00:00Z"}
        if label == "radar":
            data["candidates"] = []
        elif label == "buyer_scout":
            data["candidates"] = []
        elif label == "buyer_capacity":
            data.update({
                "buyers_seen": 17,
                "fully_activated": 0,
                "capacity_verified": 0,
                "terms_verified": 0,
            })
        elif label in ("search", "competitor"):
            data["generated_at"] = "2026-09-29T00:00:00Z"
        path.write_text(json.dumps(data))
        files.append(path)
    return files


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(tmp_path: Path, *extra):
    return subprocess.run(
        [sys.executable, "-B", "-m", MODULE, "--read-only",
         "--repo-root", str(tmp_path), *extra],
        cwd=ROOT, text=True, capture_output=True, timeout=25,
    )


def test_cli_generates_privacy_safe_graph_and_never_writes_sources(tmp_path):
    files = _test_sources(tmp_path)
    original = {str(f): _digest(f) for f in files}
    first = _run(tmp_path)
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["status"] == "COMMERCIAL_DEPENDENCY_EVIDENCE_HOLD"
    assert report["transition"] == "FIRST_COMMERCIAL_INTELLIGENCE_REVIEW"
    assert report["outbound_authorized"] is False
    assert report["database_writes"] is False
    assert report["model_training"] is False
    assert report["historical_conversations_not_verified_replies"] == 1
    assert report["buyer_capacity_records_seen_not_purchasers"] == 17
    assert "private@" not in first.stdout
    assert "synthetic-thread-1" not in first.stdout
    assert "Synthetic Partner" not in first.stdout
    assert {str(f): _digest(f) for f in files} == original
    assert sorted(tmp_path.rglob("*.json")) == sorted(files)


def test_cli_previous_control_replay_suppresses_unchanged_review(tmp_path):
    _test_sources(tmp_path)
    original = _run(tmp_path)
    assert original.returncode == 0, original.stderr
    prior = tmp_path / "previous_commercial_review.json"
    prior.write_text(original.stdout)
    second = _run(tmp_path, "--previous-commercial-review-file", str(prior))
    assert second.returncode == 0, second.stderr
    output = json.loads(second.stdout)
    assert output["transition"] == "UNCHANGED_COMMERCIAL_HOLD"
    assert output["operator_attention_due"] is False
    assert output["recommended_parallel_reviews_not_dispatched"] == []
    assert output["outbound_authorized"] is False


def test_cli_rejects_untrusted_checkpoint(tmp_path):
    _test_sources(tmp_path)
    prior = tmp_path / "untrusted.json"
    prior.write_text(json.dumps({
        "schema_version": "empire.commercial.adaptive_intelligence_control.v1",
        "outbound_authorized": True,
    }))
    failure = _run(tmp_path, "--previous-commercial-review-file", str(prior))
    assert failure.returncode != 0


def test_cli_requires_explicit_read_only(tmp_path):
    _test_sources(tmp_path)
    result = subprocess.run(
        [sys.executable, "-B", "-m", MODULE, "--repo-root", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert "required" in result.stderr
