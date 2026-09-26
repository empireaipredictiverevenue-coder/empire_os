from pathlib import Path

import pytest

from empire_os.execution_plane_dispatcher import (
    ExecutionRequest,
    dispatch_execution_request,
)


def test_mutating_request_requires_edit_and_lease_scope():
    with pytest.raises(ValueError, match="allowed_paths"):
        ExecutionRequest(
            request_id="build-1",
            capability="backend_code",
            department="engineering",
            objective="Add bounded feature",
            authority="internal_write",
            lease_resources=("domain:test",),
        ).validate()

    with pytest.raises(ValueError, match="lease_resources"):
        ExecutionRequest(
            request_id="build-2",
            capability="backend_code",
            department="engineering",
            objective="Add bounded feature",
            authority="internal_write",
            allowed_paths=("empire_os/example.py",),
        ).validate()


def test_consequential_request_never_enters_execution_plane():
    with pytest.raises(ValueError, match="consequential"):
        ExecutionRequest(
            request_id="money-1",
            capability="backend_code",
            department="commercial",
            objective="Move funds",
            authority="internal_write",
            risk_class="consequential",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:commercial",),
        ).validate()


def test_agent_reach_request_queues_safely_when_runtime_missing(tmp_path):
    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="research-1",
            capability="social_research",
            department="market_opportunity",
            objective="Research observed public market evidence.",
            authority="observe",
            evidence_domains=("reddit",),
        ),
    )
    assert result["worker"] == "agent_reach"
    assert result["status"] in {
        "WAITING_FOR_RUNTIME",
        "SENSOR_REQUEST_READY",
    }
    assert result["external_send"] is False
    assert result["payment_action"] is False
    assert result["revenue_recognition"] is False
    assert result["execution_authority"] == "none"


def test_space_request_is_workspace_only(tmp_path):
    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="workspace-1",
            capability="founder_workspace",
            department="strategy",
            objective="Create an execution ledger workspace.",
            authority="internal_write",
        ),
    )
    assert result["worker"] == "space_agent"
    assert result["status"] in {
        "WAITING_FOR_RUNTIME",
        "WORKSPACE_REQUEST_READY",
    }
    assert result["production_deploy"] is False
    assert result["execution_authority"] == "none"



def test_dispatch_exposes_promptfoo_requirement_for_ai_change(tmp_path):
    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="workspace-ai-1",
            capability="founder_workspace",
            department="strategy",
            objective="Change internal AI workspace behavior.",
            authority="internal_write",
            ai_behavior_change=True,
        ),
    )
    plan = result["verification_plan"]
    assert plan["promptfoo_required"] is True
    assert plan["production_promotion_allowed"] is False


def test_pi_mutation_waits_for_proven_builder(tmp_path):
    (tmp_path / ".git").mkdir()
    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="parallel-build-wait",
            capability="parallel_backend_code",
            department="engineering",
            objective="Implement bounded internal code change.",
            authority="internal_write",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:test",),
        ),
    )
    assert result["status"] == "WAITING_FOR_CAPABLE_BUILDER"
    assert result["reason"] == "no_mutation_capable_builder_proven"
    assert result["execution_authority"] == "none"
    assert result["production_deploy"] is False


def test_pi_mutation_fails_over_to_isolated_empire_coder(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    import empire_os.execution_plane_dispatcher as module

    def capability_ready(worker, capability, *, path):
        return worker == "empire_coder" and capability == "structured_patch_mutation"

    monkeypatch.setattr(module, "builder_capability_ready", capability_ready)
    monkeypatch.setattr(
        module,
        "run_empire_coder_sandbox_job",
        lambda *args, **kwargs: {
            "status": "PROPOSAL_READY",
            "proposal_branch": "empire-coder/job-parallel-build",
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
            request_id="parallel-build",
            capability="parallel_backend_code",
            department="engineering",
            objective="Implement bounded internal code change.",
            authority="internal_write",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:test",),
        ),
    )
    assert result["worker"] == "empire_coder"
    assert result["status"] == "CANDIDATE_GATE_PASSED"
    assert result["runtime_fallback"]["from"] == "pi"
    assert result["runtime_fallback"]["to"] == "empire_coder"
    assert result["production_deploy"] is False
    assert result["execution_authority"] == "none"
