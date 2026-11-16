from pathlib import Path

import pytest

from empire_os.empire_coder_sandbox_runner import (
    DATA_CLOUD_CLOSEOUT_BRANCH,
    EmpireCoderSandboxJob,
    EmpireCoderSandboxError,
    _path_allowed,
)


def test_empire_coder_sandbox_job_requires_bounded_paths_and_leases():
    with pytest.raises(EmpireCoderSandboxError):
        EmpireCoderSandboxJob(
            job_id="safe-1",
            objective="add a bounded change",
            department="engineering",
            capability="backend_code",
            allowed_paths=(),
            lease_resources=("domain:test",),
        ).validate()
    with pytest.raises(EmpireCoderSandboxError):
        EmpireCoderSandboxJob(
            job_id="safe-1",
            objective="add a bounded change",
            department="engineering",
            capability="backend_code",
            allowed_paths=("empire_os/example.py",),
            lease_resources=(),
        ).validate()


def test_empire_coder_sandbox_path_scope_is_prefix_bounded():
    assert _path_allowed(
        "empire_os/search/foo.py",
        ("empire_os/search/",),
    )
    assert not _path_allowed(
        "empire_os/revenue.py",
        ("empire_os/search/",),
    )


def test_empire_coder_sandbox_declares_zero_consequential_authority():
    import empire_os.empire_coder_sandbox_runner as module
    text = Path(module.__file__).read_text(encoding="utf-8")
    assert '"production_mutation": False' in text
    assert '"production_deploy": False' in text
    assert '"external_send": False' in text
    assert '"payment_action": False' in text
    assert '"revenue_recognition": False' in text
    assert '"execution_authority": "none"' in text



def test_empire_coder_accepts_governed_data_cloud_closeout_branch():
    job = EmpireCoderSandboxJob(
        job_id="data-cloud-closeout",
        objective="Implement bounded closeout work.",
        department="platform",
        capability="backend_code",
        allowed_paths=("empire_os/example.py",),
        lease_resources=("domain:data_cloud_test",),
        base_branch=DATA_CLOUD_CLOSEOUT_BRANCH,
    )
    job.validate()
    assert job.base_branch == DATA_CLOUD_CLOSEOUT_BRANCH


def test_empire_coder_rejects_arbitrary_base_branch():
    with pytest.raises(EmpireCoderSandboxError, match="allowlist"):
        EmpireCoderSandboxJob(
            job_id="bad-branch",
            objective="x",
            department="platform",
            capability="backend_code",
            allowed_paths=("empire_os/example.py",),
            lease_resources=("domain:data_cloud_test",),
            base_branch="main",
        ).validate()


def test_structured_patch_runtime_env_pins_proven_llama_cpp(monkeypatch):
    import os
    from empire_os.empire_coder_sandbox_runner import (
        _structured_patch_runtime_env,
    )

    keys = (
        "EMPIRE_CODER_LLAMA_CPP_ENABLED",
        "EMPIRE_CODER_LLAMA_CPP_MODEL",
        "EMPIRE_CODER_LLAMA_CPP_CAPABILITY",
        "EMPIRE_CODER_LLAMA_CPP_ROLES",
        "EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    with _structured_patch_runtime_env(
        True,
        model="qwen2.5-coder:1.5b",
    ):
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_ENABLED"] == "true"
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_MODEL"] == "qwen2.5-coder:1.5b"
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_CAPABILITY"] == "1"
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_ROLES"] == "planner,writer,verifier"
        assert os.environ["EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS"] == "90"

    for key in keys:
        assert key not in os.environ


def test_structured_patch_runtime_env_restores_existing_values(monkeypatch):
    import os
    from empire_os.empire_coder_sandbox_runner import (
        _structured_patch_runtime_env,
    )

    monkeypatch.setenv("EMPIRE_CODER_LLAMA_CPP_ENABLED", "false")
    monkeypatch.setenv("EMPIRE_CODER_LLAMA_CPP_MODEL", "existing-model")
    monkeypatch.setenv("EMPIRE_CODER_LLAMA_CPP_CAPABILITY", "1")
    monkeypatch.setenv("EMPIRE_CODER_LLAMA_CPP_ROLES", "planner")
    monkeypatch.setenv("EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS", "120")

    with _structured_patch_runtime_env(True, model="probe-model"):
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_MODEL"] == "probe-model"

    assert os.environ["EMPIRE_CODER_LLAMA_CPP_ENABLED"] == "false"
    assert os.environ["EMPIRE_CODER_LLAMA_CPP_MODEL"] == "existing-model"
    assert os.environ["EMPIRE_CODER_LLAMA_CPP_CAPABILITY"] == "1"
    assert os.environ["EMPIRE_CODER_LLAMA_CPP_ROLES"] == "planner"
    assert os.environ["EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS"] == "120"


