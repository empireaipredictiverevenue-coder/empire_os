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
