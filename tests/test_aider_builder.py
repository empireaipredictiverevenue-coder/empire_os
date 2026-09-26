from pathlib import Path
from types import SimpleNamespace

import empire_os.aider_builder as aider_builder
from empire_os.aider_builder import (
    AiderMutationRequest,
    build_aider_command,
    provider_ready,
    run_aider_mutation,
)


def test_provider_ready_accepts_openai_compatible_env():
    ready, reason = provider_ready({
        "OPENAI_BASE_URL": "http://127.0.0.1:20128/v1",
        "OPENAI_API_KEY": "secret-value",
    })
    assert ready is True
    assert reason == "provider_ready"


def test_aider_command_is_noncommitting_and_secret_free(
    tmp_path,
):
    target = tmp_path / "empire_os/example.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")

    request = AiderMutationRequest(
        objective="Change x to 2.",
        allowed_paths=("empire_os/example.py",),
    )
    command = build_aider_command(
        tmp_path,
        request,
        executable="/usr/local/bin/aider",
    )

    joined = " ".join(command)
    assert "--no-auto-commits" in command
    assert "--no-dirty-commits" in command
    assert "--no-auto-test" in command
    assert "--no-auto-lint" in command
    assert "--no-suggest-shell-commands" in command
    assert "--no-detect-urls" in command
    assert "--no-analytics" in command
    assert "--env-file" in command
    assert "/dev/null" in command
    assert "--file" in command
    assert "empire_os/example.py" in command
    assert "secret-value" not in joined


def test_aider_request_rejects_parent_traversal():
    request = AiderMutationRequest(
        objective="Unsafe",
        allowed_paths=("../escape.py",),
    )
    try:
        request.validate()
    except ValueError as exc:
        assert "parent traversal" in str(exc)
    else:
        raise AssertionError("parent traversal should fail")


def test_aider_run_fails_closed_without_provider(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        aider_builder,
        "aider_health",
        lambda: {
            "ready": True,
            "reason": "aider_ready",
            "version": "aider test",
            "executable": "/usr/local/bin/aider",
            "execution_authority": "none",
        },
    )
    result = run_aider_mutation(
        tmp_path,
        AiderMutationRequest(
            objective="Do bounded edit.",
            allowed_paths=("empire_os/example.py",),
        ),
        environment={},
    )
    assert result["status"] == "PROVIDER_UNAVAILABLE"
    assert result["execution_authority"] == "none"
    assert result["production_mutation"] is False


def test_aider_run_rejects_out_of_scope_changes(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "empire_os/example.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(
        aider_builder,
        "aider_health",
        lambda: {
            "ready": True,
            "reason": "aider_ready",
            "version": "aider test",
            "executable": "/usr/local/bin/aider",
            "execution_authority": "none",
        },
    )
    monkeypatch.setattr(
        aider_builder,
        "_changed_paths",
        lambda workspace: [
            "empire_os/example.py",
            "empire_os/not_allowed.py",
        ],
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="edited",
            stderr="",
        )

    monkeypatch.setattr(
        aider_builder.subprocess,
        "run",
        fake_run,
    )

    result = run_aider_mutation(
        tmp_path,
        AiderMutationRequest(
            objective="Do bounded edit.",
            allowed_paths=("empire_os/example.py",),
        ),
        environment={
            "OPENAI_API_BASE": "http://127.0.0.1:20128/v1",
            "OPENAI_API_KEY": "secret-value",
        },
    )
    assert result["status"] == "PATH_POLICY_FAILED"
    assert result["rejected_paths"] == [
        "empire_os/not_allowed.py"
    ]
    assert result["execution_authority"] == "none"
    assert result["commit_performed"] is False
    assert result["push_performed"] is False


def test_aider_run_reports_bounded_edit(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "empire_os/example.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(
        aider_builder,
        "aider_health",
        lambda: {
            "ready": True,
            "reason": "aider_ready",
            "version": "aider test",
            "executable": "/usr/local/bin/aider",
            "execution_authority": "none",
        },
    )
    monkeypatch.setattr(
        aider_builder,
        "_changed_paths",
        lambda workspace: ["empire_os/example.py"],
    )
    monkeypatch.setattr(
        aider_builder.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="edited",
            stderr="",
        ),
    )

    result = run_aider_mutation(
        tmp_path,
        AiderMutationRequest(
            objective="Do bounded edit.",
            allowed_paths=("empire_os/example.py",),
        ),
        environment={
            "OPENAI_API_BASE": "http://127.0.0.1:20128/v1",
            "OPENAI_API_KEY": "secret-value",
        },
    )
    assert result["status"] == "EDITED"
    assert result["changed_paths"] == ["empire_os/example.py"]
    assert result["production_deploy"] is False
    assert result["execution_authority"] == "none"
