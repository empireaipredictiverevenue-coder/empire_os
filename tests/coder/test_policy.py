from pathlib import Path

import pytest

from empire_os.coder.models import ToolDecision
from empire_os.coder.policy import PolicyError, classify_command, filtered_environment, resolve_path, resolve_runtime_root


def workspace(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "empire_os").mkdir()
    return tmp_path


def test_workspace_escape_and_protected_paths_are_denied(tmp_path):
    root = workspace(tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x")
    with pytest.raises(PolicyError, match="escapes"):
        resolve_path(root, outside)
    (root / "recovery").mkdir()
    (root / "recovery" / "old.py").write_text("x")
    with pytest.raises(PolicyError, match="protected"):
        resolve_path(root, "recovery/old.py")


def test_environment_filters_secrets_and_forces_observe():
    env = filtered_environment({
        "PATH": "/usr/bin",
        "HOME": "/tmp/home",
        "OPENAI_API_KEY": "secret-value",
        "SUPABASE_SERVICE_KEY": "secret-value",
        "RANDOM": "nope",
    })
    assert env["PATH"] == "/usr/bin"
    assert "OPENAI_API_KEY" not in env
    assert "SUPABASE_SERVICE_KEY" not in env
    assert "RANDOM" not in env
    assert env["EMPIRE_EXECUTION_MODE"] == "observe"
    assert env["EMPIRE_CODER_MODE"] == "OBSERVE"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("git", "status", "--short"), ToolDecision.ALLOW),
        (("git", "diff", "--check"), ToolDecision.ALLOW),
        (("git", "push"), ToolDecision.REQUIRE_APPROVAL),
        (("git", "branch", "new-feature"), ToolDecision.REQUIRE_APPROVAL),
        (("git", "branch", "--list"), ToolDecision.ALLOW),
        (("git", "reset", "--hard"), ToolDecision.DENY),
        (("rm", "-rf", "/"), ToolDecision.DENY),
        (("python3", "-m", "pytest"), ToolDecision.ALLOW),
        (("python3", "-c", "print(1)"), ToolDecision.REQUIRE_APPROVAL),
        (("npm", "install"), ToolDecision.REQUIRE_APPROVAL),
        (("npm", "run", "lint"), ToolDecision.ALLOW),
        (("npm", "run", "custom-script"), ToolDecision.REQUIRE_APPROVAL),
        (("npm", "run", "lint"), ToolDecision.ALLOW),
        (("npm", "run", "deploy"), ToolDecision.REQUIRE_APPROVAL),
        (("curl", "https://example.com"), ToolDecision.DENY),
    ],
)
def test_command_policy(argv, expected):
    assert classify_command(argv) is expected


def test_runtime_root_cannot_escape_workspace(tmp_path):
    root = workspace(tmp_path)
    assert resolve_runtime_root(root) == root / "runtime" / "coder"
    with pytest.raises(PolicyError, match="inside workspace"):
        resolve_runtime_root(root, tmp_path.parent / "coder-runtime")


def test_sensitive_env_and_key_files_are_denied(tmp_path):
    root = workspace(tmp_path)
    for name in (".env", ".env.production", "server.pem", "credentials.json"):
        (root / name).write_text("secret")
        with pytest.raises(PolicyError, match="sensitive"):
            resolve_path(root, name)
