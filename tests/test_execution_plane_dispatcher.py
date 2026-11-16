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



def test_dispatch_carries_data_cloud_base_branch_to_hermes(
    tmp_path,
    monkeypatch,
):
    import empire_os.execution_plane_dispatcher as module

    captured = {}

    def publish(_root, payload):
        captured.update(payload)
        return {"published": True}

    monkeypatch.setattr(module, "publish_control_job", publish)

    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="data-cloud-hermes",
            capability="backend_code",
            department="platform",
            objective="Implement bounded Data Cloud code.",
            authority="internal_write",
            base_branch="agent/data-cloud-wave4",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:data_cloud_example",),
        ),
    )

    assert result["worker"] == "hermes"
    assert result["status"] == "QUEUED"
    assert captured["base_branch"] == "agent/data-cloud-wave4"


def test_dispatch_carries_data_cloud_base_branch_to_pi(
    tmp_path,
    monkeypatch,
):
    import empire_os.execution_plane_dispatcher as module

    class Health:
        ready = True

        def as_dict(self):
            return {"ready": True}

    captured = {}

    monkeypatch.setattr(
        module,
        "builder_capability_ready",
        lambda worker, capability, *, path: (
            worker == "pi" and capability == "code_mutation"
        ),
    )
    monkeypatch.setattr(module, "pi_health", lambda: Health())

    def run_pi(_root, job):
        captured["base_branch"] = job.base_branch
        return {
            "status": "PROPOSAL_READY",
            "proposal_branch": None,
            "execution_authority": "none",
            "production_mutation": False,
        }

    monkeypatch.setattr(module, "run_pi_sandbox_job", run_pi)

    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="data-cloud-pi",
            capability="parallel_backend_code",
            department="platform",
            objective="Implement bounded parallel Data Cloud code.",
            authority="internal_write",
            base_branch="agent/data-cloud-wave4",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:data_cloud_parallel",),
        ),
    )

    assert result["worker"] == "pi"
    assert captured["base_branch"] == "agent/data-cloud-wave4"


def test_execution_request_rejects_unapproved_base_branch():
    with pytest.raises(ValueError, match="allowlist"):
        ExecutionRequest(
            request_id="bad-base",
            capability="backend_code",
            department="platform",
            objective="x",
            authority="internal_write",
            base_branch="main",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:data_cloud_example",),
        ).validate()


def test_observe_hermes_dispatch_preserves_zero_mutation_scope(
    tmp_path,
    monkeypatch,
):
    import empire_os.execution_plane_dispatcher as module
    from empire_os.hermes_control import HermesJob

    captured = {}

    def publish(_root, payload):
        job = HermesJob.from_mapping(payload)
        captured["job"] = job
        return {"published": True}

    monkeypatch.setattr(module, "publish_control_job", publish)

    result = dispatch_execution_request(
        tmp_path,
        ExecutionRequest(
            request_id="observe-hermes-audit",
            capability="backend_code",
            department="engineering",
            objective="Inspect architecture only.",
            authority="observe",
        ),
    )

    assert result["worker"] == "hermes"
    assert result["status"] == "QUEUED"
    assert captured["job"].authority == "observe"
    assert captured["job"].allowed_paths == ()
    assert captured["job"].lease_resources == ()
    assert result["execution_authority"] == "none"


def _stale_hermes_repo(tmp_path):
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    subprocess.run(
        ("git", "branch", "-M", "agent/data-cloud-wave4"), cwd=root, check=True,
    )
    (root / "app.py").write_text("VALUE = 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text("def test_value():\n    assert True\n")
    subprocess.run(("git", "add", "app.py", "tests/test_app.py"), cwd=root, check=True)
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "base"), cwd=root, check=True,
    )
    old = subprocess.check_output(
        ("git", "rev-parse", "HEAD"), cwd=root, text=True,
    ).strip()
    subprocess.run(
        ("git", "update-ref", "refs/remotes/origin/agent/data-cloud-wave4", old),
        cwd=root, check=True,
    )
    (root / "app.py").write_text("VALUE = 2\n")
    subprocess.run(("git", "add", "app.py"), cwd=root, check=True)
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "current"), cwd=root, check=True,
    )
    return root