def test_sandbox_proven_small_llama_cannot_masquerade_as_architecture_writer(
    monkeypatch,
):
    """Use real configured model names, without invoking inference or writing data."""
    import os
    from empire_os.coder.router import ModelProfile, ModelRouter
    from empire_os.coder.orchestrator import local_ollama_profiles
    from empire_os.empire_coder_sandbox_runner import (
        _structured_patch_runtime_env,
    )

    monkeypatch.delenv("EMPIRE_CODER_LLAMA_CPP_CAPABILITY", raising=False)
    with _structured_patch_runtime_env(
        True, model="qwen2.5-coder:1.5b",
    ):
        small_capacity = int(os.environ["EMPIRE_CODER_LLAMA_CPP_CAPABILITY"])
        assert small_capacity == 1
        writer_profiles = (
            ModelProfile(
                provider="llama_cpp",
                model="qwen2.5-coder:1.5b",
                capability=small_capacity,
                local=True,
                roles=("planner", "writer", "verifier"),
            ),
            *local_ollama_profiles(("qwen3-coder:30b",)),
        )
        route = ModelRouter(writer_profiles).route(
            "Security architecture refactor for an existing production module",
            role="writer",
        )
        assert route.provider == "ollama"
        assert route.model == "qwen3-coder:30b"

    # If the capable writer is absent, never pretend the small backend
    # is eligible for an architecture patch.
    weak_only = ModelRouter(writer_profiles[:1]).route(
        "Security architecture refactor for an existing production module",
        role="writer",
    )
    assert weak_only.provider == "unconfigured"


@pytest.mark.parametrize(
    "candidate",
    [
        "../empire_os/example.py",
        "../../empire_os/example.py",
        "/empire_os/example.py",
        r"..\empire_os\example.py",
        "empire_os/../empire_os/example.py",
        "empire_os//example.py",
        "C:/empire_os/example.py",
        "././empire_os/example.py",
        "empire_os/./example.py",
    ],
)
def test_sandbox_never_normalizes_unsafe_candidate_into_allowed_scope(candidate):
    assert not _path_allowed(candidate, ("empire_os/",))
    assert not _path_allowed(candidate, ("empire_os/example.py",))


@pytest.mark.parametrize(
    "allowed",
    [
        "../empire_os/",
        "/empire_os/",
        "empire_os/../",
        r"..\empire_os\example.py",
        "C:/empire_os/",
        "empire_os//",
    ],
)
def test_sandbox_denies_unsafe_allowlist_entries(allowed):
    assert not _path_allowed("empire_os/example.py", (allowed,))
    with pytest.raises(EmpireCoderSandboxError, match="safe repo-relative"):
        EmpireCoderSandboxJob(
            job_id="sandbox-path-regression",
            objective="Update a small existing unit-test helper",
            department="engineering",
            capability="backend_code",
            allowed_paths=(allowed,),
            lease_resources=("domain:software_test",),
            pytest_targets=("tests/test_empire_coder_sandbox_runner.py",),
        ).validate()


def test_sandbox_valid_relative_scopes_still_work_and_tests_must_be_safe():
    assert _path_allowed("empire_os/search/foo.py", ("empire_os/search/",))
    assert _path_allowed("./empire_os/search/foo.py", ("empire_os/search/",))
    assert not _path_allowed("empire_os/searches/foo.py", ("empire_os/search/",))
    with pytest.raises(EmpireCoderSandboxError, match="invalid pytest"):
        EmpireCoderSandboxJob(
            job_id="sandbox-target-regression",
            objective="Update a small existing unit-test helper",
            department="engineering",
            capability="backend_code",
            allowed_paths=("empire_os/search/",),
            lease_resources=("domain:software_test",),
            pytest_targets=("tests/../../unsafe.py",),
        ).validate()



