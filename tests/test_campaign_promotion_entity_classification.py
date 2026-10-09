"""Regression: Campaign observer classification must reach canonical runtime binding.

Uses a temporary root; never writes to live runtime or grants send authority.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROMOTER = ROOT / "scripts" / "promote_campaign_runtime_bindings.py"
TARGETS = (
    "entity_classification",
    "canonical_identity",
    "conflict_detection",
    "duplicate_detection",
    "evidence_lineage",
    "input_quality",
    "quarantine",
)


def _slot(lane: str, control: str, status: str) -> dict:
    return {
        "lane": lane,
        "control": control,
        "status": status,
        "artifact_paths": [],
        "active_units": [],
        "matched_keys": [],
        "confidence": 0.0,
        "action_authority_granted": False,
    }


@pytest.mark.parametrize("missing_proof", [False, True])
def test_campaign_classification_promotion_is_evidence_bound(
    tmp_path: Path, missing_proof: bool
) -> None:
    binding_path = (
        tmp_path / "runtime/control_plane/runtime_control_bindings_latest.json"
    )
    observer_path = (
        tmp_path / "runtime/campaigns_control/campaign_runtime_observer_latest.json"
    )
    binding_path.parent.mkdir(parents=True)
    observer_path.parent.mkdir(parents=True)

    campaign_controls = {
        c: _slot(
            "campaigns",
            c,
            "VERIFIED_RUNTIME" if c in {"action_authority", "freshness"} else "UNVERIFIED",
        )
        for c in (*TARGETS, "action_authority", "freshness")
    }
    conversation_controls = {
        c: _slot("conversations_replies", c, "VERIFIED_RUNTIME")
        for c in TARGETS
    }
    before = {
        "authority": "OBSERVE",
        "lanes": [
            {"lane": "campaigns", "controls": campaign_controls},
            {"lane": "conversations_replies", "controls": conversation_controls},
        ],
    }
    binding_path.write_text(json.dumps(before), encoding="utf-8")
    observer = {
        "status": "VERIFIED_RUNTIME",
        "runtime_verified_controls": [
            c for c in TARGETS if not (missing_proof and c == "entity_classification")
        ],
    }
    observer_path.write_text(json.dumps(observer), encoding="utf-8")

    source = PROMOTER.read_text(encoding="utf-8")
    old_root = 'ROOT = Path("/srv/empire_os")'
    assert source.count(old_root) == 1
    sandbox_script = tmp_path / "promote_in_sandbox.py"
    sandbox_script.write_text(
        source.replace(old_root, "ROOT = Path(" + repr(str(tmp_path)) + ")"),
        encoding="utf-8",
    )
    run = subprocess.run(
        [sys.executable, str(sandbox_script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    after = json.loads(binding_path.read_text(encoding="utf-8"))
    if missing_proof:
        assert run.returncode != 0
        assert "observer does not prove: entity_classification" in (
            run.stdout + run.stderr
        )
        assert after == before
        return

    assert run.returncode == 0, run.stdout + run.stderr
    assert after["authority"] == "OBSERVE"
    assert after["lanes"][1] == before["lanes"][1]
    current = after["lanes"][0]["controls"]
    assert set(current) == set(before["lanes"][0]["controls"])
    for control in TARGETS:
        assert current[control]["status"] == "VERIFIED_RUNTIME"
        assert current[control]["action_authority_granted"] is False
    assert "CANONICAL_BINDING_WRITE: PASS" in run.stdout

    # Re-running against already-promoted evidence must not duplicate rows.
    again = subprocess.run(
        [sys.executable, str(sandbox_script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert again.returncode == 0, again.stdout + again.stderr
    assert "ADDED: none" in again.stdout
    assert json.loads(binding_path.read_text(encoding="utf-8")) == after