def _stale_code_request(*, allow=False, tests=("tests/test_app.py",)):
    return ExecutionRequest(
        request_id="stale-root-code",
        capability="backend_code",
        department="engineering",
        objective="Bounded implementation using current source",
        authority="internal_write",
        risk_class="low",
        source_ref="founder-approved-stale-base-test",
        allowed_paths=("app.py",),
        lease_resources=("path:app.py",),
        required_tests=tests,
        allow_stale_base_local_fallback=allow,
    )


def test_stale_hermes_base_holds_without_explicit_local_route(tmp_path, monkeypatch):
    import empire_os.execution_plane_dispatcher as module

    root = _stale_hermes_repo(tmp_path)
    monkeypatch.setattr(
        module, "publish_control_job",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not publish")),
    )
    result = dispatch_execution_request(root, _stale_code_request())
    assert result["status"] == "HELD_STALE_REMOTE_BASE"
    assert result["worker"] == "hermes"
    assert result["fallback_requires_explicit_authorisation"] is True
    assert result["source_base_readback"]["remote_matches_head"] == "False"
    assert result["production_deploy"] is False


def test_explicit_authorised_stale_base_uses_existing_local_codex_candidate(
    tmp_path, monkeypatch,
):
    import empire_os.execution_plane_dispatcher as module

    root = _stale_hermes_repo(tmp_path)
    called = []

    def candidate(_root, job):
        called.append((_root, job))
        return {
            "status": "LOCAL_PROPOSAL_READY",
            "proposal_patch": "/tmp/isolated-only.patch",
            "verification_passed": True,
            "production_mutation": False,
            "production_deploy": False,
            "execution_authority": "none",
        }

    monkeypatch.setattr(module, "run_empire_coder_codex_local_candidate", candidate)
    monkeypatch.setattr(
        module, "publish_control_job",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not publish")),
    )
    result = dispatch_execution_request(root, _stale_code_request(allow=True))
    assert result["worker"] == "empire_coder"
    assert result["status"] == "LOCAL_PROPOSAL_READY"
    assert result["runtime_fallback"]["from"] == "hermes"
    assert result["runtime_fallback"]["external_push"] is False
    assert result["proposal_gate"]["candidate_gate_passed"] is False
    assert result["proposal_gate"]["founder_release_review_required"] is True
    assert result["production_deploy"] is False
    assert called[0][1].allowed_paths == ("app.py",)
    assert called[0][1].pytest_targets == ("tests/test_app.py",)


def test_local_codex_fallback_rejects_inferred_write_authority():
    with pytest.raises(ValueError, match="local Codex fallback"):
        ExecutionRequest(
            request_id="bad-observe", capability="backend_code",
            department="engineering", objective="plan only",
            authority="observe", allow_stale_base_local_fallback=True,
            required_tests=("tests/test_app.py",),
        ).validate()
    with pytest.raises(ValueError, match="local Codex fallback"):
        _stale_code_request(allow=True, tests=()).validate()


def test_matching_hermes_remote_still_uses_original_owner(tmp_path, monkeypatch):
    import subprocess
    import empire_os.execution_plane_dispatcher as module

    root = _stale_hermes_repo(tmp_path)
    now = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=root, text=True).strip()
    subprocess.run(
        ("git", "update-ref", "refs/remotes/origin/agent/data-cloud-wave4", now),
        cwd=root, check=True,
    )
    observed = []
    monkeypatch.setattr(
        module, "publish_control_job",
        lambda _r, packet: observed.append(packet) or {"published": True},
    )
    result = dispatch_execution_request(root, _stale_code_request(allow=True))
    assert result["status"] == "QUEUED"
    assert result["worker"] == "hermes"
    assert observed[0]["base_branch"] == "agent/data-cloud-wave4"
