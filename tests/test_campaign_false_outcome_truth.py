"""Campaign outcome truth regressions: false is NOT a measured outcome.

All executed scripts point at pytest temporary roots; never touch live artifacts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def save(root: Path, rel: str, data: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def run_script(root: Path, name: str) -> subprocess.CompletedProcess:
    source = (ROOT / "scripts" / (name + ".py")).read_text()
    old = 'ROOT = Path("/srv/empire_os")'
    assert source.count(old) == 1
    runner = root / (name + "_isolated.py")
    runner.write_text(source.replace(old, "ROOT = Path(" + repr(str(root)) + ")"))
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, str(runner)], cwd=root, env=env,
        capture_output=True, text=True, timeout=25,
    )


@pytest.mark.parametrize(
    ("measured", "expected"),
    [(False, False), (True, False), (0, True), (2, True), ("", False)],
)
def test_boolean_placeholder_never_verifies_an_outcome(
    tmp_path: Path, measured: object, expected: bool,
) -> None:
    campaign = "campaign-real-id"
    save(
        tmp_path, "runtime/astra/owned_campaign_deployed_release.json",
        {"campaigns": [{"campaign_id": campaign}]},
    )
    save(
        tmp_path, "runtime/campaigns_control/campaign_output_outcome_latest.json",
        {"output_quality_proved": True},
    )
    # A department plan is expressly excluded, even if it says revenue=999.
    save(
        tmp_path, "runtime/astra/department_cycle_latest.json",
        {"campaign_id": campaign, "actual_revenue": 999},
    )
    save(
        tmp_path, "runtime/verified_events/events.json",
        {"campaign_id": campaign, "conversion_count": measured},
    )
    result = run_script(tmp_path, "run_campaign_measured_outcome_resolver")
    assert result.returncode == 0, result.stdout + result.stderr
    proof = json.loads(
        (tmp_path / "runtime/campaigns_control/campaign_measured_outcome_latest.json")
        .read_text()
    )
    assert proof["outcome_linkage_proved"] is expected
    assert ("outcome_linkage" in proof["runtime_verified_controls"]) is expected
    assert proof["exact_outcome_match_count"] == int(expected)
    assert proof["governance"]["action_authority_granted"] is False


def _control(lane: str, control: str, *, path: str = "") -> dict:
    return {
        "lane": lane, "control": control, "status": "VERIFIED_RUNTIME",
        "confidence": 0.9, "artifact_paths": [path] if path else [],
        "active_units": [], "matched_keys": [], "reason": "",
    }


def test_measured_promotion_revokes_stale_verification(tmp_path: Path) -> None:
    source_path = (
        "runtime/campaigns_control/campaign_measured_outcome_latest.json"
    )
    save(
        tmp_path, source_path,
        {"runtime_verified_controls": ["output_quality"],
         "output_quality_proved": True, "outcome_linkage_proved": False,
         "exact_outcome_match_count": 0},
    )
    save(
        tmp_path, "runtime/control_plane/runtime_control_bindings_latest.json",
        {"authority": "OBSERVE", "lanes": [
            {"lane": "campaigns", "controls": {
                "outcome_linkage": _control(
                    "campaigns", "outcome_linkage", path=source_path
                ), "output_quality": _control("campaigns", "output_quality")
            }},
            {"lane": "conversations_replies", "controls": {
                "outcome_linkage": _control("conversations_replies", "outcome_linkage"),
                "output_quality": _control("conversations_replies", "output_quality"),
            }},
        ]},
    )
    for _ in range(2):
        run = run_script(tmp_path, "promote_campaign_measured_controls")
        assert run.returncode == 0, run.stdout + run.stderr
        data = json.loads(
            (tmp_path / "runtime/control_plane/runtime_control_bindings_latest.json")
            .read_text()
        )
        assert data["authority"] == "OBSERVE"
        controls = data["lanes"][0]["controls"]
        assert controls["outcome_linkage"]["status"] == "UNVERIFIED"
        assert controls["output_quality"]["status"] == "VERIFIED_RUNTIME"


def test_fabric_rejects_stale_campaign_outcome(tmp_path: Path) -> None:
    save(
        tmp_path, "runtime/campaigns_control/campaign_measured_outcome_latest.json",
        {"outcome_linkage_proved": False, "runtime_verified_controls": [],
         "exact_outcome_match_count": 0},
    )
    save(
        tmp_path, "runtime/control_plane/runtime_control_bindings_latest.json",
        {"lanes": [{"lane": "campaigns", "controls": {
            "outcome_linkage": _control("campaigns", "outcome_linkage")
        }}]},
    )
    save(
        tmp_path, "runtime/control_plane/detection_fabric_latest.json",
        {"lanes": [{
            "lane": "campaigns", "lane_status": "ACTIVE_RUNTIME",
            "controls": {
                "outcome_linkage": {
                    "status": "VERIFIED_RUNTIME", "runtime_evidence": {
                        "artifact_paths": ["stale-source"]},
                    "source_evidence": []
                }
            }
        }]},
    )
    result = run_script(tmp_path, "apply_runtime_control_bindings")
    assert result.returncode == 0, result.stdout + result.stderr
    new = json.loads(
        (tmp_path / "runtime/control_plane/detection_fabric_latest.json")
        .read_text()
    )
    lane = new["lanes"][0]
    assert lane["controls"]["outcome_linkage"]["status"] != "VERIFIED_RUNTIME"
    assert lane["runtime_verified_control_count"] == 0
    assert "outcome_linkage" in lane["runtime_unverified_controls"]
