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
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_CAPABILITY"] == "3"
        assert os.environ["EMPIRE_CODER_LLAMA_CPP_ROLES"] == "planner,writer,verifier"
        assert os.environ["EMPIRE_CODER_OLLAMA_TIMEOUT_SECONDS"] == "30"

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
