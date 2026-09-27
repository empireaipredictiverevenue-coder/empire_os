import pytest

from empire_os.ops_core import OpsPolicyError, safe_repo_path, env_key_status


def test_path_policy_rejects_escape_and_protected_paths():
    with pytest.raises(OpsPolicyError):
        safe_repo_path("../etc/passwd")
    with pytest.raises(OpsPolicyError):
        safe_repo_path("recovery/x")
    with pytest.raises(OpsPolicyError):
        safe_repo_path("toop")


def test_path_policy_allows_repo_files():
    p=safe_repo_path("empire_os/ops_core.py")
    assert str(p).startswith("/srv/empire_os/")


def test_env_status_never_returns_values(monkeypatch):
    monkeypatch.setenv("EXAMPLE_SECRET","abc123")
    assert env_key_status(["EXAMPLE_SECRET"]) == {"EXAMPLE_SECRET": True}
