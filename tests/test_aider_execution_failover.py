from empire_os.execution_plane_dispatcher import (
    ExecutionRequest,
    dispatch_execution_request,
)


def test_pi_mutation_can_use_proven_aider_fallback(
    tmp_path,
    monkeypatch,
):
    (tmp_path / ".git").mkdir()
    import empire_os.execution_plane_dispatcher as module

    def capability_ready(worker, capability, *, path):
        if worker == "pi":
            return False
        return (
            worker == "empire_coder"
            and capability == "aider_mutation"
        )

    monkeypatch.setattr(
        module,
        "builder_capability_ready",
        capability_ready,
    )
    monkeypatch.setattr(
        module,
        "run_empire_coder_sandbox_job",
        lambda *args, **kwargs: {
            "status": "PROPOSAL_READY",
            "proposal_branch": "empire-coder/job-aider-fallback",
            "mutation_backend": "aider",
            "execution_authority": "none",
            "production_mutation": False,
        },
    )
    monkeypatch.setattr(
        module,
        "verify_proposal_candidate",
        lambda *args, **kwargs: {
            "candidate_gate_passed": True,
            "awaiting_promptfoo": False,
        },
    )

    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="parallel-build-aider",
            capability="parallel_backend_code",
            department="engineering",
            objective="Implement a bounded internal code change.",
            authority="internal_write",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:test",),
        ),
    )

    assert result["worker"] == "empire_coder"
    assert result["status"] == "CANDIDATE_GATE_PASSED"
    backends = result["runtime_fallback"]["empire_coder_backends"]
    assert backends["structured_patch"] is False
    assert backends["aider"] is True
    assert result["worker_result"]["mutation_backend"] == "aider"
    assert result["production_deploy"] is False
    assert result["execution_authority"] == "none"
