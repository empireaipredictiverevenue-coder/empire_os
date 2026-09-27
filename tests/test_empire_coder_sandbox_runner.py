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
