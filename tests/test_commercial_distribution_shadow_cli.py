"""Boundary tests: the Revenue Distribution preview never writes production inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from empire_os.revenue_distribution import SOURCES

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts.review_commercial_distribution_shadow_20261020"


def _files(tmp_path):
    prior = tmp_path / "runtime/revenue_distribution/latest.json"
    prior.parent.mkdir(parents=True, exist_ok=True)
    prior.write_text(json.dumps({
        "schema_version": "empire.revenue_distribution.v1",
        "execution_authority": "none",
        "opportunities": [],
    }))
    paths = [prior]
    for name, relative in SOURCES.items():
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        stamp = "2026-09-29T00:00:00Z" if name in ("search", "competitor") else "2026-10-20T09:00:00Z"
        data = {"generated_at": stamp, "status": "OBSERVE"}
        if name == "radar":
            data["candidates"] = []
        elif name == "catalog":
            data["products"] = []
        elif name == "buyer_scout":
            data["candidates"] = []
        elif name == "buyer_capacity":
            data.update({
                "buyers_seen": 10,
                "fully_activated": 0,
                "terms_verified": 0,
                "capacity_verified": 0,
            })
        p.write_text(json.dumps(data))
        paths.append(p)
    return paths


def test_manual_shadow_cli_never_refreshes_upstreams(tmp_path):
    paths = _files(tmp_path)
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result = subprocess.run(
        [sys.executable, "-B", "-m", SCRIPT,
         "--read-only", "--repo-root", str(tmp_path)],
        cwd=ROOT, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["source_states"]["search"] == "stale"
    assert report["source_states"]["competitor"] == "stale"
    assert report["status"] == "SOURCE_AND_BUYER_EVIDENCE_HOLD"
    assert report["snapshot_writes"] is False
    assert report["agent_tasks_created"] is False
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths} == hashes
    assert sorted(tmp_path.rglob("*.json")) == sorted(paths)


def test_cli_requires_manual_read_only_flag(tmp_path):
    _files(tmp_path)
    result = subprocess.run(
        [sys.executable, "-B", "-m", SCRIPT, "--repo-root", str(tmp_path)],
        cwd=ROOT, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode != 0
    assert "required" in result.stderr