def test_sandbox_prefers_exact_authorised_source_code_without_symbol_scan():
    from types import SimpleNamespace
    from empire_os.coder.context import ContextDocument, ContextPack
    from empire_os.empire_coder_sandbox_runner import _scoped_source_context

    reads = []

    def read(path, *, max_chars):
        reads.append((path, max_chars))
        return "class ProviderHealth:\n    def _load(self):\n        return {}"

    coder = SimpleNamespace(repo=SimpleNamespace(read=read))
    original = ContextPack(
        objective="Repair the existing software loader",
        task_state={},
        documents=(
            ContextDocument("docs/BLUEPRINT_V6.md", "original blueprint", "B" * 2000),
            ContextDocument("empire_os/unrelated.py", "broad search match", "X" * 1800),
        ),
        symbols=(),
        token_budget_chars=8000,
    )
    scoped = _scoped_source_context(
        coder, original,
        ("empire_os/coder/provider_health.py", "tests/coder/test_provider_health.py"),
    )
    assert reads == [
        ("empire_os/coder/provider_health.py", 2400),
        ("tests/coder/test_provider_health.py", 2400),
    ]
    assert [doc.path for doc in scoped.documents] == [
        "empire_os/coder/provider_health.py",
        "tests/coder/test_provider_health.py",
        "docs/BLUEPRINT_V6.md",
    ]
    assert "ProviderHealth" in scoped.documents[0].excerpt
    assert scoped.documents[-1].excerpt == "B" * 800
    assert scoped.token_budget_chars == 6000
    assert original.documents[1].path == "empire_os/unrelated.py"


def test_sandbox_context_rejects_traversal_and_preserves_pack_on_no_sources():
    from types import SimpleNamespace
    from empire_os.coder.context import ContextPack
    from empire_os.empire_coder_sandbox_runner import _scoped_source_context

    reads = []

    def read(path, *, max_chars):
        reads.append(path)
        raise OSError("source missing")

    coder = SimpleNamespace(repo=SimpleNamespace(read=read))
    original = ContextPack("software task", {}, (), (), 4000)
    result = _scoped_source_context(
        coder, original,
        ("../outside.py", "/etc/passwd", "empire_os/safe.py"),
    )
    assert result is original
    assert reads == ["empire_os/safe.py"]



def test_sandbox_inference_deadline_interrupts_model_wait_and_restores_signal():
    import signal
    import time
    from empire_os.empire_coder_sandbox_runner import _bounded_inference_runtime

    if not hasattr(signal, "setitimer"):
        pytest.skip("POSIX runtime deadline required")
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0
    handler = signal.getsignal(signal.SIGALRM)
    with pytest.raises(EmpireCoderSandboxError, match="model_inference_deadline_exceeded"):
        with _bounded_inference_runtime(0.03):
            time.sleep(0.35)
    assert signal.getsignal(signal.SIGALRM) is handler
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0

    with _bounded_inference_runtime(0.4):
        assert 2 + 2 == 4
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0


def test_sandbox_runtime_deadline_fails_closed_if_other_timer_is_active(monkeypatch):
    import signal
    from empire_os.empire_coder_sandbox_runner import _bounded_inference_runtime

    if not hasattr(signal, "getitimer"):
        pytest.skip("POSIX runtime deadline required")
    original_handler = signal.getsignal(signal.SIGALRM)
    monkeypatch.setattr(signal, "getitimer", lambda _which: (15.0, 0.0))
    with pytest.raises(EmpireCoderSandboxError, match="existing_process_deadline"):
        with _bounded_inference_runtime(30):
            raise AssertionError("deadline conflict must never execute model")
    assert signal.getsignal(signal.SIGALRM) is original_handler


def test_sandbox_runtime_deadline_rejects_non_main_thread():
    from concurrent.futures import ThreadPoolExecutor
    from empire_os.empire_coder_sandbox_runner import _bounded_inference_runtime

    def outside_main_thread():
        with _bounded_inference_runtime(1):
            return "BAD_UNBOUNDED_INFERENCE"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(outside_main_thread)
        with pytest.raises(EmpireCoderSandboxError, match="model_deadline_requires_main_thread"):
            future.result()


def test_sandbox_runtime_deadline_already_expired_blocks_inference():
    from empire_os.empire_coder_sandbox_runner import _bounded_inference_runtime

    with pytest.raises(EmpireCoderSandboxError, match="model_inference_deadline_exceeded"):
        with _bounded_inference_runtime(-1):
            raise AssertionError("expired inference must never run")


