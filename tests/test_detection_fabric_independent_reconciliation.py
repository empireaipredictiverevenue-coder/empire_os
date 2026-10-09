"""Reconciliation must preserve real independently observed truth and fail closed.

All subprocess mutations are directed into pytest tmp_path, never live runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/reconcile_materialized_runtime_bindings.py"
CONTROLS = (
    "action_authority",
    "canonical_identity",
    "conflict_detection",
    "duplicate_detection",
    "entity_classification",
    "evidence_lineage",
    "freshness",
    "input_quality",
    "outcome_linkage",
    "output_quality",
    "quarantine",
)
EVIDENCE = "runtime/leads_control/leads_runtime_observer_latest.json"


def slot(lane: str, control: str, verified: bool = False) -> dict:
    return {
        "lane": lane,
        "control": control,
        "status": "VERIFIED_RUNTIME" if verified else "UNVERIFIED",
        "artifact_paths": [EVIDENCE] if control == "entity_classification"
        and lane == "leads" else [],
    }


@pytest.mark.parametrize("evidence_case", ["valid", "missing", "wrong_lane", "future"])
def test_independent_proof_is_required(tmp_path: Path, evidence_case: str) -> None:
    bindings_path = (
        tmp_path / "runtime/control_plane/runtime_control_bindings_latest.json"
    )
    fabric_path = tmp_path / "runtime/control_plane/detection_fabric_latest.json"
    proof_path = tmp_path / EVIDENCE
    for p in (bindings_path, fabric_path, proof_path):
        p.parent.mkdir(parents=True, exist_ok=True)

    b = {
        "authority": "OBSERVE",
        "lanes": [
            {"lane": "conversations_replies", "controls": {
                c: slot("conversations_replies", c, True) for c in CONTROLS
            }},
            {"lane": "consent_suppression", "controls": {
                c: slot("consent_suppression", c) for c in CONTROLS
            }},
            {"lane": "leads", "controls": {
                c: slot(
                    "leads", c,
                    c in {"action_authority", "freshness", "entity_classification"}
                ) for c in CONTROLS
            }},
        ],
    }
    fabric = {
        "lanes": [{
            "lane": "leads",
            "runtime_verified_control_count": 2,
            "runtime_unverified_controls": [
                c for c in CONTROLS if c not in {"action_authority", "freshness"}
            ],
        }],
    }
    proof = {
        "lane": "leads" if evidence_case != "wrong_lane" else "campaigns",
        "mode": "OBSERVE",
        "status": "VERIFIED_RUNTIME",
        "runtime_verified_controls": (
            ["entity_classification"] if evidence_case != "missing" else []
        ),
        "generated_at": (
            "2099-01-01T00:00:00+00:00" if evidence_case == "future"
            else datetime.now(timezone.utc).isoformat()
        ),
        "action_authority_granted": False,
    }
    bindings_path.write_text(json.dumps(b), encoding="utf-8")
    fabric_path.write_text(json.dumps(fabric), encoding="utf-8")
    proof_path.write_text(json.dumps(proof), encoding="utf-8")

    source = SOURCE.read_text(encoding="utf-8")
    needle = 'ROOT = Path("/srv/empire_os")'
    assert source.count(needle) == 1
    sandbox = tmp_path / "reconcile_in_sandbox.py"
    sandbox.write_text(
        source.replace(needle, "ROOT = Path(" + repr(str(tmp_path)) + ")"),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(sandbox)], capture_output=True,
        text=True, check=False, timeout=15,
    )
    after = json.loads(bindings_path.read_text(encoding="utf-8"))
    if evidence_case == "valid":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "CANONICAL_RECONCILIATION: PASS" in result.stdout
        assert after["authority"] == "OBSERVE"
        assert after["lanes"][1]["controls"]["action_authority"]["status"] != (
            "VERIFIED_RUNTIME"
        )
        assert after["lanes"][2]["controls"]["entity_classification"]["status"] == (
            "VERIFIED_RUNTIME"
        )
    else:
        assert result.returncode != 0
        assert "unproven_canonical" in result.stdout + result.stderr
        assert after == b
