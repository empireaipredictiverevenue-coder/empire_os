from pathlib import Path

import empire_os.predictive_coding_team_status as status


def test_hermes_status_prefers_recovery_result(monkeypatch, tmp_path):
    original_result = (
        "jobs/results/predictive-quantum-exchange-bridge-v1.json"
    )
    recovery_result = (
        "jobs/results/"
        "predictive-quantum-exchange-bridge-v1-recovery-v1.json"
    )

    def exists(repo_root, path, **kwargs):
        return path in {original_result, recovery_result}

    def read(repo_root, path, **kwargs):
        if path == original_result:
            return {
                "status": "FAILED",
                "error": "original failure",
                "proposal_branch": None,
                "proposal_commit": None,
                "changed_paths": [],
            }
        if path == recovery_result:
            return {
                "status": "CANDIDATE_GATE_PASSED",
                "proposal_branch": (
                    "hermes/job-predictive-quantum-exchange-bridge-v1-recovery-v1"
                ),
                "proposal_commit": "abc123",
                "changed_paths": [
                    "empire_os/revenue_exchange_optimization_bridge.py",
                    "tests/test_revenue_exchange_optimization_bridge.py",
                ],
                "proposal_gate": {
                    "candidate_gate_passed": True,
                },
            }
        raise AssertionError(path)

    monkeypatch.setattr(status, "control_path_exists", exists)
    monkeypatch.setattr(status, "read_control_json", read)

    result = status._hermes_state(
        tmp_path,
        "predictive-quantum-exchange-bridge-v1",
        control_branch="ops/hermes-control",
        remote="origin",
    )

    assert result["status"] == "CANDIDATE_GATE_PASSED"
    assert result["result_path"] == recovery_result
    assert result["recovered_from"]["status"] == "FAILED"
    assert result["recovered_from"]["error"] == "original failure"