def test_original_worker_and_isolated_sandbox_share_inference_lock(tmp_path):
    import fcntl
    from empire_os.empire_coder_sandbox_runner import (
        _shared_coder_ollama_lock,
        EmpireCoderSandboxError,
    )
    original_lock = tmp_path / "runtime/coder/ollama.lock"
    original_lock.parent.mkdir(parents=True)
    original_lock.touch()
    with _shared_coder_ollama_lock(tmp_path):
        # Independent open-file handles conflict, even in one process.
        with original_lock.open("r+") as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(EmpireCoderSandboxError, match="inference_busy"):
            with _shared_coder_ollama_lock(tmp_path):
                raise AssertionError("should not enter nested inference")
    # Lock release is guaranteed after both success and failure.
    with _shared_coder_ollama_lock(tmp_path):
        pass


def test_original_coder_lock_absence_or_symlink_fails_closed(tmp_path):
    from empire_os.empire_coder_sandbox_runner import (
        _shared_coder_ollama_lock,
        EmpireCoderSandboxError,
    )
    with pytest.raises(EmpireCoderSandboxError, match="lock_unavailable"):
        with _shared_coder_ollama_lock(tmp_path):
            pass
    lock = tmp_path / "runtime/coder/ollama.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("")
    lock.symlink_to(elsewhere)
    with pytest.raises(EmpireCoderSandboxError, match="lock_unavailable"):
        with _shared_coder_ollama_lock(tmp_path):
            pass


def test_shared_inference_lock_released_after_exception(tmp_path):
    from empire_os.empire_coder_sandbox_runner import _shared_coder_ollama_lock
    lock = tmp_path / "runtime/coder/ollama.lock"
    lock.parent.mkdir(parents=True)
    lock.touch()
    with pytest.raises(RuntimeError, match="synthetic code exception"):
        with _shared_coder_ollama_lock(tmp_path):
            raise RuntimeError("synthetic code exception")
    with _shared_coder_ollama_lock(tmp_path):
        pass



def test_sandbox_model_failures_persist_across_isolated_clones(tmp_path):
    """Use authentic ProviderHealth logic, never call local inference."""
    from empire_os.coder.provider_health import ProviderHealth
    from empire_os.empire_coder_sandbox_runner import _SandboxWriterHealth

    original_path = tmp_path / "runtime/coder/model_health.json"
    original = ProviderHealth(original_path)
    original.record_failure("ollama", "qwen3-coder:30b", "TimeoutError")
    original_before = original_path.read_bytes()

    sandbox = _SandboxWriterHealth(tmp_path)
    assert ("ollama", "qwen3-coder:30b") in sandbox.excluded_routes()
    sandbox.record_failure(
        "llama_cpp", "qwen2.5-coder:1.5b",
        "EmpireCoderSandboxError:model_inference_deadline_exceeded",
    )
    # A new disposable Coder clone reads the original, retained telemetry.
    new_clone = _SandboxWriterHealth(tmp_path)
    assert ("llama_cpp", "qwen2.5-coder:1.5b") in new_clone.excluded_routes()
    assert ("ollama", "qwen3-coder:30b") in new_clone.excluded_routes()
    first = new_clone.snapshot()["routes"]["llama_cpp:qwen2.5-coder:1.5b"]
    assert first["cooldown_seconds_applied"] == 300
    assert "TimeoutError" in first["last_error"]
    new_clone.record_failure(
        "llama_cpp", "qwen2.5-coder:1.5b",
        "EmpireCoderSandboxError:model_inference_deadline_exceeded",
    )
    second = new_clone.snapshot()["routes"]["llama_cpp:qwen2.5-coder:1.5b"]
    assert second["cooldown_seconds_applied"] == 600

    # The original worker's own provider state is never overwritten.
    assert original_path.read_bytes() == original_before
    new_clone.record_success("llama_cpp", "qwen2.5-coder:1.5b")
    assert ("llama_cpp", "qwen2.5-coder:1.5b") not in new_clone.excluded_routes()
    assert ("ollama", "qwen3-coder:30b") in new_clone.excluded_routes()


def test_sandbox_model_health_recovers_malformed_private_cache(tmp_path):
    from empire_os.empire_coder_sandbox_runner import _SandboxWriterHealth

    private = tmp_path / "runtime/execution_plane/coder_sandbox_model_health.json"
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text('{"routes": null}')
    health = _SandboxWriterHealth(tmp_path)
    assert health.excluded_routes() == ()
    health.record_failure("llama_cpp", "tiny", "TimeoutError")
    assert ("llama_cpp", "tiny") in health.excluded_routes()


