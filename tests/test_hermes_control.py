import pytest

from empire_os.hermes_control import (
    DEFAULT_BASE_BRANCH,
    HermesControlError,
    HermesJob,
    build_hermes_prompt,
    path_is_allowed,
    path_is_protected,
    validate_changed_paths,
)


def base_job(**overrides):
    data = {
        "schema_version": "empire.hermes.control_job.v1",
        "job_id": "revenue-sprint-001",
        "kind": "code_task",
        "authority": "internal_write",
        "base_branch": DEFAULT_BASE_BRANCH,
        "prompt": "Improve the revenue command queue without external actions.",
        "allowed_paths": [
            "empire_os/",
            "tests/",
            "scripts/",
            "docs/",
            "deploy/",
        ],
        "pytest_targets": [
            "tests/test_control_fabric.py",
        ],
        "max_runtime_seconds": 900,
    }
    data.update(overrides)
    return data


def test_job_schema_accepts_internal_reversible_task():
    job = HermesJob.from_mapping(base_job())

    assert job.job_id == "revenue-sprint-001"
    assert job.authority == "internal_write"
    assert job.base_branch == DEFAULT_BASE_BRANCH
    assert job.pytest_targets == (
        "tests/test_control_fabric.py",
    )


@pytest.mark.parametrize(
    "authority",
    ["governed_external", "founder_gate"],
)
def test_job_schema_rejects_consequential_authority(authority):
    with pytest.raises(HermesControlError, match="observe/internal_write"):
        HermesJob.from_mapping(
            base_job(authority=authority)
        )


def test_job_schema_rejects_arbitrary_base_branch():
    with pytest.raises(HermesControlError, match="pinned"):
        HermesJob.from_mapping(
            base_job(base_branch="main")
        )


def test_job_schema_rejects_arbitrary_test_command():
    with pytest.raises(HermesControlError, match="invalid pytest target"):
        HermesJob.from_mapping(
            base_job(
                pytest_targets=[
                    "tests/test_ok.py; rm -rf /"
                ]
            )
        )


def test_protected_paths_are_fail_closed():
    assert path_is_protected("recovery/old.py") is True
    assert path_is_protected("toop/file.txt") is True
    assert path_is_protected("runtime/live.json") is True
    assert path_is_protected(".env") is True
    assert path_is_protected("empire_os/app.py") is False


def test_changed_paths_must_match_job_scope():
    allowed = ("empire_os/", "tests/")

    assert path_is_allowed(
        "empire_os/revenue_command.py",
        allowed,
    )
    assert path_is_allowed(
        "tests/test_revenue_command.py",
        allowed,
    )

    with pytest.raises(HermesControlError, match="outside job policy"):
        validate_changed_paths(
            [
                "empire_os/revenue_command.py",
                "deploy/systemd/unsafe.service",
            ],
            allowed_paths=allowed,
        )


def test_prompt_contains_nonnegotiable_production_guards(tmp_path):
    job = HermesJob.from_mapping(base_job())
    prompt = build_hermes_prompt(
        job,
        production_repo=tmp_path / "repo",
        worktree=tmp_path / "worktree",
    )

    required = (
        "Do not use sudo.",
        "Do not run systemctl start/stop/restart/enable/disable.",
        "Do not send email, SMS, voice calls, webhooks, messages, or public posts.",
        "Do not create payment requests, move funds, sign agreements, recognize revenue",
        "Do not apply database migrations",
        "Do not push, merge, rebase, tag, or alter remote git refs.",
        "Unknown remains unknown.",
    )
    for text in required:
        assert text in prompt


def test_prompt_points_hermes_at_isolated_worktree(tmp_path):
    job = HermesJob.from_mapping(base_job())
    worktree = tmp_path / "worktree"
    prompt = build_hermes_prompt(
        job,
        production_repo=tmp_path / "repo",
        worktree=worktree,
    )

    assert f"Editable isolated worktree: {worktree}" in prompt
    assert "Production runtime is READ-ONLY context" in prompt
    assert "EMPIRE_AUTONOMOUS_MODE" not in prompt
