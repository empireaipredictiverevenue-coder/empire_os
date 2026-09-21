from types import SimpleNamespace

from empire_os.coder_supervisor import (
    _commit_verified_candidate,
    _safe_repo_path,
)


def test_candidate_path_rejects_protected_and_escape_paths():
    for value in ("../secret", "/etc/passwd", "recovery/file.py", "toop/file.py"):
        try:
            _safe_repo_path(value)
        except ValueError:
            pass
        else:
            raise AssertionError(value)


def test_verified_candidate_commit_uses_explicit_target_path(tmp_path):
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ["git", "status", "--short"]:
            return SimpleNamespace(returncode=0, stdout=" M empire_os/x.py\n", stderr="")
        if argv[:3] == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = _commit_verified_candidate(
        tmp_path,
        "Test directive",
        {
            "applied": True,
            "target_path": "empire_os/x.py",
            "verification": {"verdict": "PASS"},
        },
        runner=runner,
    )
    assert result["committed"] is True
    assert result["commit_sha"] == "abc123"
    assert ["git", "add", "--", "empire_os/x.py"] in calls
    assert not any(call[:2] == ["git", "add"] and "." in call for call in calls)


def test_failed_verification_never_commits(tmp_path):
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = _commit_verified_candidate(
        tmp_path,
        "Test directive",
        {
            "applied": True,
            "target_path": "empire_os/x.py",
            "verification": {"verdict": "FAIL"},
        },
        runner=runner,
    )
    assert result["committed"] is False
    assert result["reason"] == "verification_not_passed"
    assert calls == []
