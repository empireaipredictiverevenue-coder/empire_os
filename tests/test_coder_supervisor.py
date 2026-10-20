from types import SimpleNamespace

from empire_os.coder_supervisor import (
    _nonprotected_dirty,
    _commit_verified_candidate,
    _safe_repo_path,
    _tests_from_implementation_result,
    _verification_passed,
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


def test_exact_protected_roots_are_ignored_as_repo_dirt(tmp_path):
    def runner(argv, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="?? recovery/\n?? toop\n",
            stderr="",
        )

    assert _nonprotected_dirty(tmp_path, runner=runner) == []


def test_real_dirty_file_still_blocks_implementation(tmp_path):
    def runner(argv, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=" M empire_os/real.py\n?? toop\n",
            stderr="",
        )

    assert _nonprotected_dirty(tmp_path, runner=runner) == [
        "empire_os/real.py"
    ]


def test_verification_helpers_require_pass():
    passed = {
        "verification": {
            "verdict": "PASS",
            "checks": [
                {
                    "command": [
                        "python",
                        "-m",
                        "pytest",
                        "-q",
                        "tests/test_example.py",
                    ]
                }
            ],
        }
    }
    failed = {"verification": {"verdict": "FAIL", "checks": []}}
    assert _verification_passed(passed) is True
    assert _verification_passed(failed) is False
    assert _tests_from_implementation_result(passed) == [
        "tests/test_example.py"
    ]



def test_clean_checkout_does_not_turn_advisory_directives_into_implement_jobs(
    tmp_path, monkeypatch,
):
    """No model calls, tasks or queue jobs may come from internal_plan alone."""
    from pathlib import Path
    import empire_os.coder_supervisor as module

    class ExistingDirectiveStore:
        def __init__(self, root):
            self.root = root

        def list(self, *, statuses):
            if statuses == {"implementation_ready"}:
                return (
                    SimpleNamespace(authority="internal_plan"),
                    SimpleNamespace(authority="internal_plan"),
                )
            return ()

        def summary(self):
            return {"status_counts": {"implementation_ready": 2},
                    "founder_gate_count": 0}

        def update(self, *args, **kwargs):
            raise AssertionError("advisory state must not mutate")

    class ExistingCoder:
        def __init__(self, root, **kwargs):
            self.root = root

        def create_task(self, *args, **kwargs):
            raise AssertionError("unapproved task creation")

    class ExistingQueue:
        def __init__(self, root, **kwargs):
            self.pending = Path(root) / "pending"
            self.running = Path(root) / "running"
            self.pending.mkdir(exist_ok=True)
            self.running.mkdir(exist_ok=True)

        def enqueue(self, *args, **kwargs):
            raise AssertionError("unapproved IMPLEMENT enqueue")

    monkeypatch.setattr(module, "FounderDirectiveStore", ExistingDirectiveStore)
    monkeypatch.setattr(module, "plan_captured_directives",
                        lambda *args, **kwargs: {"planned": 0})

    for dirty in ("", " M empire_os/unrelated_owner.py\n"):
        observed = module.run_coder_supervisor(
            tmp_path, coder_factory=ExistingCoder,
            queue_factory=ExistingQueue,
            runner=lambda *args, content=dirty, **kwargs: SimpleNamespace(
                returncode=0, stdout=content, stderr="",
            ),
        )
        assert observed["queued_implementation"] == 0
        assert observed["implementation_authority_held"] == 2
        assert observed["advisory_directive_promoted_to_execution"] is False
        assert observed["implementation_next_action"] == (
            "EXISTING_EXECUTION_PLANE_OWNER_VERIFY_SCOPED_REQUEST"
        )
        assert bool(observed["repo_blocked_by_nonprotected_dirty"]) == bool(dirty)