def _codex_local_git_repo(tmp_path):
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    subprocess.run(
        ("git", "branch", "-M", "agent/data-cloud-wave4"),
        cwd=root, check=True,
    )
    (root / "app.py").write_text("VALUE = 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text(
        "from app import VALUE\n\ndef test_value():\n    assert VALUE == 2\n"
    )
    subprocess.run(("git", "add", "app.py", "tests/test_app.py"), cwd=root, check=True)
    subprocess.run(
        ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "baseline"), cwd=root, check=True,
    )
    return root


def _fake_codex(tmp_path, *, changed_path="app.py", body="VALUE = 2"):
    cli = tmp_path / "fake-codex"
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "if sys.argv[1:3] == ['login','status']:\n"
        "    print('Logged in using ChatGPT', file=sys.stderr)\n"
        "    sys.exit(0)\n"
        "assert not Path('/srv/empire_os/runtime/execution_plane/leases.json').exists()\n"
        f"Path({changed_path!r}).write_text({(body + chr(10))!r})\n"
        "print('edited candidate')\n"
    )
    cli.chmod(0o700)
    return cli


def _codex_job(*, paths=("app.py",), tests=("tests/test_app.py",), job_id="codex-test"):
    return EmpireCoderSandboxJob(
        job_id=job_id,
        objective="Change app VALUE from 1 to 2 so the test passes.",
        department="engineering",
        capability="backend_code",
        allowed_paths=paths,
        lease_resources=("path:app.py",),
        pytest_targets=tests,
        max_runtime_seconds=200,
    )


def test_codex_local_candidate_isolated_scoped_verified_and_never_pushed(
    tmp_path, monkeypatch,
):
    import hashlib
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    cli = _fake_codex(tmp_path)
    monkeypatch.setattr(module, "_local_codex_binary", lambda: str(cli))
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(), work_root=tmp_path / "isolated",
    )
    assert result["status"] == "LOCAL_PROPOSAL_READY", result
    assert result["verification_passed"] is True
    assert result["changed_paths"] == ["app.py"]
    assert result["production_mutation"] is False
    assert result["production_deploy"] is False
    assert result["founder_gate_required"] is True
    patch = Path(result["proposal_patch"])
    assert patch.exists()
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == result["proposal_sha256"]
    assert (root / "app.py").read_text() == "VALUE = 1\n"
    assert not list((tmp_path / "isolated").glob("*"))
    assert not list((root / "runtime/execution_plane/leases").glob("*.json")) if (
        root / "runtime/execution_plane/leases"
    ).is_dir() else True


def test_codex_local_candidate_refuses_unapproved_paths(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    cli = _fake_codex(tmp_path, changed_path="other.py")
    monkeypatch.setattr(module, "_local_codex_binary", lambda: str(cli))
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(), work_root=tmp_path / "isolated",
    )
    assert result["status"] == "PATH_POLICY_FAILED"
    assert result["reason"] == "model_changed_unapproved_path"
    assert result["proposal_patch"] is None
    assert not (root / "other.py").exists()


def test_codex_local_candidate_fails_closed_without_real_tests(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    monkeypatch.setattr(
        module, "_local_codex_binary",
        lambda: (_ for _ in ()).throw(AssertionError("Codex should not run")),
    )
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(tests=()), work_root=tmp_path / "isolated",
    )
    assert result["status"] == "HELD"
    assert result["reason"] == "required_tests_required"


def test_codex_local_candidate_missing_login_or_binary_fails_closed(
    tmp_path, monkeypatch,
):
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    monkeypatch.setattr(module, "_local_codex_binary", lambda: None)
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(), work_root=tmp_path / "isolated",
    )
    assert result["status"] == "HELD"
    assert result["reason"] == "codex_cli_not_installed"


def test_codex_local_candidate_preserves_existing_workspace(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    cli = _fake_codex(tmp_path)
    monkeypatch.setattr(module, "_local_codex_binary", lambda: str(cli))
    existing = tmp_path / "isolated/codex-codex-test"
    existing.mkdir(parents=True)
    (existing / "other_agent.txt").write_text("preserve")
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(), work_root=tmp_path / "isolated",
    )
    assert result["status"] == "HELD"
    assert result["reason"] == "isolated_clone_already_exists"
    assert (existing / "other_agent.txt").read_text() == "preserve"


