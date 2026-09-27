from empire_os.openhands_workspace_adapter import (
    OpenHandsWorkspaceRequest,
    build_openhands_workspace_contract,
)


def test_openhands_workspace_contract_is_disposable_and_nonexecuting():
    result = build_openhands_workspace_contract(
        OpenHandsWorkspaceRequest(
            job_id="job-1",
            objective="Prepare a bounded coding workspace.",
            allowed_paths=(
                "empire_os/example.py",
                "tests/test_example.py",
            ),
        )
    )
    assert result["workspace_contract_ready"] is True
    assert result["disposable"] is True
    assert result["production_repo_writable"] is False
    assert result["mutation_capability_proven"] is False
    assert result["mutation_probe_required"] is True
    assert result["independent_verification_required"] is True
    assert result["production_deploy"] is False
    assert result["execution_authority"] == "none"


def test_openhands_workspace_request_requires_bounded_paths():
    request = OpenHandsWorkspaceRequest(
        job_id="job-2",
        objective="Prepare workspace.",
        allowed_paths=(),
    )
    try:
        request.validate()
    except ValueError as exc:
        assert "allowed_paths" in str(exc)
    else:
        raise AssertionError("missing allowed_paths should fail")