def test_codex_candidate_aborts_if_original_head_advances_during_inference(
    tmp_path, monkeypatch,
):
    import subprocess
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    monkeypatch.setattr(
        module, "_local_codex_binary", lambda: str(_fake_codex(tmp_path)),
    )
    original = module._run
    seen = 0

    def concurrently_advanced(argv, **kwargs):
        nonlocal seen
        if argv[:3] == ["git", "rev-parse", "HEAD"]:
            seen += 1
            if seen == 2:
                return subprocess.CompletedProcess(
                    argv, returncode=0, stdout="f" * 40 + "\n", stderr="",
                )
        return original(argv, **kwargs)

    monkeypatch.setattr(module, "_run", concurrently_advanced)
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(job_id="head-advanced-canary"),
        work_root=tmp_path / "isolated",
    )
    assert seen >= 2
    assert result["reason"] == "source_head_changed_during_candidate"
    assert result["verification_passed"] is False
    assert result["proposal_patch"] is None
    assert not list((root / "runtime/execution_plane/coder_proposals").glob("*.patch"))


def test_os_isolated_model_runtime_requires_bwrap(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as module

    real_which = module.shutil.which
    monkeypatch.setattr(
        module.shutil, "which",
        lambda program: None if program == "bwrap" else real_which(program),
    )
    cli = _fake_codex(tmp_path)
    assert module._isolated_codex_argv(
        cli=str(cli), clone=tmp_path,
    ) is None


def test_codex_authenticated_under_narrow_hermes_systemd_path(tmp_path, monkeypatch):
    """The real service PATH omits Node: prepend the CLI's own Node runtime."""
    import os
    import subprocess
    import empire_os.empire_coder_sandbox_runner as module

    repo = _codex_local_git_repo(tmp_path)
    codex = tmp_path / "codex-bin"
    codex.write_text("#!/usr/bin/env node\n")
    codex.chmod(0o700)
    node_bin = tmp_path / "nvm/versions/node/v99.0.0/bin"
    node_bin.mkdir(parents=True)
    (node_bin / "node").write_text("executable test fixture")
    monkeypatch.setattr(module, "_local_codex_binary", lambda: str(codex))
    monkeypatch.setattr(module, "_local_codex_node_bin", lambda _cli: node_bin)
    systemd_path = (
        "/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:"
        "/usr/sbin:/usr/bin:/sbin:/bin"
    )
    monkeypatch.setenv("PATH", systemd_path)
    original_run = module._run
    login_calls = []

    def guarded_run(argv, *, cwd, env=None, timeout=180):
        if argv == [str(codex), "login", "status"]:
            assert env is not None
            assert env["PATH"] == str(node_bin) + os.pathsep + systemd_path
            login_calls.append(True)
            return subprocess.CompletedProcess(
                argv, 0, stdout="", stderr="Logged in using ChatGPT\n",
            )
        if argv == ["git", "rev-parse", "HEAD"]:
            # Stop after the real authenticated preflight, before clone/model.
            return subprocess.CompletedProcess(
                argv, 1, stdout="", stderr="isolated test stops here",
            )
        return original_run(argv, cwd=cwd, env=env, timeout=timeout)

    monkeypatch.setattr(module, "_run", guarded_run)
    result = module.run_empire_coder_codex_local_candidate(
        repo, _codex_job(job_id="node-systemd-auth-regression"),
        work_root=tmp_path / "model-work",
    )
    assert login_calls == [True]
    assert result["reason"] == "source_branch_not_current_head"
    assert result["reason"] != "codex_cli_not_authenticated"
    assert not (tmp_path / "model-work").exists()


def test_missing_codex_node_runtime_fails_before_auth(tmp_path, monkeypatch):
    import empire_os.empire_coder_sandbox_runner as module

    root = _codex_local_git_repo(tmp_path)
    monkeypatch.setattr(module, "_local_codex_binary", lambda: str(tmp_path / "codex"))
    monkeypatch.setattr(module, "_local_codex_node_bin", lambda _cli: None)
    monkeypatch.setattr(
        module, "_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("no subprocess without Node runtime")
        ),
    )
    result = module.run_empire_coder_codex_local_candidate(
        root, _codex_job(job_id="missing-node-held"),
    )
    assert result["status"] == "HELD"
    assert result["reason"] == "codex_node_runtime_unavailable"
